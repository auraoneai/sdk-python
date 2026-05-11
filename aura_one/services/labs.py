"""Labs service for AuraOne SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


class LabsService:
    """Synchronous labs service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def list_bundles(self, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.get("/v1/labs/bundles", config=request_config)

    def create_bundle(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post("/v1/labs/bundles", data=payload, config=request_config)

    def get_bundle(self, bundle_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.get(f"/v1/labs/bundles/{bundle_id}", config=request_config)

    def update_bundle(
        self,
        bundle_id: str,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.patch(
            f"/v1/labs/bundles/{bundle_id}",
            data=payload,
            config=request_config,
        )

    def provision_bundle(self, bundle_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.post(
            f"/v1/labs/bundles/{bundle_id}/provision",
            config=request_config,
        )


class AsyncLabsService:
    """Asynchronous labs service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def list_bundles(self, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get("/v1/labs/bundles", config=request_config)

    async def create_bundle(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post("/v1/labs/bundles", data=payload, config=request_config)

    async def get_bundle(self, bundle_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(f"/v1/labs/bundles/{bundle_id}", config=request_config)

    async def update_bundle(
        self,
        bundle_id: str,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.patch(
            f"/v1/labs/bundles/{bundle_id}",
            data=payload,
            config=request_config,
        )

    async def provision_bundle(self, bundle_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/v1/labs/bundles/{bundle_id}/provision",
            config=request_config,
        )
