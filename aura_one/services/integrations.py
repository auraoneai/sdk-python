"""Integrations service for AuraOne SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


class IntegrationsService:
    """Synchronous integrations service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def get_health(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.get("/v1/integration/health", params=params, config=request_config)

    def run_health_test(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post("/v1/integration/health/test", data=payload, config=request_config)

    def list_registry(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.get("/v1/integration/registry", params=params, config=request_config)

    def register_integration(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post("/v1/integration/registry", data=payload, config=request_config)


class AsyncIntegrationsService:
    """Asynchronous integrations service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def get_health(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get("/v1/integration/health", params=params, config=request_config)

    async def run_health_test(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post("/v1/integration/health/test", data=payload, config=request_config)

    async def list_registry(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get("/v1/integration/registry", params=params, config=request_config)

    async def register_integration(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post("/v1/integration/registry", data=payload, config=request_config)
