"""Visualization service for AuraOne SDK.

Wraps the visualization surface:

- ``/api/v1/visualization/dashboards/**`` — dashboard CRUD plus share /
  favorite / bookmark / view engagement.
- ``/api/v1/visualization/data`` — widget configuration reads and the
  structured query executor.
- ``/api/v1/visualization/export`` — synchronous dashboard/widget render.
- ``/api/visualization/exports/...`` — scheduled export configs, runs,
  history, and artifact download (secondary-dashboards readmission P1-06).
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


def _dashboard_list_params(options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    for key in ("limit", "offset", "search", "tags", "sortBy", "sortOrder", "view"):
        if options.get(key) is not None:
            params[key] = options[key]
    if options.get("org_id"):
        params["orgId"] = options["org_id"]
    if options.get("organization_id"):
        params["organizationId"] = options["organization_id"]
    if options.get("include_public") is not None:
        params["includePublic"] = "true" if options["include_public"] else "false"
    if options.get("include_analytics") is not None:
        params["includeAnalytics"] = "true" if options["include_analytics"] else "false"
    return params or None


class VisualizationService:
    """Synchronous visualization service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    # -- dashboards ---------------------------------------------------------

    def list_dashboards(
        self,
        org_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        search: Optional[str] = None,
        tags: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        include_public: Optional[bool] = None,
        view: Optional[str] = None,
        include_analytics: Optional[bool] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/visualization/dashboards — filtered, paginated list."""
        params = _dashboard_list_params(
            {
                "org_id": org_id,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
                "search": search,
                "tags": tags,
                "sortBy": sort_by,
                "sortOrder": sort_order,
                "include_public": include_public,
                "view": view,
                "include_analytics": include_analytics,
            }
        )
        return self.http_client.get(
            "/api/v1/visualization/dashboards",
            params=params,
            config=request_config,
        )

    def create_dashboard(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/visualization/dashboards — create (201)."""
        return self.http_client.post(
            "/api/v1/visualization/dashboards",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def get_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """GET /api/v1/visualization/dashboards/{dashboard_id} — with widgets."""
        return self.http_client.get(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}",
            config=request_config,
        )

    def update_dashboard(
        self,
        dashboard_id: str,
        patch: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """PUT /api/v1/visualization/dashboards/{dashboard_id}."""
        return self.http_client.put(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}",
            data=patch,
            config=_mutation_config(request_config, idempotency_key),
        )

    def delete_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """DELETE /api/v1/visualization/dashboards/{dashboard_id}."""
        return self.http_client.delete(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}",
            config=request_config,
        )

    def share_dashboard(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST .../share — mints a bearer-token share URL."""
        return self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/share",
            config=_mutation_config(request_config, idempotency_key),
        )

    def favorite_dashboard(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/favorite",
            config=_mutation_config(request_config, idempotency_key),
        )

    def unfavorite_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.delete(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/favorite",
            config=request_config,
        )

    def bookmark_dashboard(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/bookmark",
            config=_mutation_config(request_config, idempotency_key),
        )

    def unbookmark_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.delete(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/bookmark",
            config=request_config,
        )

    def record_dashboard_view(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST .../view — record a dashboard view."""
        return self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/view",
            config=_mutation_config(request_config, idempotency_key),
        )

    # -- widget data ----------------------------------------------------------

    def list_widgets(
        self,
        dashboard_id: Optional[str] = None,
        widget_id: Optional[str] = None,
        chart_type: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/visualization/data — widget records; pass ``widget_id``
        for a single widget."""
        params: Dict[str, Any] = {}
        if dashboard_id:
            params["dashboardId"] = dashboard_id
        if widget_id:
            params["widgetId"] = widget_id
        if chart_type:
            params["chartType"] = chart_type
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
        return self.http_client.get(
            "/api/v1/visualization/data",
            params=params or None,
            config=request_config,
        )

    def run_query(
        self,
        query: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/visualization/data — execute a structured query against
        an org-owned data source."""
        return self.http_client.post(
            "/api/v1/visualization/data",
            data=query,
            config=request_config,
        )

    def export(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/visualization/export — synchronous render of exactly
        one of ``dashboardId``/``widgetId`` into the requested format."""
        return self.http_client.post(
            "/api/v1/visualization/export",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    # -- scheduled exports (/api/visualization/exports) -----------------------

    def list_exports(
        self,
        org_id: Optional[str] = None,
        export_id: Optional[str] = None,
        format: Optional[str] = None,  # noqa: A002 - mirrors the API parameter
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/visualization/exports — list export configs; pass
        ``export_id`` for a single ``{data: ExportConfig}`` response."""
        params: Dict[str, Any] = {}
        if org_id:
            params["orgId"] = org_id
        if export_id:
            params["id"] = export_id
        if format:
            params["format"] = format
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if sort_by:
            params["sortBy"] = sort_by
        if sort_order:
            params["sortOrder"] = sort_order
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self.http_client.get(
            "/api/visualization/exports",
            params=params or None,
            config=request_config,
        )

    def create_export(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/visualization/exports — create a scheduled export config."""
        return self.http_client.post(
            "/api/visualization/exports",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    def update_export(
        self,
        export_id: str,
        patch: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """PATCH /api/visualization/exports?id={export_id} — update a config."""
        return self.http_client.patch(
            f"/api/visualization/exports?id={_id(export_id)}",
            data=patch,
            config=_mutation_config(request_config, idempotency_key),
        )

    def delete_export(self, export_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """DELETE /api/visualization/exports?id={export_id} — soft delete."""
        return self.http_client.delete(
            f"/api/visualization/exports?id={_id(export_id)}",
            config=request_config,
        )

    def run_export(
        self,
        export_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """POST /api/visualization/exports/{id}/run — enqueue a run (202)."""
        return self.http_client.post(
            f"/api/visualization/exports/{_id(export_id)}/run",
            data=overrides if overrides else None,
            config=_mutation_config(request_config, idempotency_key),
        )

    def get_export_history(
        self,
        export_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """GET /api/visualization/exports/{id}/history — paginated run history."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self.http_client.get(
            f"/api/visualization/exports/{_id(export_id)}/history",
            params=params or None,
            config=request_config,
        )

    def download_export(
        self,
        export_id: str,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """GET /api/visualization/exports/{id}/download — fetch a completed
        export artifact (binary body or redirect to a signed URL)."""
        params = {"orgId": org_id} if org_id else None
        return self.http_client.get(
            f"/api/visualization/exports/{_id(export_id)}/download",
            params=params,
            config=request_config,
        )


class AsyncVisualizationService:
    """Asynchronous visualization service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def list_dashboards(
        self,
        org_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        search: Optional[str] = None,
        tags: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        include_public: Optional[bool] = None,
        view: Optional[str] = None,
        include_analytics: Optional[bool] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params = _dashboard_list_params(
            {
                "org_id": org_id,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
                "search": search,
                "tags": tags,
                "sortBy": sort_by,
                "sortOrder": sort_order,
                "include_public": include_public,
                "view": view,
                "include_analytics": include_analytics,
            }
        )
        return await self.http_client.get(
            "/api/v1/visualization/dashboards",
            params=params,
            config=request_config,
        )

    async def create_dashboard(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/v1/visualization/dashboards",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def get_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}",
            config=request_config,
        )

    async def update_dashboard(
        self,
        dashboard_id: str,
        patch: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.put(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}",
            data=patch,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def delete_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.delete(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}",
            config=request_config,
        )

    async def share_dashboard(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/share",
            config=_mutation_config(request_config, idempotency_key),
        )

    async def favorite_dashboard(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/favorite",
            config=_mutation_config(request_config, idempotency_key),
        )

    async def unfavorite_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.delete(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/favorite",
            config=request_config,
        )

    async def bookmark_dashboard(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/bookmark",
            config=_mutation_config(request_config, idempotency_key),
        )

    async def unbookmark_dashboard(self, dashboard_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.delete(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/bookmark",
            config=request_config,
        )

    async def record_dashboard_view(
        self,
        dashboard_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/v1/visualization/dashboards/{_id(dashboard_id)}/view",
            config=_mutation_config(request_config, idempotency_key),
        )

    async def list_widgets(
        self,
        dashboard_id: Optional[str] = None,
        widget_id: Optional[str] = None,
        chart_type: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if dashboard_id:
            params["dashboardId"] = dashboard_id
        if widget_id:
            params["widgetId"] = widget_id
        if chart_type:
            params["chartType"] = chart_type
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
        return await self.http_client.get(
            "/api/v1/visualization/data",
            params=params or None,
            config=request_config,
        )

    async def run_query(
        self,
        query: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/v1/visualization/data",
            data=query,
            config=request_config,
        )

    async def export(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/v1/visualization/export",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def list_exports(
        self,
        org_id: Optional[str] = None,
        export_id: Optional[str] = None,
        format: Optional[str] = None,  # noqa: A002 - mirrors the API parameter
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if org_id:
            params["orgId"] = org_id
        if export_id:
            params["id"] = export_id
        if format:
            params["format"] = format
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if sort_by:
            params["sortBy"] = sort_by
        if sort_order:
            params["sortOrder"] = sort_order
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self.http_client.get(
            "/api/visualization/exports",
            params=params or None,
            config=request_config,
        )

    async def create_export(
        self,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/visualization/exports",
            data=payload,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def update_export(
        self,
        export_id: str,
        patch: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.patch(
            f"/api/visualization/exports?id={_id(export_id)}",
            data=patch,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def delete_export(self, export_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.delete(
            f"/api/visualization/exports?id={_id(export_id)}",
            config=request_config,
        )

    async def run_export(
        self,
        export_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            f"/api/visualization/exports/{_id(export_id)}/run",
            data=overrides if overrides else None,
            config=_mutation_config(request_config, idempotency_key),
        )

    async def get_export_history(
        self,
        export_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self.http_client.get(
            f"/api/visualization/exports/{_id(export_id)}/history",
            params=params or None,
            config=request_config,
        )

    async def download_export(
        self,
        export_id: str,
        org_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        params = {"orgId": org_id} if org_id else None
        return await self.http_client.get(
            f"/api/visualization/exports/{_id(export_id)}/download",
            params=params,
            config=request_config,
        )
