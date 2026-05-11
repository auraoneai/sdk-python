"""Governance service for AuraOne SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


class GovernanceService:
    """Synchronous governance/compliance service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def list_frameworks(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.get("/v1/compliance/frameworks", params=params, config=request_config)

    def create_framework(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post("/v1/compliance/frameworks", data=payload, config=request_config)

    def list_evidence(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.get("/v1/compliance/evidence", params=params, config=request_config)

    def append_evidence(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post("/v1/compliance/evidence", data=payload, config=request_config)


class AsyncGovernanceService:
    """Asynchronous governance/compliance service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def list_frameworks(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get("/v1/compliance/frameworks", params=params, config=request_config)

    async def create_framework(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post("/v1/compliance/frameworks", data=payload, config=request_config)

    async def list_evidence(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get("/v1/compliance/evidence", params=params, config=request_config)

    async def append_evidence(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post("/v1/compliance/evidence", data=payload, config=request_config)
