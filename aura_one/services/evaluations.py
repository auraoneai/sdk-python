"""Evaluations service for AuraOne SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


class EvaluationsService:
    """Synchronous evaluations service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def create(
        self,
        template_id: str,
        agent_bundle_url: str,
        reward_spec_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "template_id": template_id,
            "agent_bundle_url": agent_bundle_url,
        }
        if reward_spec_id:
            payload["reward_spec_id"] = reward_spec_id
        if config:
            payload["config"] = config
        return self.http_client.post("/api/v1/evaluations", data=payload, config=request_config)

    def get(self, evaluation_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.get(f"/api/v1/evaluations/{evaluation_id}", config=request_config)

    def cancel(self, evaluation_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.post(
            f"/api/v1/evaluations/{evaluation_id}/cancel",
            config=request_config,
        )

    def list_templates(
        self,
        domain: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if domain:
            params["domain"] = domain
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        response = self.http_client.get("/api/v1/templates", params=params or None, config=request_config)
        if isinstance(response, list):
            return response
        return response.get("templates") or response.get("data") or []


class AsyncEvaluationsService:
    """Asynchronous evaluations service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def create(
        self,
        template_id: str,
        agent_bundle_url: str,
        reward_spec_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "template_id": template_id,
            "agent_bundle_url": agent_bundle_url,
        }
        if reward_spec_id:
            payload["reward_spec_id"] = reward_spec_id
        if config:
            payload["config"] = config
        return await self.http_client.post("/api/v1/evaluations", data=payload, config=request_config)

    async def get(self, evaluation_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(f"/api/v1/evaluations/{evaluation_id}", config=request_config)

    async def cancel(self, evaluation_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/v1/evaluations/{evaluation_id}/cancel",
            config=request_config,
        )

    async def list_templates(
        self,
        domain: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if domain:
            params["domain"] = domain
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        response = await self.http_client.get("/api/v1/templates", params=params or None, config=request_config)
        if isinstance(response, list):
            return response
        return response.get("templates") or response.get("data") or []

