"""GraphQL service for AuraOne Python SDK (`aura_one` and `aura`)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..exceptions import AuraOneError
from ..types import RequestConfig
try:
    from ..utils import AsyncHttpClient
except ImportError:
    from ..async_utils import AsyncHttpClient


GRAPHQL_PERSISTED_QUERIES: Dict[str, Dict[str, str]] = {
    "OptimizationJob": {
        "sha256Hash": "c2d6f57b508ee1e21e1f819a42f9a177d467b2d1f61ca4681b3b269a84f47291",
        "operationName": "OptimizationJob",
        "source": """query OptimizationJob($id: ID!) {
  job(id: $id) {
    id
    name
    strategy
    status
    progress
    bestScore
    organizationId
    userId
  }
}""",
    },
    "OptimizationJobs": {
        "sha256Hash": "5b1dc3104d637a1155593c1a9f14dc3969d85759f04e502503d5f7a3d88c5e7a",
        "operationName": "OptimizationJobs",
        "source": """query OptimizationJobs($limit: Int, $offset: Int) {
  jobs(limit: $limit, offset: $offset) {
    id
    name
    strategy
    status
    progress
    bestScore
    organizationId
    userId
  }
}""",
    },
    "OptimizationJobHistory": {
        "sha256Hash": "931f550bd9ea2c91ddefe76d44d69d425979a951b858ac03b51a4d74a13e0cb8",
        "operationName": "OptimizationJobHistory",
        "source": """query OptimizationJobHistory($id: ID!) {
  jobHistory(id: $id) {
    ts
    score
    parameters
  }
}""",
    },
    "OptimizationJobSurfaces": {
        "sha256Hash": "07a11763cb1542a68e8a1d39954652b43b3ea9640a05ebba8cdaf21897ced888",
        "operationName": "OptimizationJobSurfaces",
        "source": """query OptimizationJobSurfaces($id: ID!) {
  jobSurfaces(id: $id) {
    parameterX
    parameterY
    resolution
    data
  }
}""",
    },
}


class GraphQLExecutionError(AuraOneError):
    """Raised when a GraphQL operation returns errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        ext_code = None
        if errors and isinstance(errors[0], dict):
            ext = errors[0].get("extensions")
            if isinstance(ext, dict) and isinstance(ext.get("code"), str):
                ext_code = ext["code"]
        super().__init__(
            message,
            code=ext_code or "GRAPHQL_ERROR",
            details=details or (errors[0] if errors else None),
            status_code=400,
        )
        self.errors = errors or []


def _build_graphql_body(
    query: Optional[str],
    variables: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    persisted_query_hash: Optional[str] = None,
    include_query_with_hash: bool = True,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if query and (not persisted_query_hash or include_query_with_hash):
        body["query"] = query
    if variables is not None:
        body["variables"] = variables
    if operation_name is not None:
        body["operationName"] = operation_name
    if persisted_query_hash:
        body["extensions"] = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": persisted_query_hash,
            }
        }
    return body


def _parse_graphql_response(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "json") and callable(payload.json):
        if hasattr(payload, "raise_for_status") and callable(payload.raise_for_status):
            status_code = getattr(payload, "status_code", 200)
            if isinstance(status_code, int) and status_code >= 500:
                payload.raise_for_status()
        payload = payload.json()
    if not isinstance(payload, dict):
        raise GraphQLExecutionError(
            "Invalid GraphQL response payload",
            details={"payload": payload},
        )
    errors = payload.get("errors")
    if errors:
        error_list = errors if isinstance(errors, list) else [errors]
        first = error_list[0] if error_list else {}
        message = (
            first.get("message")
            if isinstance(first, dict)
            else str(first)
        )
        raise GraphQLExecutionError(
            message or "GraphQL execution failed",
            details=first if isinstance(first, dict) else {"error": first},
            errors=[e for e in error_list if isinstance(e, dict)],
        )
    data = payload.get("data")
    if data is None:
        raise GraphQLExecutionError(
            "GraphQL response missing 'data' field",
            details=payload,
        )
    return data


