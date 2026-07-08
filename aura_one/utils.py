"""HTTP client utilities for AuraOne SDK."""

import json
import time
from typing import Dict, Any, Optional, Protocol, runtime_checkable
from urllib.parse import urljoin, urlencode

import httpx

from .async_utils import AsyncHttpClient
from .types import RequestConfig, RateLimitInfo, RetryConfig
from .auth import AuthProvider
from .exceptions import (
    AuraOneError,
    NetworkError,
    TimeoutError,
    ResponseParsingError,
    create_error_from_response,
)
from .version import __version__


@runtime_checkable
class HttpClientProtocol(Protocol):
    """Protocol for HTTP clients."""

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Make GET request."""
        ...

    def post(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Make POST request."""
        ...

    def put(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Make PUT request."""
        ...

    def delete(self, path: str, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Make DELETE request."""
        ...

    def patch(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Make PATCH request."""
        ...


class HttpClient:
    """Synchronous HTTP client for AuraOne API."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        debug: bool = False,
        auth_provider: Optional[AuthProvider] = None,
    ):
        """Initialize HTTP client.

        Args:
            base_url: Base URL for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            debug: Enable debug logging
            auth_provider: Authentication provider
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug
        self.auth_provider = auth_provider

        # Default headers
        self.default_headers = {
            "Content-Type": "application/json",
            "User-Agent": f"auraone-python-sdk/{__version__}",
        }

        # Initialize httpx client
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

        # Retry configuration
        self.retry_config = RetryConfig(
            max_retries=max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )

    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _build_headers(self, config: Optional[RequestConfig] = None) -> Dict[str, str]:
        """Build request headers."""
        headers = self.default_headers.copy()

        # Add authentication headers
        if self.auth_provider:
            auth_headers = self.auth_provider.get_auth_headers()
            headers.update(auth_headers)

        # Add config headers
        if config and config.headers:
            headers.update(config.headers)

        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle HTTP response."""
        # Extract rate limit info
        rate_limit_info = self._extract_rate_limit_info(response)

        if rate_limit_info and rate_limit_info.remaining == 0:
            if self.debug:
                print(f"[AuraOne SDK] Rate limit info: {rate_limit_info}")

        # Handle error responses
        if not response.is_success:
            self._handle_error_response(response, rate_limit_info)

        # Parse response content
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise ResponseParsingError(f"Failed to parse JSON response: {e}")

        elif "application/x-jsonlines" in content_type:
            return response.text

        elif "text/" in content_type:
            return response.text

        else:
            # Binary data
            return response.content

    def _handle_error_response(
        self,
        response: httpx.Response,
        rate_limit_info: Optional[RateLimitInfo] = None
    ) -> None:
        """Handle error response."""
        try:
            if "application/json" in response.headers.get("content-type", ""):
                error_data = response.json()
            else:
                error_data = {"error": response.text or f"HTTP {response.status_code}"}
        except json.JSONDecodeError:
            error_data = {"error": f"HTTP {response.status_code}"}

        # Add rate limit info to details if available
        if rate_limit_info:
            error_data["details"] = error_data.get("details", {})
            error_data["details"]["rate_limit_info"] = rate_limit_info

        # Create appropriate error
        error = create_error_from_response(response.status_code, error_data)
        raise error

    def _extract_rate_limit_info(self, response: httpx.Response) -> Optional[RateLimitInfo]:
        """Extract rate limit information from response headers."""
        limit_header = response.headers.get("x-ratelimit-limit")
        remaining_header = response.headers.get("x-ratelimit-remaining")
        reset_header = response.headers.get("x-ratelimit-reset")
        retry_after_header = response.headers.get("retry-after")

        if limit_header and remaining_header and reset_header:
            try:
                return RateLimitInfo(
                    limit=int(limit_header),
                    remaining=int(remaining_header),
                    reset=int(reset_header),
                    retry_after=int(retry_after_header) if retry_after_header else None,
                )
            except ValueError:
                pass

        return None

    def _should_retry(self, response: httpx.Response, attempt: int) -> bool:
        """Check if request should be retried."""
        if attempt >= self.retry_config.max_retries:
            return False

        # Retry on specific status codes
        if response.status_code in self.retry_config.status_forcelist:
            return True

        return False

    def _calculate_backoff_delay(self, attempt: int, rate_limit_info: Optional[RateLimitInfo] = None) -> float:
        """Calculate backoff delay for retry."""
        if rate_limit_info and rate_limit_info.retry_after:
            return rate_limit_info.retry_after

        # Exponential backoff
        delay = self.retry_config.backoff_factor * (2 ** attempt)
        return min(delay, 60.0)  # Max 60 seconds

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None,
    ) -> Any:
        """Make HTTP request with retries."""
        url = self._build_url(path)
        headers = self._build_headers(config)

        # Handle timeout override
        timeout = config.timeout if config and config.timeout else self.timeout

        # Prepare request data
        json_data = data if data else None
        query_params = params if params else None

        if self.debug:
            print(f"[AuraOne SDK] {method.upper()} {url}")
            if json_data:
                print(f"[AuraOne SDK] Request data: {json_data}")

        last_response = None
        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=query_params,
                    timeout=timeout,
                )

                last_response = response

                # Check if we should retry
                if not response.is_success and self._should_retry(response, attempt):
                    rate_limit_info = self._extract_rate_limit_info(response)
                    delay = self._calculate_backoff_delay(attempt, rate_limit_info)

                    if self.debug:
                        print(f"[AuraOne SDK] Retrying request in {delay:.2f}s (attempt {attempt + 1}/{self.retry_config.max_retries})")

                    time.sleep(delay)
                    continue

                # Process successful response or final error
                return self._handle_response(response)

            except httpx.TimeoutException:
                last_exception = TimeoutError("Request timeout", details={"timeout": timeout})
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    time.sleep(delay)
                    continue

            except httpx.NetworkError as e:
                last_exception = NetworkError(f"Network error: {e}")
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    time.sleep(delay)
                    continue

            except AuraOneError:
                raise

            except Exception as e:
                last_exception = AuraOneError(f"Request failed: {e}")
                break

        # Raise the last error
        if last_exception:
            raise last_exception
        elif last_response:
            return self._handle_response(last_response)
        else:
            raise AuraOneError("Request failed with no response")

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        """Make GET request."""
        return self._make_request("GET", path, params=params, config=config)

    def post(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        """Make POST request."""
        return self._make_request("POST", path, data=data, config=config)

    def put(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        """Make PUT request."""
        return self._make_request("PUT", path, data=data, config=config)

    def delete(self, path: str, config: Optional[RequestConfig] = None) -> Any:
        """Make DELETE request."""
        return self._make_request("DELETE", path, config=config)

    def patch(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        """Make PATCH request."""
        return self._make_request("PATCH", path, data=data, config=config)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


def build_query_params(params: Dict[str, Any]) -> str:
    """Build query string from parameters.

    Args:
        params: Query parameters

    Returns:
        URL-encoded query string
    """
    # Filter out None values
    filtered_params = {k: v for k, v in params.items() if v is not None}

    if not filtered_params:
        return ""

    return "?" + urlencode(filtered_params, doseq=True)


__all__ = [
    "HttpClient",
    "AsyncHttpClient",
    "HttpClientProtocol",
    "build_query_params",
]
