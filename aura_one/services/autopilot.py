"""Autopilot service for AuraOne SDK.

Wraps ``/api/v1/autopilot/...`` — natural-language workflow drafting, explicit
approval gates, one-click deploy, and durable run inspection
(secondary-dashboards readmission P0-06..P0-08).

The approve/deploy/execute/revise routes require an idempotency key; the SDK
sends ``X-Idempotency-Key`` and auto-generates a UUID4 when omitted.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from urllib.parse import quote

from ..types import RequestConfig
from ..utils import HttpClientProtocol


def _id(value: str) -> str:
    return quote(value, safe="")


def _mutation_config(
    request_config: Optional[RequestConfig],
    idempotency_key: Optional[str],
) -> RequestConfig:
    headers = dict(request_config.headers) if request_config and request_config.headers else {}
    headers.setdefault("X-Idempotency-Key", idempotency_key or str(uuid.uuid4()))
    return RequestConfig(
        timeout=request_config.timeout if request_config else None,
        max_retries=request_config.max_retries if request_config else None,
        headers=headers,
    )


class AutopilotService:
    """Synchronous autopilot service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def list(
        self,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/autopilot — workflows + recent runs for the org."""
        params = {"orgId": org_id} if org_id else None
        return self.http_client.get("/api/v1/autopilot", params=params, config=request_config)

    def get_metrics(
        self,
        org_id: Optional[str] = None,
        days: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/autopilot/metrics?days= — adoption metrics (1-365d)."""
        params: Dict[str, Any] = {}
        if org_id:
            params["orgId"] = org_id
        if days is not None:
            params["days"] = days
        return self.http_client.get(
            "/api/v1/autopilot/metrics",
            params=params or None,
            config=request_config,
        )

    def generate(
        self,
        description: str,
        seed: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/autopilot/generate — draft a workflow plan from natural
        language and freeze the canonical plan on the new workflow row (201)."""
        payload: Dict[str, Any] = {"description": description}
        if seed is not None:
            payload["seed"] = seed
        return self.http_client.post(
            "/api/v1/autopilot/generate",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def approve(
        self,
        workflow_id: str,
        rationale: str,
        edited_plan: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/autopilot/{workflow_id}/approve — freeze the draft plan
        into an immutable attested version."""
        payload: Dict[str, Any] = {"rationale": rationale}
        if edited_plan is not None:
            payload["editedPlan"] = edited_plan
        return self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/approve",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def deploy(
        self,
        workflow_id: str,
        modifications: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/autopilot/{workflow_id}/deploy — deploy the approved
        plan, optionally with bounded modifications."""
        payload: Dict[str, Any] = {}
        if modifications is not None:
            payload["modifications"] = modifications
        return self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/deploy",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def execute(
        self,
        workflow_id: str,
        seed: Optional[str] = None,
        sync: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/autopilot/{workflow_id}/execute — queue a durable run
        (202) or run inline with ``sync=True``."""
        payload: Dict[str, Any] = {}
        if seed is not None:
            payload["seed"] = seed
        if sync is not None:
            payload["sync"] = sync
        return self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/execute",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def revise(
        self,
        workflow_id: str,
        plan: Dict[str, Any],
        rationale: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/autopilot/{workflow_id}/revise — replace the draft plan."""
        payload: Dict[str, Any] = {"plan": plan}
        if rationale is not None:
            payload["rationale"] = rationale
        return self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/revise",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def get_run(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/autopilot/runs/{run_id} — run detail + ordered steps."""
        return self.http_client.get(f"/api/v1/autopilot/runs/{_id(run_id)}", config=request_config)

    def control_run(
        self,
        run_id: str,
        action: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/autopilot/runs/{run_id} — ``cancel`` or ``resume``."""
        if action not in {"cancel", "resume"}:
            raise ValueError(f"Unsupported autopilot run action: {action!r}")
        return self.http_client.post(
            f"/api/v1/autopilot/runs/{_id(run_id)}",
            data={"action": action},
            config=_mutation_config(request_config, idempotency_key),
        )

    def cancel_run(self, run_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.control_run(run_id, "cancel", idempotency_key, request_config)

    def resume_run(self, run_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.control_run(run_id, "resume", idempotency_key, request_config)

    def get_run_audit(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/autopilot/runs/{run_id}/audit — full audit trail."""
        return self.http_client.get(
            f"/api/v1/autopilot/runs/{_id(run_id)}/audit",
            config=request_config,
        )

    def get_run_events(
        self,
        run_id: str,
        after: Optional[int] = None,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/autopilot/runs/{run_id}/events — ordered per-step events.
        Pass the previous response's ``cursor`` as ``after`` to poll."""
        params: Dict[str, Any] = {}
        if after is not None:
            params["after"] = after
        if limit is not None:
            params["limit"] = limit
        return self.http_client.get(
            f"/api/v1/autopilot/runs/{_id(run_id)}/events",
            params=params or None,
            config=request_config,
        )


class AsyncAutopilotService:
    """Asynchronous autopilot service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def list(
        self,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params = {"orgId": org_id} if org_id else None
        return await self.http_client.get("/api/v1/autopilot", params=params, config=request_config)

    async def get_metrics(
        self,
        org_id: Optional[str] = None,
        days: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if org_id:
            params["orgId"] = org_id
        if days is not None:
            params["days"] = days
        return await self.http_client.get(
            "/api/v1/autopilot/metrics",
            params=params or None,
            config=request_config,
        )

    async def generate(
        self,
        description: str,
        seed: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"description": description}
        if seed is not None:
            payload["seed"] = seed
        return await self.http_client.post(
            "/api/v1/autopilot/generate",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def approve(
        self,
        workflow_id: str,
        rationale: str,
        edited_plan: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"rationale": rationale}
        if edited_plan is not None:
            payload["editedPlan"] = edited_plan
        return await self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/approve",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def deploy(
        self,
        workflow_id: str,
        modifications: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if modifications is not None:
            payload["modifications"] = modifications
        return await self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/deploy",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def execute(
        self,
        workflow_id: str,
        seed: Optional[str] = None,
        sync: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if seed is not None:
            payload["seed"] = seed
        if sync is not None:
            payload["sync"] = sync
        return await self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/execute",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def revise(
        self,
        workflow_id: str,
        plan: Dict[str, Any],
        rationale: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"plan": plan}
        if rationale is not None:
            payload["rationale"] = rationale
        return await self.http_client.post(
            f"/api/v1/autopilot/{_id(workflow_id)}/revise",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def get_run(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(f"/api/v1/autopilot/runs/{_id(run_id)}", config=request_config)

    async def control_run(
        self,
        run_id: str,
        action: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        if action not in {"cancel", "resume"}:
            raise ValueError(f"Unsupported autopilot run action: {action!r}")
        return await self.http_client.post(
            f"/api/v1/autopilot/runs/{_id(run_id)}",
            data={"action": action},
            config=_mutation_config(request_config, idempotency_key),
        )

    async def cancel_run(self, run_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.control_run(run_id, "cancel", idempotency_key, request_config)

    async def resume_run(self, run_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.control_run(run_id, "resume", idempotency_key, request_config)

    async def get_run_audit(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/v1/autopilot/runs/{_id(run_id)}/audit",
            config=request_config,
        )

    async def get_run_events(
        self,
        run_id: str,
        after: Optional[int] = None,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if after is not None:
            params["after"] = after
        if limit is not None:
            params["limit"] = limit
        return await self.http_client.get(
            f"/api/v1/autopilot/runs/{_id(run_id)}/events",
            params=params or None,
            config=request_config,
        )