class GraphQLService:
    """Synchronous GraphQL service targeting `/api/graphql`."""

    def __init__(
        self,
        http_client: Any,
        endpoint: str = "/api/graphql",
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.http_client = http_client
        self._http = http_client
        self.endpoint = endpoint
        self._endpoint = endpoint
        self._default_headers = dict(default_headers or {})

    def _build_config(
        self,
        headers: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[RequestConfig]:
        merged = dict(self._default_headers)
        if headers:
            merged.update(headers)
        if idempotency_key:
            merged["X-Idempotency-Key"] = idempotency_key
        if not merged:
            return None
        return RequestConfig(headers=merged)

    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        persisted_query_hash: Optional[str] = None,
        include_query_with_hash: bool = True,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation against `/api/graphql`."""
        body = _build_graphql_body(
            query,
            variables=variables,
            operation_name=operation_name,
            persisted_query_hash=persisted_query_hash,
            include_query_with_hash=include_query_with_hash,
        )
        if hasattr(self._http, "_request") and callable(self._http._request):
            merged_headers = dict(self._default_headers)
            if headers:
                merged_headers.update(headers)
            if idempotency_key:
                merged_headers["X-Idempotency-Key"] = idempotency_key
            response = self._http._request(
                "POST",
                self._endpoint,
                json=body,
                headers=merged_headers or None,
            )
            return _parse_graphql_response(response)

        config = self._build_config(headers, idempotency_key=idempotency_key)
        response = self._http.post(self._endpoint, data=body, config=config)
        return _parse_graphql_response(response)

    def query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        persisted_query_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.execute(
            query,
            variables=variables,
            operation_name=operation_name,
            headers=headers,
            persisted_query_hash=persisted_query_hash,
        )

    def mutate(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        persisted_query_hash: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.execute(
            mutation,
            variables=variables,
            operation_name=operation_name,
            headers=headers,
            persisted_query_hash=persisted_query_hash,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )

    def get_optimization_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        entry = GRAPHQL_PERSISTED_QUERIES["OptimizationJob"]
        data = self.query(
            entry["source"],
            variables={"id": job_id},
            operation_name=entry["operationName"],
            persisted_query_hash=entry["sha256Hash"],
        )
        return data.get("job")

    def list_optimization_jobs(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        entry = GRAPHQL_PERSISTED_QUERIES["OptimizationJobs"]
        variables: Dict[str, Any] = {}
        if limit is not None:
            variables["limit"] = limit
        if offset is not None:
            variables["offset"] = offset
        data = self.query(
            entry["source"],
            variables=variables or None,
            operation_name=entry["operationName"],
            persisted_query_hash=entry["sha256Hash"],
        )
        return list(data.get("jobs") or [])


class AsyncGraphQLService:
    """Asynchronous GraphQL service targeting `/api/graphql`."""

    def __init__(
        self,
        http_client: AsyncHttpClient,
        endpoint: str = "/api/graphql",
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.http_client = http_client
        self._http = http_client
        self.endpoint = endpoint
        self._endpoint = endpoint
        self._default_headers = dict(default_headers or {})

    def _build_config(
        self,
        headers: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[RequestConfig]:
        merged = dict(self._default_headers)
        if headers:
            merged.update(headers)
        if idempotency_key:
            merged["X-Idempotency-Key"] = idempotency_key
        if not merged:
            return None
        return RequestConfig(headers=merged)

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        persisted_query_hash: Optional[str] = None,
        include_query_with_hash: bool = True,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = _build_graphql_body(
            query,
            variables=variables,
            operation_name=operation_name,
            persisted_query_hash=persisted_query_hash,
            include_query_with_hash=include_query_with_hash,
        )
        config = self._build_config(headers, idempotency_key=idempotency_key)
        response = await self._http.post(self._endpoint, data=body, config=config)
        return _parse_graphql_response(response)

    async def query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        persisted_query_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.execute(
            query,
            variables=variables,
            operation_name=operation_name,
            headers=headers,
            persisted_query_hash=persisted_query_hash,
        )

    async def mutate(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        persisted_query_hash: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.execute(
            mutation,
            variables=variables,
            operation_name=operation_name,
            headers=headers,
            persisted_query_hash=persisted_query_hash,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )


GraphQLClient = GraphQLService
AsyncGraphQLClient = AsyncGraphQLService

__all__ = [
    "GRAPHQL_PERSISTED_QUERIES",
    "GraphQLService",
    "AsyncGraphQLService",
    "GraphQLClient",
    "AsyncGraphQLClient",
    "GraphQLExecutionError",
]
