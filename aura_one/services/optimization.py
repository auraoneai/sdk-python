"""Optimization service for AuraOne SDK.

Wraps ``/api/v1/optimization/...`` — the optimization job lifecycle plus the
readmission P0-02 trial-data routes (``history``, ``suggest``,
``visualization``, ``visualization/surface``, ``metrics``) and per-user
wizard ``drafts``.

Every call is org-scoped server-side: the organization comes from the
credential, and a configured client ``organization_id`` is asserted as
``?orgId=``.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from urllib.parse import quote

from ..types import RequestConfig
from ..utils import HttpClientProtocol

_SAFE: str = ""


def _id(value: str) -> str:
    return quote(value, safe=_SAFE)


def _mutation_config(
    request_config: Optional[RequestConfig],
    idempotency_key: Optional[str],
) -> RequestConfig:
    """Merge an ``X-Idempotency-Key`` header into the request config.

    The server's idempotency middleware accepts both header spellings; the
    Python SDK convention is ``X-Idempotency-Key``. A UUID4 is generated when
    the caller does not supply one.
    """
    headers = dict(request_config.headers) if request_config and request_config.headers else {}
    headers.setdefault("X-Idempotency-Key", idempotency_key or str(uuid.uuid4()))
    return RequestConfig(
        timeout=request_config.timeout if request_config else None,
        max_retries=request_config.max_retries if request_config else None,
        headers=headers,
    )


class OptimizationService:
    """Synchronous optimization service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    # -- overview / jobs ---------------------------------------------------

    def get_summary(self, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/optimization — latest job + per-status counts."""
        return self.http_client.get("/api/v1/optimization", config=request_config)

    def list_jobs(
        self,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs — up to 100 most recent jobs."""
        params = {"orgId": org_id} if org_id else None
        return self.http_client.get("/api/v1/optimization/jobs", params=params, config=request_config)

    def create_job(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/optimization/jobs — create a job (idempotent)."""
        return self.http_client.post(
            "/api/v1/optimization/jobs",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def get_job(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs/{job_id}."""
        return self.http_client.get(f"/api/v1/optimization/jobs/{_id(job_id)}", config=request_config)

    def update_job(
        self,
        job_id: str,
        patch: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """PATCH /api/v1/optimization/jobs/{job_id} (idempotent)."""
        return self.http_client.patch(
            f"/api/v1/optimization/jobs/{_id(job_id)}",
            data=patch,
            config=_mutation_config(request_config, idempotency_key),
        )

    def delete_job(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """DELETE /api/v1/optimization/jobs/{job_id} — terminal-state jobs only."""
        return self.http_client.delete(f"/api/v1/optimization/jobs/{_id(job_id)}", config=request_config)

    def run_job_action(
        self,
        job_id: str,
        action: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/optimization/jobs/{job_id}/{action}.

        ``action`` is one of ``start``, ``pause``, ``resume``, ``stop``.
        Illegal transitions reject with 409 ``ILLEGAL_TRANSITION``.
        """
        if action not in {"start", "pause", "resume", "stop"}:
            raise ValueError(f"Unsupported optimization job action: {action!r}")
        return self.http_client.post(
            f"/api/v1/optimization/jobs/{_id(job_id)}/{action}",
            config=_mutation_config(request_config, idempotency_key),
        )

    def start_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.run_job_action(job_id, "start", idempotency_key, request_config)

    def pause_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.run_job_action(job_id, "pause", idempotency_key, request_config)

    def resume_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.run_job_action(job_id, "resume", idempotency_key, request_config)

    def stop_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.run_job_action(job_id, "stop", idempotency_key, request_config)

    # -- trial data (P0-02) ------------------------------------------------

    def get_job_history(
        self,
        job_id: str,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs/{job_id}/history — paginated trials."""
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        return self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/history",
            params=params or None,
            config=request_config,
        )

    def get_job_suggestion(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs/{job_id}/suggest — flat parameter set."""
        return self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/suggest",
            config=request_config,
        )

    def submit_job_suggestion(
        self,
        job_id: str,
        suggestion: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/optimization/jobs/{job_id}/suggest — record an
        operator-proposed parameter set."""
        return self.http_client.post(
            f"/api/v1/optimization/jobs/{_id(job_id)}/suggest",
            data=suggestion,
            config=request_config,
        )

    def get_job_visualization(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs/{job_id}/visualization — trial points."""
        return self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/visualization",
            config=request_config,
        )

    def get_job_surface(
        self,
        job_id: str,
        x: str,
        y: str,
        resolution: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs/{job_id}/visualization/surface?x=&y= —
        interpolated objective surface + contour lines."""
        params: Dict[str, Any] = {"x": x, "y": y}
        if resolution is not None:
            params["resolution"] = resolution
        return self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/visualization/surface",
            params=params,
            config=request_config,
        )

    def get_job_metrics(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/optimization/jobs/{job_id}/metrics."""
        return self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/metrics",
            config=request_config,
        )

    # -- drafts ------------------------------------------------------------

    def get_draft(
        self,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/optimization/drafts — the caller's wizard draft."""
        params = {"orgId": org_id} if org_id else None
        return self.http_client.get("/api/v1/optimization/drafts", params=params, config=request_config)

    def save_draft(
        self,
        draft: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/optimization/drafts — persist the caller's wizard draft."""
        return self.http_client.post("/api/v1/optimization/drafts", data=draft, config=request_config)


class AsyncOptimizationService:
    """Asynchronous optimization service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def get_summary(self, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get("/api/v1/optimization", config=request_config)

    async def list_jobs(
        self,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params = {"orgId": org_id} if org_id else None
        return await self.http_client.get("/api/v1/optimization/jobs", params=params, config=request_config)

    async def create_job(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/v1/optimization/jobs",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def get_job(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(f"/api/v1/optimization/jobs/{_id(job_id)}", config=request_config)

    async def update_job(
        self,
        job_id: str,
        patch: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.patch(
            f"/api/v1/optimization/jobs/{_id(job_id)}",
            data=patch,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def delete_job(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.delete(f"/api/v1/optimization/jobs/{_id(job_id)}", config=request_config)

    async def run_job_action(
        self,
        job_id: str,
        action: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        if action not in {"start", "pause", "resume", "stop"}:
            raise ValueError(f"Unsupported optimization job action: {action!r}")
        return await self.http_client.post(
            f"/api/v1/optimization/jobs/{_id(job_id)}/{action}",
            config=_mutation_config(request_config, idempotency_key),
        )

    async def start_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.run_job_action(job_id, "start", idempotency_key, request_config)

    async def pause_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.run_job_action(job_id, "pause", idempotency_key, request_config)

    async def resume_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.run_job_action(job_id, "resume", idempotency_key, request_config)

    async def stop_job(self, job_id: str, idempotency_key: Optional[str] = None, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.run_job_action(job_id, "stop", idempotency_key, request_config)

    async def get_job_history(
        self,
        job_id: str,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        return await self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/history",
            params=params or None,
            config=request_config,
        )

    async def get_job_suggestion(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/suggest",
            config=request_config,
        )

    async def submit_job_suggestion(
        self,
        job_id: str,
        suggestion: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/v1/optimization/jobs/{_id(job_id)}/suggest",
            data=suggestion,
            config=request_config,
        )

    async def get_job_visualization(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/visualization",
            config=request_config,
        )

    async def get_job_surface(
        self,
        job_id: str,
        x: str,
        y: str,
        resolution: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"x": x, "y": y}
        if resolution is not None:
            params["resolution"] = resolution
        return await self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/visualization/surface",
            params=params,
            config=request_config,
        )

    async def get_job_metrics(self, job_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/v1/optimization/jobs/{_id(job_id)}/metrics",
            config=request_config,
        )

    async def get_draft(
        self,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params = {"orgId": org_id} if org_id else None
        return await self.http_client.get("/api/v1/optimization/drafts", params=params, config=request_config)

    async def save_draft(
        self,
        draft: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post("/api/v1/optimization/drafts", data=draft, config=request_config)
