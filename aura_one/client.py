"""Main AuraOne API client with sync and async support."""

import os
from typing import Optional, Dict, Any

from .async_client import AsyncAuraOneClient
from .types import ClientConfig
from .auth import AuthProvider
from .utils import HttpClient
from .services import (
    AuthService,
    AnalyticsService,
    TrainingService,
    BillingService,
    CollaborationService,
    RoboticsService,
    EvaluationsService,
    LabsService,
    GovernanceService,
    IntegrationsService,
)
from .exceptions import AuthenticationError, ConfigurationError
from .graphql import GraphQLClient
from .version import __version__


class AuraOneClient:
    """Synchronous AuraOne API client.

    This client provides access to all AuraOne API endpoints using synchronous HTTP requests.
    It's suitable for traditional Python applications, scripts, and environments where
    async/await is not required.

    Example:
        >>> client = AuraOneClient.with_api_key("your-api-key")
        >>> client.analytics.track_user("button_clicked", {"button": "submit"})
        >>> training_data = client.training.export_dpo(org_id="your-org-id")
    """

    def __init__(self, config: Optional[ClientConfig] = None):
        """Initialize the AuraOne client.

        Args:
            config: Client configuration options
        """
        self.config = config or ClientConfig()
        self._validate_config()

        # Initialize authentication provider
        self.auth_provider = AuthProvider(
            api_key=self.config.api_key,
            debug=self.config.debug
        )

        # Initialize HTTP client
        self.http_client = HttpClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            debug=self.config.debug,
            auth_provider=self.auth_provider,
        )

        # Initialize services
        self.auth = AuthService(self.http_client)
        self.analytics = AnalyticsService(self.http_client)
        self.training = TrainingService(self.http_client)
        self.billing = BillingService(self.http_client)
        self.collaboration = CollaborationService(self.http_client)
        self.robotics = RoboticsService(self.http_client)
        self.evaluations = EvaluationsService(self.http_client)
        self.labs = LabsService(self.http_client)
        self.governance = GovernanceService(self.http_client)
        self.integrations = IntegrationsService(self.http_client)
        self.graphql = GraphQLClient(self.http_client)

    @classmethod
    def with_api_key(cls, api_key: str, **kwargs) -> "AuraOneClient":
        """Create client with API key authentication.

        Args:
            api_key: Your AuraOne API key
            **kwargs: Additional client configuration options

        Returns:
            AuraOne client instance

        Raises:
            AuthenticationError: If API key format is invalid

        Example:
            >>> client = AuraOneClient.with_api_key(
            ...     "aura_live_1234567890abcdef",
            ...     debug=True,
            ...     timeout=60.0
            ... )
        """
        if not AuthProvider.is_valid_api_key(api_key):
            raise AuthenticationError("Invalid API key format")

        config = ClientConfig(api_key=api_key, **kwargs)
        return cls(config)

    @classmethod
    def with_token(cls, token: str, refresh_token: Optional[str] = None, **kwargs) -> "AuraOneClient":
        """Create client with JWT token authentication.

        Args:
            token: JWT access token
            refresh_token: Optional refresh token
            **kwargs: Additional client configuration options

        Returns:
            AuraOne client instance

        Raises:
            AuthenticationError: If token format is invalid

        Example:
            >>> client = AuraOneClient.with_token(
            ...     "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            ...     refresh_token="refresh_token_here"
            ... )
        """
        if not AuthProvider.is_valid_jwt_token(token):
            raise AuthenticationError("Invalid JWT token format")

        config = ClientConfig(**kwargs)
        client = cls(config)
        client.auth_provider.set_token(token, refresh_token)
        return client

    @classmethod
    def from_environment(cls, **kwargs) -> "AuraOneClient":
        """Create client from environment variables.

        Reads authentication credentials from:
        - AURAONE_API_KEY
        - AURAONE_TOKEN (with optional AURAONE_REFRESH_TOKEN)

        Args:
            **kwargs: Additional client configuration options

        Returns:
            AuraOne client instance

        Raises:
            AuthenticationError: If no valid credentials found in environment

        Example:
            >>> # Set AURAONE_API_KEY=your_api_key in environment
            >>> client = AuraOneClient.from_environment(
            ...     base_url="https://api-staging.auraone.ai"
            ... )
        """
        api_key = os.getenv("AURAONE_API_KEY")
        token = os.getenv("AURAONE_TOKEN")
        refresh_token = os.getenv("AURAONE_REFRESH_TOKEN")

        if api_key:
            return cls.with_api_key(api_key, **kwargs)
        elif token:
            return cls.with_token(token, refresh_token, **kwargs)
        else:
            raise AuthenticationError(
                "No authentication credentials found in environment variables. "
                "Set AURAONE_API_KEY or AURAONE_TOKEN environment variable."
            )

    def set_api_key(self, api_key: str) -> None:
        """Set API key for authentication.

        Args:
            api_key: Your AuraOne API key

        Raises:
            AuthenticationError: If API key format is invalid
        """
        if not AuthProvider.is_valid_api_key(api_key):
            raise AuthenticationError("Invalid API key format")

        self.auth_provider.set_api_key(api_key)

    def set_token(self, token: str, refresh_token: Optional[str] = None) -> None:
        """Set JWT token for authentication.

        Args:
            token: JWT access token
            refresh_token: Optional refresh token

        Raises:
            AuthenticationError: If token format is invalid
        """
        if not AuthProvider.is_valid_jwt_token(token):
            raise AuthenticationError("Invalid JWT token format")

        self.auth_provider.set_token(token, refresh_token)

    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        self.auth_provider.clear_auth()

    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self.auth_provider.is_authenticated()

    def get_auth_method(self) -> str:
        """Get current authentication method."""
        return self.auth_provider.get_auth_method()

    def test_connection(self) -> Dict[str, Any]:
        """Test API connectivity and authentication.

        Returns:
            Dictionary with connection status and information

        Example:
            >>> status = client.test_connection()
            >>> if status["success"]:
            ...     print("Connected successfully!")
            ... else:
            ...     print(f"Connection failed: {status['message']}")
        """
        try:
            health = self.analytics.get_health()
            return {
                "success": True,
                "authenticated": self.is_authenticated(),
                "method": self.get_auth_method(),
                "message": "Connection successful",
                "service_status": health.status,
            }
        except Exception as e:
            return {
                "success": False,
                "authenticated": self.is_authenticated(),
                "method": self.get_auth_method(),
                "message": str(e),
            }

    def get_config(self) -> Dict[str, Any]:
        """Get client configuration information.

        Returns:
            Dictionary with client configuration details
        """
        return {
            "base_url": self.config.base_url,
            "authenticated": self.is_authenticated(),
            "auth_method": self.get_auth_method(),
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "debug": self.config.debug,
            "version": __version__,
        }

    def _validate_config(self) -> None:
        """Validate client configuration."""
        if not self.config.base_url or not self.config.base_url.startswith(("http://", "https://")):
            raise ConfigurationError("Invalid base_url provided")

        if self.config.timeout <= 0 or self.config.timeout > 300:
            raise ConfigurationError("Timeout must be between 0 and 300 seconds")

        if self.config.max_retries < 0 or self.config.max_retries > 10:
            raise ConfigurationError("max_retries must be between 0 and 10")

    def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        self.http_client.close()

    def __enter__(self) -> "AuraOneClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


__all__ = ["AuraOneClient", "AsyncAuraOneClient"]
