import os
from typing import Any, Dict, Optional

from .async_utils import AsyncHttpClient
from .auth import AuthProvider
from .exceptions import AuthenticationError, ConfigurationError
from .graphql import AsyncGraphQLClient
from .services import (
    AsyncAnalyticsService,
    AsyncAuthService,
    AsyncBillingService,
    AsyncCollaborationService,
    AsyncEvaluationsService,
    AsyncGovernanceService,
    AsyncIntegrationsService,
    AsyncLabsService,
    AsyncRoboticsService,
    AsyncTrainingService,
)
from .types import ClientConfig
from .version import __version__


class AsyncAuraOneClient:
    def __init__(self, config: Optional[ClientConfig] = None):
        self.config = config or ClientConfig()
        self._validate_config()

        self.auth_provider = AuthProvider(
            api_key=self.config.api_key,
            debug=self.config.debug
        )

        self.http_client = AsyncHttpClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            debug=self.config.debug,
            auth_provider=self.auth_provider,
        )

        self.auth = AsyncAuthService(self.http_client)
        self.analytics = AsyncAnalyticsService(self.http_client)
        self.training = AsyncTrainingService(self.http_client)
        self.billing = AsyncBillingService(self.http_client)
        self.collaboration = AsyncCollaborationService(self.http_client)
        self.robotics = AsyncRoboticsService(self.http_client)
        self.evaluations = AsyncEvaluationsService(self.http_client)
        self.labs = AsyncLabsService(self.http_client)
        self.governance = AsyncGovernanceService(self.http_client)
        self.integrations = AsyncIntegrationsService(self.http_client)
        self.graphql = AsyncGraphQLClient(self.http_client)

    @classmethod
    def with_api_key(cls, api_key: str, **kwargs) -> "AsyncAuraOneClient":
        if not AuthProvider.is_valid_api_key(api_key):
            raise AuthenticationError("Invalid API key format")

        config = ClientConfig(api_key=api_key, **kwargs)
        return cls(config)

    @classmethod
    def with_token(cls, token: str, refresh_token: Optional[str] = None, **kwargs) -> "AsyncAuraOneClient":
        if not AuthProvider.is_valid_jwt_token(token):
            raise AuthenticationError("Invalid JWT token format")

        config = ClientConfig(**kwargs)
        client = cls(config)
        client.auth_provider.set_token(token, refresh_token)
        return client

    @classmethod
    def from_environment(cls, **kwargs) -> "AsyncAuraOneClient":
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

    async def set_api_key(self, api_key: str) -> None:
        if not AuthProvider.is_valid_api_key(api_key):
            raise AuthenticationError("Invalid API key format")

        self.auth_provider.set_api_key(api_key)

    async def set_token(self, token: str, refresh_token: Optional[str] = None) -> None:
        if not AuthProvider.is_valid_jwt_token(token):
            raise AuthenticationError("Invalid JWT token format")

        self.auth_provider.set_token(token, refresh_token)

    async def clear_auth(self) -> None:
        self.auth_provider.clear_auth()

    def is_authenticated(self) -> bool:
        return self.auth_provider.is_authenticated()

    def get_auth_method(self) -> str:
        return self.auth_provider.get_auth_method()

    async def test_connection(self) -> Dict[str, Any]:
        try:
            health = await self.analytics.get_health()
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
        if not self.config.base_url or not self.config.base_url.startswith(("http://", "https://")):
            raise ConfigurationError("Invalid base_url provided")

        if self.config.timeout <= 0 or self.config.timeout > 300:
            raise ConfigurationError("Timeout must be between 0 and 300 seconds")

        if self.config.max_retries < 0 or self.config.max_retries > 10:
            raise ConfigurationError("max_retries must be between 0 and 10")

    async def close(self) -> None:
        await self.http_client.close()

    async def __aenter__(self) -> "AsyncAuraOneClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


__all__ = ["AsyncAuraOneClient"]
