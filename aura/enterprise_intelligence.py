"""Customer-facing Enterprise Intelligence (EI) API surface.

Mirrors ``sdks/typescript/src/services/EnterpriseIntelligenceService.ts``
and the "Enterprise Intelligence" section of
``docs/api/public-api-contract.md``. Wraps ``AuraClient._request`` so calls
share the client's auth headers (``X-API-Key`` for ``ak_`` keys), ``?orgId=``
assertion, and retry plumbing.

Scope rules: every GET except ``get_health`` requires the
``enterprise-intelligence.read`` scope; ``create_run`` and
``get_run_inputs`` require ``enterprise-intelligence.write``. ``get_health``
is unauthenticated. The organization is derived from the API key record
server-side.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .client import AuraClient


class EnterpriseIntelligenceService:
    """Synchronous client for the documented EI routes.

    Every method returns the decoded response envelope (``data``, plus
    ``meta``/``permissions``/``links`` where the route emits them).
    """

    def __init__(self, client: "AuraClient"):
        self._client = client

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        r = self._client._request("GET", path, params=params or None)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _queue_params(
        q: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if q:
            params["q"] = q
        if status:
            params["f.status"] = status
        return params

    # ---- Workflows (read) ----

    def list_workflows(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/workflows (read scope)."""
        return self._get(
            "/api/v1/enterprise-intelligence/workflows",
            params=self._queue_params(q, status),
        )

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/workflows/{workflowId} (read scope)."""
        return self._get(f"/api/v1/enterprise-intelligence/workflows/{workflow_id}")

    # ---- Runs (create/read) ----

    def list_runs(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/runs (read scope)."""
        return self._get(
            "/api/v1/enterprise-intelligence/runs",
            params=self._queue_params(q, status),
        )

    def create_run(
        self,
        *,
        workflow_version_id: str,
        input_content_id: str,
        environment_version: str,
        deadline_at: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/enterprise-intelligence/runs (write scope).

        The strict body is ``{workflowVersionId, inputContentId,
        environmentVersion, deadlineAt?}``; the required ``idempotency-key``
        header (8–255 chars) is auto-generated when not supplied.
        """
        body: Dict[str, Any] = {
            "workflowVersionId": workflow_version_id,
            "inputContentId": input_content_id,
            "environmentVersion": environment_version,
        }
        if deadline_at is not None:
            body["deadlineAt"] = deadline_at
        r = self._client._request(
            "POST",
            "/api/v1/enterprise-intelligence/runs",
            json=body,
            headers={"idempotency-key": idempotency_key or str(uuid.uuid4())},
        )
        r.raise_for_status()
        return r.json()

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/runs/{runId} (read scope)."""
        return self._get(f"/api/v1/enterprise-intelligence/runs/{run_id}")

    def get_run_output(self, run_id: str) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/runs/{runId}/output (read scope)."""
        return self._get(f"/api/v1/enterprise-intelligence/runs/{run_id}/output")

    def get_run_trace(self, run_id: str) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/runs/{runId}/trace (read scope)."""
        return self._get(f"/api/v1/enterprise-intelligence/runs/{run_id}/trace")

    def get_run_delivery(self, run_id: str) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/runs/{runId}/delivery (read scope)."""
        return self._get(f"/api/v1/enterprise-intelligence/runs/{run_id}/delivery")

    # ---- Run inputs (write scope) ----

    def get_run_inputs(self, q: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/run-inputs (write scope)."""
        return self._get(
            "/api/v1/enterprise-intelligence/run-inputs",
            params={"q": q} if q else None,
        )

    # ---- Deliveries (read) ----

    def list_deliveries(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/deliveries (read scope)."""
        return self._get(
            "/api/v1/enterprise-intelligence/deliveries",
            params=self._queue_params(q, status),
        )

    def get_delivery(self, delivery_id: str) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/deliveries/{deliveryId} (read scope)."""
        return self._get(f"/api/v1/enterprise-intelligence/deliveries/{delivery_id}")

    # ---- Connector receipts (read) ----

    def list_connector_receipts(
        self,
        connector_id: str,
        workflow_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/connectors/{connectorId}/receipts (read scope)."""
        params = {
            k: v
            for k, v in {"workflowId": workflow_id, "runId": run_id}.items()
            if v
        }
        return self._get(
            f"/api/v1/enterprise-intelligence/connectors/{connector_id}/receipts",
            params=params or None,
        )

    def get_connector_receipt(
        self,
        connector_id: str,
        receipt_id: str,
        workflow_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/connectors/{connectorId}/receipts/{receiptId} (read scope)."""
        params = {
            k: v
            for k, v in {"workflowId": workflow_id, "runId": run_id}.items()
            if v
        }
        return self._get(
            f"/api/v1/enterprise-intelligence/connectors/{connector_id}/receipts/{receipt_id}",
            params=params or None,
        )

    # ---- Health (unauthenticated) ----

    def get_health(self) -> Dict[str, Any]:
        """GET /api/v1/enterprise-intelligence/health (unauthenticated).

        The platform returns 503 with the same body shape when ``status`` is
        ``UNAVAILABLE``; that surfaces as ``httpx.HTTPStatusError``.
        """
        return self._get("/api/v1/enterprise-intelligence/health")
