import asyncio
import json
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx

from .auth import AuthProvider
from .exceptions import (
    AuraOneError,
    NetworkError,
    ResponseParsingError,
    TimeoutError,
    create_error_from_response,
)
from .types import RateLimitInfo, RequestConfig, RetryConfig
from .version import __version__


class AsyncHttpClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        debug: bool = False,
        auth_provider: Optional[AuthProvider] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug
        self.auth_provider = auth_provider

        self.default_headers = {
            "Content-Type": "application/json",
            "User-Agent": f"auraone-python-sdk/{__version__}",
        }

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

        self.retry_config = RetryConfig(
            max_retries=max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )

    def _build_url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _build_headers(self, config: Optional[RequestConfig] = None) -> Dict[str, str]:
        headers = self.default_headers.copy()

        if self.auth_provider:
            auth_headers = self.auth_provider.get_auth_headers()
            headers.update(auth_headers)

        if config and config.headers:
            headers.update(config.headers)

        return headers

    async def _handle_response(self, response: httpx.Response) -> Any:
        rate_limit_info = self._extract_rate_limit_info(response)

        if rate_limit_info and rate_limit_info.remaining == 0:
            if self.debug:
                print(f"[AuraOne SDK] Rate limit info: {rate_limit_info}")

        if not response.is_success:
            await self._handle_error_response(response, rate_limit_info)

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
            return response.content

    async def _handle_error_response(
        self,
        response: httpx.Response,
        rate_limit_info: Optional[RateLimitInfo] = None
    ) -> None:
        try:
            if "application/json" in response.headers.get("content-type", ""):
                error_data = response.json()
            else:
                error_data = {"error": response.text or f"HTTP {response.status_code}"}
        except json.JSONDecodeError:
            error_data = {"error": f"HTTP {response.status_code}"}

        if rate_limit_info:
            error_data["details"] = error_data.get("details", {})
            error_data["details"]["rate_limit_info"] = rate_limit_info

        error = create_error_from_response(response.status_code, error_data)
        raise error

    def _extract_rate_limit_info(self, response: httpx.Response) -> Optional[RateLimitInfo]:
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
        if attempt >= self.retry_config.max_retries:
            return False

        if response.status_code in self.retry_config.status_forcelist:
            return True

        return False

    def _calculate_backoff_delay(self, attempt: int, rate_limit_info: Optional[RateLimitInfo] = None) -> float:
        if rate_limit_info and rate_limit_info.retry_after:
            return rate_limit_info.retry_after

        delay = self.retry_config.backoff_factor * (2 ** attempt)
        return min(delay, 60.0)

    async def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None,
    ) -> Any:
        url = self._build_url(path)
        headers = self._build_headers(config)
        timeout = config.timeout if config and config.timeout else self.timeout
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
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=query_params,
                    timeout=timeout,
                )

                last_response = response

                if not response.is_success and self._should_retry(response, attempt):
                    rate_limit_info = self._extract_rate_limit_info(response)
                    delay = self._calculate_backoff_delay(attempt, rate_limit_info)

                    if self.debug:
                        print(f"[AuraOne SDK] Retrying request in {delay:.2f}s (attempt {attempt + 1}/{self.retry_config.max_retries})")

                    await asyncio.sleep(delay)
                    continue

                return await self._handle_response(response)

            except httpx.TimeoutException:
                last_exception = TimeoutError("Request timeout", details={"timeout": timeout})
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

            except httpx.NetworkError as e:
                last_exception = NetworkError(f"Network error: {e}")
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

            except AuraOneError:
                raise

            except Exception as e:
                last_exception = AuraOneError(f"Request failed: {e}")
                break

        if last_exception:
            raise last_exception
        elif last_response:
            return await self._handle_response(last_response)
        else:
            raise AuraOneError("Request failed with no response")

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        return await self._make_request("GET", path, params=params, config=config)

    async def post(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        return await self._make_request("POST", path, data=data, config=config)

    async def put(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        return await self._make_request("PUT", path, data=data, config=config)

    async def delete(self, path: str, config: Optional[RequestConfig] = None) -> Any:
        return await self._make_request("DELETE", path, config=config)

    async def patch(self, path: str, data: Optional[Dict[str, Any]] = None, config: Optional[RequestConfig] = None) -> Any:
        return await self._make_request("PATCH", path, data=data, config=config)

    async def close(self) -> None:
        await self.client.aclose()


__all__ = ["AsyncHttpClient"]
