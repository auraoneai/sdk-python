"""GraphQL client utilities for the AuraOne SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .exceptions import AuraOneError
from .types import RequestConfig
from .utils import HttpClient, AsyncHttpClient


class GraphQLExecutionError(AuraOneError):
    """Raised when a GraphQL operation returns errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="GRAPHQL_ERROR", details=details, status_code=400)


class GraphQLClient:
    """Lightweight GraphQL client that reuses the core HTTP stack."""

    def __init__(
        self,
        http_client: HttpClient,
        endpoint: str = "/graphql",
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._http = http_client
        self._endpoint = endpoint
        self._default_headers = default_headers or {}

    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL operation and return the `data` portion."""
        config = self._build_config(headers)
        response = self._http.post(
            self._endpoint,
            data={
                "query": query,
                "variables": variables,
                "operationName": operation_name,
            },
            config=config,
        )
        return self._parse_response(response)

    def _build_config(self, headers: Optional[Dict[str, str]]) -> Optional[RequestConfig]:
        merged_headers = {**self._default_headers}
        if headers:
            merged_headers.update(headers)
        if not merged_headers:
            return None
        return RequestConfig(headers=merged_headers)

    def _parse_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        errors = payload.get("errors")
        if errors:
            first = errors[0] if isinstance(errors, list) else errors
            message = first.get("message") if isinstance(first, dict) else str(first)
            raise GraphQLExecutionError(message or "GraphQL execution failed", details=first)

        data = payload.get("data")
        if data is None:
            raise GraphQLExecutionError("GraphQL response missing 'data' field", details=payload)
        return data


class AsyncGraphQLClient:
    """Async companion to :class:`GraphQLClient`."""

    def __init__(
        self,
        http_client: AsyncHttpClient,
        endpoint: str = "/graphql",
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._http = http_client
        self._endpoint = endpoint
        self._default_headers = default_headers or {}

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL request asynchronously."""
        config = self._build_config(headers)
        response = await self._http.post(
            self._endpoint,
            data={
                "query": query,
                "variables": variables,
                "operationName": operation_name,
            },
            config=config,
        )
        return self._parse_response(response)

    def _build_config(self, headers: Optional[Dict[str, str]]) -> Optional[RequestConfig]:
        merged_headers = {**self._default_headers}
        if headers:
            merged_headers.update(headers)
        if not merged_headers:
            return None
        return RequestConfig(headers=merged_headers)

    def _parse_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        errors = payload.get("errors")
        if errors:
            first = errors[0] if isinstance(errors, list) else errors
            message = first.get("message") if isinstance(first, dict) else str(first)
            raise GraphQLExecutionError(message or "GraphQL execution failed", details=first)

        data = payload.get("data")
        if data is None:
            raise GraphQLExecutionError("GraphQL response missing 'data' field", details=payload)
        return data


__all__ = ["GraphQLClient", "AsyncGraphQLClient", "GraphQLExecutionError"]
