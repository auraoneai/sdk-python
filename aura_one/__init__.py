"""
AuraOne Python SDK

Official Python SDK for AuraOne API - Comprehensive AI platform for training, analytics, and collaboration.

Basic Usage:
    >>> from aura_one import AuraOneClient
    >>> client = AuraOneClient.with_api_key("your-api-key")
    >>>
    >>> # Track analytics event
    >>> client.analytics.track_user("button_clicked", {"button": "submit", "page": "dashboard"})
    >>>
    >>> # Export training data
    >>> training_data = client.training.export_dpo(org_id="your-org-id", min_confidence=3)

Async Usage:
    >>> from aura_one import AsyncAuraOneClient
    >>> client = AsyncAuraOneClient.with_api_key("your-api-key")
    >>>
    >>> # Track analytics event (async)
    >>> await client.analytics.track_user("button_clicked", {"button": "submit", "page": "dashboard"})
    >>>
    >>> # Export training data (async)
    >>> training_data = await client.training.export_dpo(org_id="your-org-id", min_confidence=3)

Environment Variables:
    >>> from aura_one import AuraOneClient
    >>> # Reads from AURAONE_API_KEY or AURAONE_TOKEN environment variables
    >>> client = AuraOneClient.from_environment()

Error Handling:
    >>> from aura_one import AuraOneError, AuthenticationError, RateLimitError
    >>> try:
    ...     result = client.analytics.track_user("event", {})
    ... except AuthenticationError:
    ...     print("Invalid credentials")
    ... except RateLimitError:
    ...     print("Rate limit exceeded")
    ... except AuraOneError as e:
    ...     print(f"API error: {e}")
"""

from .client import AuraOneClient, AsyncAuraOneClient
from .graphql import GraphQLClient, AsyncGraphQLClient, GraphQLExecutionError
from .exceptions import (
    AuraOneError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    NotFoundError,
)
from .types import (
    ClientConfig,
    AnalyticsEvent,
    TrainingExportRequest,
    APIKey,
    EventCategory,
    TrainingFormat,
)

# Version info
__version__ = "1.0.0"
__api_version__ = "1.0"
__author__ = "AuraOne Team"
__email__ = "support@auraone.ai"
__license__ = "MIT"

# Default configuration
DEFAULT_CONFIG = {
    "base_url": "https://api.auraone.ai",
    "timeout": 30.0,
    "max_retries": 3,
    "rate_limit_retry": True,
    "debug": False,
}

# Convenience functions
def with_api_key(api_key: str, **kwargs) -> AuraOneClient:
    """Create AuraOne client with API key authentication.

    Args:
        api_key: Your AuraOne API key
        **kwargs: Additional client configuration options

    Returns:
        AuraOne client instance

    Example:
        >>> client = with_api_key("aura_live_1234567890abcdef", debug=True)
    """
    return AuraOneClient.with_api_key(api_key, **kwargs)

def with_token(token: str, refresh_token: str = None, **kwargs) -> AuraOneClient:
    """Create AuraOne client with JWT token authentication.

    Args:
        token: JWT access token
        refresh_token: Optional refresh token
        **kwargs: Additional client configuration options

    Returns:
        AuraOne client instance

    Example:
        >>> client = with_token("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...", "refresh_token_here")
    """
    return AuraOneClient.with_token(token, refresh_token, **kwargs)

def from_environment(**kwargs) -> AuraOneClient:
    """Create AuraOne client from environment variables.

    Args:
        **kwargs: Additional client configuration options

    Returns:
        AuraOne client instance

    Example:
        >>> client = from_environment(timeout=45.0, max_retries=5)
    """
    return AuraOneClient.from_environment(**kwargs)

# Async versions
def async_with_api_key(api_key: str, **kwargs) -> AsyncAuraOneClient:
    """Create async AuraOne client with API key authentication.

    Args:
        api_key: Your AuraOne API key
        **kwargs: Additional client configuration options

    Returns:
        Async AuraOne client instance

    Example:
        >>> client = async_with_api_key("aura_live_1234567890abcdef", debug=True)
    """
    return AsyncAuraOneClient.with_api_key(api_key, **kwargs)

def async_with_token(token: str, refresh_token: str = None, **kwargs) -> AsyncAuraOneClient:
    """Create async AuraOne client with JWT token authentication.

    Args:
        token: JWT access token
        refresh_token: Optional refresh token
        **kwargs: Additional client configuration options

    Returns:
        Async AuraOne client instance

    Example:
        >>> client = async_with_token("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...", "refresh_token_here")
    """
    return AsyncAuraOneClient.with_token(token, refresh_token, **kwargs)

def async_from_environment(**kwargs) -> AsyncAuraOneClient:
    """Create async AuraOne client from environment variables.

    Args:
        **kwargs: Additional client configuration options

    Returns:
        Async AuraOne client instance

    Example:
        >>> client = async_from_environment(timeout=45.0, max_retries=5)
    """
    return AsyncAuraOneClient.from_environment(**kwargs)

# Validation utilities
def is_valid_api_key(api_key: str) -> bool:
    """Validate API key format.

    Args:
        api_key: API key to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> if is_valid_api_key(user_input):
        ...     client = with_api_key(user_input)
        ... else:
        ...     print("Invalid API key format")
    """
    from .auth import AuthProvider
    return AuthProvider.is_valid_api_key(api_key)

def is_valid_jwt_token(token: str) -> bool:
    """Validate JWT token format.

    Args:
        token: JWT token to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> if is_valid_jwt_token(user_token):
        ...     client = with_token(user_token)
        ... else:
        ...     print("Invalid JWT token format")
    """
    from .auth import AuthProvider
    return AuthProvider.is_valid_jwt_token(token)

# Export everything
__all__ = [
    # Main classes
    "AuraOneClient",
    "AsyncAuraOneClient",
    "GraphQLClient",
    "AsyncGraphQLClient",

    # Exceptions
    "AuraOneError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "NotFoundError",
    "GraphQLExecutionError",

    # Types
    "ClientConfig",
    "AnalyticsEvent",
    "TrainingExportRequest",
    "APIKey",
    "EventCategory",
    "TrainingFormat",

    # Convenience functions
    "with_api_key",
    "with_token",
    "from_environment",
    "async_with_api_key",
    "async_with_token",
    "async_from_environment",

    # Validation utilities
    "is_valid_api_key",
    "is_valid_jwt_token",

    # Constants
    "DEFAULT_CONFIG",
]
