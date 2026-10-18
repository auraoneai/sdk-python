"""Capacity utilization service for AuraOne SDK.

Wraps ``GET /api/v1/capacity/utilization`` — the organization-scoped
usage/capacity series rendered on the capacity dashboard
(secondary-dashboards readmission P1-09).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


def _params(org_id: Optional[str], range_: Optional[str]) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if org_id:
        params["orgId"] = org_id
    if range_:
        params["range"] = range_
    return params or None


class CapacityService:
    """Synchronous capacity utilization service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def get_utilization(
        self,
        org_id: Optional[str] = None,
        range: Optional[str] = None,  # noqa: A002 - mirrors the API parameter
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/capacity/utilization — credits/sessions/gpu/storage
        utilization rows for the resolved organization over ``range``
        (``24h|7d|30d|90d`` or ``week|month|quarter|year``; default ``7d``).
        """
        return self.http_client.get(
            "/api/v1/capacity/utilization",
            params=_params(org_id, range),
            config=request_config,
        )


class AsyncCapacityService:
    """Asynchronous capacity utilization service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def get_utilization(
        self,
        org_id: Optional[str] = None,
        range: Optional[str] = None,  # noqa: A002 - mirrors the API parameter
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get(
            "/api/v1/capacity/utilization",
            params=_params(org_id, range),
            config=request_config,
        )
