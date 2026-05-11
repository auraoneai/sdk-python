"""Exception classes for AuraOne SDK."""

from typing import Optional, Dict, Any


class AuraOneError(Exception):
    """Base exception class for AuraOne SDK errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        """Initialize AuraOne error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code

    def __str__(self) -> str:
        """String representation of error."""
        parts = [self.message]
        if self.code:
            parts.append(f"Code: {self.code}")
        if self.status_code:
            parts.append(f"Status: {self.status_code}")
        return " | ".join(parts)

    def __repr__(self) -> str:
        """Detailed representation of error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r})"
        )


class AuthenticationError(AuraOneError):
    """Authentication failed."""

    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTH_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize authentication error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details, status_code=401)


class AuthorizationError(AuraOneError):
    """Authorization failed (forbidden)."""

    def __init__(
        self,
        message: str = "Access forbidden",
        code: str = "AUTHORIZATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize authorization error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details, status_code=403)


class RateLimitError(AuraOneError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: str = "RATE_LIMIT",
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ):
        """Initialize rate limit error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
            retry_after: Seconds to wait before retrying
        """
        super().__init__(message, code, details, status_code=429)
        self.retry_after = retry_after


class ValidationError(AuraOneError):
    """Request validation failed."""

    def __init__(
        self,
        message: str = "Invalid request parameters",
        code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validation error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details, status_code=400)


class NotFoundError(AuraOneError):
    """Resource not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize not found error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details, status_code=404)


class ConflictError(AuraOneError):
    """Resource conflict."""

    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize conflict error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details, status_code=409)


class ServerError(AuraOneError):
    """Server error (5xx)."""

    def __init__(
        self,
        message: str = "Internal server error",
        code: str = "SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        """Initialize server error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
            status_code: HTTP status code
        """
        super().__init__(message, code, details, status_code)


class NetworkError(AuraOneError):
    """Network connection error."""

    def __init__(
        self,
        message: str = "Network error",
        code: str = "NETWORK_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize network error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details)


class TimeoutError(AuraOneError):
    """Request timeout error."""

    def __init__(
        self,
        message: str = "Request timeout",
        code: str = "TIMEOUT",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize timeout error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details, status_code=408)


class ConfigurationError(AuraOneError):
    """SDK configuration error."""

    def __init__(
        self,
        message: str = "Invalid configuration",
        code: str = "CONFIG_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize configuration error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details)


class ResponseParsingError(AuraOneError):
    """Error parsing API response."""

    def __init__(
        self,
        message: str = "Failed to parse response",
        code: str = "PARSE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize response parsing error.

        Args:
            message: Error message
            code: Error code
            details: Additional error details
        """
        super().__init__(message, code, details)


def create_error_from_response(
    status_code: int,
    response_data: Dict[str, Any],
    default_message: str = "API error",
) -> AuraOneError:
    """Create appropriate error from API response.

    Args:
        status_code: HTTP status code
        response_data: Response data containing error information
        default_message: Default error message

    Returns:
        Appropriate AuraOne error instance
    """
    message = response_data.get("error", default_message)
    code = response_data.get("code")
    details = response_data.get("details")

    if status_code == 400:
        return ValidationError(message, code, details)
    elif status_code == 401:
        return AuthenticationError(message, code, details)
    elif status_code == 403:
        return AuthorizationError(message, code, details)
    elif status_code == 404:
        return NotFoundError(message, code, details)
    elif status_code == 409:
        return ConflictError(message, code, details)
    elif status_code == 429:
        retry_after = None
        if details and "retry_after" in details:
            retry_after = details["retry_after"]
        return RateLimitError(message, code, details, retry_after)
    elif status_code >= 500:
        return ServerError(message, code, details, status_code)
    else:
        return AuraOneError(message, code, details, status_code)


__all__ = [
    "AuraOneError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ServerError",
    "NetworkError",
    "TimeoutError",
    "ConfigurationError",
    "ResponseParsingError",
    "create_error_from_response",
]