"""Attention evidence service for AuraOne SDK.

Wraps ``GET|POST /api/v1/algorithms/attention`` — the durable attention
evidence surface (secondary-dashboards readmission P1-01). Tenants push
captures recorded against their own runs via :meth:`ingest_evidence`;
:meth:`get_evidence` reads back only the resolved organization's rows.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


def _evidence_params(
    org_id: Optional[str],
    model_id: Optional[str],
    run_id: Optional[str],
    limit: Optional[int],
) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if org_id:
        params["orgId"] = org_id
    if model_id:
        params["modelId"] = model_id
    if run_id:
        params["runId"] = run_id
    if limit is not None:
        params["limit"] = limit
    return params or None


class AttentionService:
    """Synchronous attention evidence service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def get_evidence(
        self,
        org_id: Optional[str] = None,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/algorithms/attention — recorded heads/patterns/flow.

        ``status`` in the response is ``"empty"`` when the organization has
        not ingested any evidence yet.
        """
        return self.http_client.get(
            "/api/v1/algorithms/attention",
            params=_evidence_params(org_id, model_id, run_id, limit),
            config=request_config,
        )

    def ingest_evidence(
        self,
        records: List[Dict[str, Any]],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/algorithms/attention — push a batch of captures.

        Max 500 records and a 1 MiB payload per call; split larger captures.
        """
        return self.http_client.post(
            "/api/v1/algorithms/attention",
            data={"records": records},
            config=request_config,
        )


class AsyncAttentionService:
    """Asynchronous attention evidence service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def get_evidence(
        self,
        org_id: Optional[str] = None,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get(
            "/api/v1/algorithms/attention",
            params=_evidence_params(org_id, model_id, run_id, limit),
            config=request_config,
        )

    async def ingest_evidence(
        self,
        records: List[Dict[str, Any]],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/v1/algorithms/attention",
            data={"records": records},
            config=request_config,
        )
