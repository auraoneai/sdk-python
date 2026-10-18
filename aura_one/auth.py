"""Authentication provider for AuraOne SDK."""

import os
import re
import json
import base64
from typing import Dict, Optional, Callable
from datetime import datetime, timezone

from .exceptions import AuthenticationError


class AuthProvider:
    """Handles authentication for AuraOne API requests."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        on_token_refresh: Optional[Callable[[str], None]] = None,
        debug: bool = False,
    ):
        """Initialize authentication provider.

        Args:
            api_key: API key for authentication
            token: JWT token for authentication
            refresh_token: Refresh token for token renewal
            on_token_refresh: Callback when token is refreshed
            debug: Enable debug logging
        """
        self.api_key = api_key
        self.token = token
        self.refresh_token = refresh_token
        self.on_token_refresh = on_token_refresh
        self.debug = debug

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Dictionary of authentication headers
        """
        headers = {}

        if self.api_key:
            headers["X-API-Key"] = self.api_key

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def set_api_key(self, api_key: str) -> None:
        """Set API key for authentication.

        Args:
            api_key: API key to set

        Raises:
            AuthenticationError: If API key format is invalid
        """
        if not self.is_valid_api_key(api_key):
            raise AuthenticationError("Invalid API key format")

        self.api_key = api_key
        # Clear JWT tokens when API key is set
        self.token = None
        self.refresh_token = None

        if self.debug:
            print(f"[AuraOne SDK] API key set: {api_key[:12]}...")

    def set_token(self, token: str, refresh_token: Optional[str] = None) -> None:
        """Set JWT token for authentication.

        Args:
            token: JWT token to set
            refresh_token: Optional refresh token

        Raises:
            AuthenticationError: If token format is invalid
        """
        if not self.is_valid_jwt_token(token):
            raise AuthenticationError("Invalid JWT token format")

        self.token = token
        self.refresh_token = refresh_token
        # Clear API key when JWT token is set
        self.api_key = None

        if self.debug:
            print(f"[AuraOne SDK] JWT token set")

    def is_authenticated(self) -> bool:
        """Check if authentication is configured.

        Returns:
            True if authenticated, False otherwise
        """
        return bool(self.api_key or self.token)

    def get_auth_method(self) -> str:
        """Get current authentication method.

        Returns:
            Authentication method: 'apikey', 'jwt', or 'none'
        """
        if self.api_key:
            return "apikey"
        elif self.token:
            return "jwt"
        else:
            return "none"

    def clear_auth(self) -> None:
        """Clear all authentication data."""
        self.api_key = None
        self.token = None
        self.refresh_token = None

        if self.debug:
            print("[AuraOne SDK] Authentication cleared")

    def get_token_expiration(self) -> Optional[datetime]:
        """Get JWT token expiration time.

        Returns:
            Token expiration datetime or None if not available
        """
        if not self.token:
            return None

        try:
            payload = self.get_token_payload(self.token)
            if payload and "exp" in payload:
                return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        except Exception:
            pass

        return None

    def will_token_expire_soon(self, minutes_threshold: int = 5) -> bool:
        """Check if current token will expire soon.

        Args:
            minutes_threshold: Minutes before expiration to consider "soon"

        Returns:
            True if token will expire soon, False otherwise
        """
        expiration = self.get_token_expiration()
        if not expiration:
            return True

        threshold_seconds = minutes_threshold * 60
        time_until_expiry = (expiration - datetime.now(timezone.utc)).total_seconds()

        return time_until_expiry < threshold_seconds

    @staticmethod
    def is_valid_api_key(api_key: str) -> bool:
        """Validate API key format.

        Args:
            api_key: API key to validate

        Returns:
            True if valid format, False otherwise
        """
        # Platform-issued keys: ak_<8 hex>_<64 hex> (apps/src/lib/security/api-keys.ts).
        # Compute-issued `aoc_` keys are rejected for platform clients (R2);
        # use is_compute_api_key to distinguish them for error messages.
        platform_pattern = r"^ak_[a-f0-9]{8}_[a-f0-9]{64}$"
        return bool(re.match(platform_pattern, api_key))

    @staticmethod
    def is_compute_api_key(api_key: str) -> bool:
        """True when the key is a Compute-authority key (aoc_)."""
        return bool(re.match(r"^aoc_[a-f0-9]{8}_[A-Za-z0-9_\-]{8,128}$", api_key))

    @staticmethod
    def is_valid_jwt_token(token: str) -> bool:
        """Validate JWT token format (basic validation).

        Args:
            token: JWT token to validate

        Returns:
            True if valid format, False otherwise
        """
        try:
            # Basic JWT format validation (three parts separated by dots)
            parts = token.split(".")
            return len(parts) == 3 and all(len(part) > 0 for part in parts)
        except Exception:
            return False

    @staticmethod
    def get_token_payload(token: str) -> Optional[Dict]:
        """Extract token payload without verification.

        Args:
            token: JWT token

        Returns:
            Token payload as dictionary or None if extraction fails
        """
        try:
            if not AuthProvider.is_valid_jwt_token(token):
                return None

            # Get payload part (second part of JWT)
            payload_part = token.split(".")[1]

            # Add padding if needed for base64 decoding
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += "=" * padding

            # Decode base64
            decoded = base64.b64decode(payload_part)
            payload = json.loads(decoded.decode("utf-8"))

            return payload
        except Exception:
            return None

    @staticmethod
    def is_token_expired(token: str) -> bool:
        """Check if JWT token is expired.

        Args:
            token: JWT token to check

        Returns:
            True if expired, False otherwise
        """
        payload = AuthProvider.get_token_payload(token)
        if not payload or "exp" not in payload:
            return True

        # Token expiration is in seconds, compare with current timestamp
        return payload["exp"] < datetime.now(timezone.utc).timestamp()

    @classmethod
    def from_environment(cls, debug: bool = False) -> "AuthProvider":
        """Create AuthProvider from environment variables.

        Args:
            debug: Enable debug logging

        Returns:
            AuthProvider instance

        Environment Variables:
            AURAONE_API_KEY: API key for authentication
            AURAONE_TOKEN: JWT token for authentication
            AURAONE_REFRESH_TOKEN: Refresh token for token renewal
        """
        api_key = os.getenv("AURAONE_API_KEY")
        token = os.getenv("AURAONE_TOKEN")
        refresh_token = os.getenv("AURAONE_REFRESH_TOKEN")

        return cls(
            api_key=api_key,
            token=token,
            refresh_token=refresh_token,
            debug=debug
        )


__all__ = ["AuthProvider"]