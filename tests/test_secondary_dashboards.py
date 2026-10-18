"""P2-04 (secondary-dashboards readmission): transport-path coverage for the
new public services — attention, optimization, autopilot, visualization,
capacity. A fake HTTP client records (method, path, kwargs) calls so tests
assert the exact platform routes each SDK method targets.
"""

import uuid

from aura_one.services import (
    AsyncAttentionService,
    AsyncAutopilotService,
    AsyncCapacityService,
    AsyncOptimizationService,
    AsyncVisualizationService,
    AttentionService,
    AutopilotService,
    CapacityService,
    OptimizationService,
    VisualizationService,
)


class FakeHttpClient:
    def __init__(self, response=None):
        self.response = response if response is not None else {}
        self.calls = []

    def _rec(self, method, path, **kw):
        self.calls.append((method, path, kw))
        return self.response

    def get(self, path, **kw):
        return self._rec("GET", path, **kw)

    def post(self, path, **kw):
        return self._rec("POST", path, **kw)

    def put(self, path, **kw):
        return self._rec("PUT", path, **kw)

    def patch(self, path, **kw):
        return self._rec("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self._rec("DELETE", path, **kw)


class FakeAsyncHttpClient:
    def __init__(self, response=None):
        self.response = response if response is not None else {}
        self.calls = []

    async def _rec(self, method, path, **kw):
        self.calls.append((method, path, kw))
        return self.response

    async def get(self, path, **kw):
        return await self._rec("GET", path, **kw)

    async def post(self, path, **kw):
        return await self._rec("POST", path, **kw)

    async def put(self, path, **kw):
        return await self._rec("PUT", path, **kw)

    async def patch(self, path, **kw):
        return await self._rec("PATCH", path, **kw)

    async def delete(self, path, **kw):
        return await self._rec("DELETE", path, **kw)


def _assert_idempotency_header(kw, expected=None):
    headers = (kw.get("config") and kw["config"].headers) or {}
    key = headers.get("X-Idempotency-Key")
    assert key, "mutation must send X-Idempotency-Key"
    if expected is not None:
        assert key == expected
    else:
        uuid.UUID(key)  # auto-generated key must be a UUID


# ---------------------------------------------------------------- attention


def test_attention_get_and_ingest_paths():
    http = FakeHttpClient()
    svc = AttentionService(http)

    svc.get_evidence(model_id="m1", run_id="r1", limit=100)
    svc.ingest_evidence([{"modelId": "m1", "layer": 1, "head": 0}])

    method, path, kw = http.calls[0]
    assert method == "GET"
    assert path == "/api/v1/algorithms/attention"
    assert kw["params"] == {"modelId": "m1", "runId": "r1", "limit": 100}

    method, path, kw = http.calls[1]
    assert method == "POST"
    assert path == "/api/v1/algorithms/attention"
    assert kw["data"]["records"][0]["head"] == 0


# ------------------------------------------------------------- optimization


def test_optimization_job_lifecycle_paths():
    http = FakeHttpClient()
    svc = OptimizationService(http)

    svc.get_summary()
    svc.list_jobs(org_id="org-1")
    svc.create_job({"jobType": "hpo"}, idempotency_key="cj-1")
    svc.get_job("j1")
    svc.update_job("j1", {"status": "running"}, idempotency_key="uj-1")
    svc.delete_job("j1")

    assert http.calls[0][:2] == ("GET", "/api/v1/optimization")
    assert http.calls[1][:2] == ("GET", "/api/v1/optimization/jobs")
    assert http.calls[1][2]["params"] == {"orgId": "org-1"}
    assert http.calls[2][:2] == ("POST", "/api/v1/optimization/jobs")
    _assert_idempotency_header(http.calls[2][2], "cj-1")
    assert http.calls[3][:2] == ("GET", "/api/v1/optimization/jobs/j1")
    assert http.calls[4][:2] == ("PATCH", "/api/v1/optimization/jobs/j1")
    _assert_idempotency_header(http.calls[4][2], "uj-1")
    assert http.calls[5][:2] == ("DELETE", "/api/v1/optimization/jobs/j1")


def test_optimization_actions_and_trial_data_paths():
    http = FakeHttpClient()
    svc = OptimizationService(http)

    svc.run_job_action("j1", "pause", idempotency_key="pa-1")
    svc.get_job_history("j1", page=2, page_size=25)
    svc.get_job_suggestion("j1")
    svc.submit_job_suggestion("j1", {"lr": 0.5})
    svc.get_job_visualization("j1")
    svc.get_job_surface("j1", x="lr", y="depth", resolution=40)
    svc.get_job_metrics("j1")

    assert http.calls[0][:2] == ("POST", "/api/v1/optimization/jobs/j1/pause")
    _assert_idempotency_header(http.calls[0][2], "pa-1")
    assert http.calls[1][:2] == ("GET", "/api/v1/optimization/jobs/j1/history")
    assert http.calls[1][2]["params"] == {"page": 2, "pageSize": 25}
    assert http.calls[2][:2] == ("GET", "/api/v1/optimization/jobs/j1/suggest")
    assert http.calls[3][:2] == ("POST", "/api/v1/optimization/jobs/j1/suggest")
    assert http.calls[3][2]["data"] == {"lr": 0.5}
    assert http.calls[4][:2] == ("GET", "/api/v1/optimization/jobs/j1/visualization")
    assert http.calls[5][:2] == ("GET", "/api/v1/optimization/jobs/j1/visualization/surface")
    assert http.calls[5][2]["params"] == {"x": "lr", "y": "depth", "resolution": 40}
    assert http.calls[6][:2] == ("GET", "/api/v1/optimization/jobs/j1/metrics")


def test_optimization_rejects_unknown_action():
    import pytest

    svc = OptimizationService(FakeHttpClient())
    with pytest.raises(ValueError):
        svc.run_job_action("j1", "explode")


def test_optimization_drafts_paths():
    http = FakeHttpClient()
    svc = OptimizationService(http)
    svc.get_draft(org_id="org-9")
    svc.save_draft({"name": "draft"})
    assert http.calls[0][:2] == ("GET", "/api/v1/optimization/drafts")
    assert http.calls[0][2]["params"] == {"orgId": "org-9"}
    assert http.calls[1][:2] == ("POST", "/api/v1/optimization/drafts")


# ---------------------------------------------------------------- autopilot


def test_autopilot_workflow_lifecycle_paths():
    http = FakeHttpClient()
    svc = AutopilotService(http)

    svc.list(org_id="org-1")
    svc.generate("Eval support chats", seed="s1", idempotency_key="g-1")
    svc.approve("wf1", rationale="ok", edited_plan={"v": 2}, idempotency_key="a-1")
    svc.deploy("wf1", modifications={"datasetId": "ds1"}, idempotency_key="d-1")
    svc.execute("wf1", seed="s2", sync=True, idempotency_key="e-1")
    svc.revise("wf1", plan={"steps": []}, rationale="r", idempotency_key="rv-1")

    assert http.calls[0][:2] == ("GET", "/api/v1/autopilot")
    assert http.calls[0][2]["params"] == {"orgId": "org-1"}

    assert http.calls[1][:2] == ("POST", "/api/v1/autopilot/generate")
    assert http.calls[1][2]["data"] == {"description": "Eval support chats", "seed": "s1"}
    _assert_idempotency_header(http.calls[1][2], "g-1")

    assert http.calls[2][:2] == ("POST", "/api/v1/autopilot/wf1/approve")
    assert http.calls[2][2]["data"] == {"rationale": "ok", "editedPlan": {"v": 2}}
    _assert_idempotency_header(http.calls[2][2], "a-1")

    assert http.calls[3][:2] == ("POST", "/api/v1/autopilot/wf1/deploy")
    assert http.calls[3][2]["data"] == {"modifications": {"datasetId": "ds1"}}

    assert http.calls[4][:2] == ("POST", "/api/v1/autopilot/wf1/execute")
    assert http.calls[4][2]["data"] == {"seed": "s2", "sync": True}

    assert http.calls[5][:2] == ("POST", "/api/v1/autopilot/wf1/revise")
    assert http.calls[5][2]["data"] == {"plan": {"steps": []}, "rationale": "r"}


def test_autopilot_run_inspection_paths():
    http = FakeHttpClient()
    svc = AutopilotService(http)

    svc.get_run("run1")
    svc.control_run("run1", "cancel", idempotency_key="c-1")
    svc.get_run_audit("run1")
    svc.get_run_events("run1", after=5, limit=50)
    svc.get_metrics(days=7)

    assert http.calls[0][:2] == ("GET", "/api/v1/autopilot/runs/run1")
    assert http.calls[1][:2] == ("POST", "/api/v1/autopilot/runs/run1")
    assert http.calls[1][2]["data"] == {"action": "cancel"}
    _assert_idempotency_header(http.calls[1][2], "c-1")
    assert http.calls[2][:2] == ("GET", "/api/v1/autopilot/runs/run1/audit")
    assert http.calls[3][:2] == ("GET", "/api/v1/autopilot/runs/run1/events")
    assert http.calls[3][2]["params"] == {"after": 5, "limit": 50}
    assert http.calls[4][:2] == ("GET", "/api/v1/autopilot/metrics")
    assert http.calls[4][2]["params"] == {"days": 7}


# ------------------------------------------------------------ visualization


def test_visualization_dashboard_paths():
    http = FakeHttpClient()
    svc = VisualizationService(http)
    payload = {"name": "Ops", "layout": {}, "widgets": [], "refreshInterval": 60, "isPublic": False}

    svc.list_dashboards(org_id="o1", view="favorites", limit=10)
    svc.create_dashboard(payload, idempotency_key="cd-1")
    svc.get_dashboard("d1")
    svc.update_dashboard("d1", {"name": "Ops2"}, idempotency_key="ud-1")
    svc.share_dashboard("d1", idempotency_key="sh-1")
    svc.favorite_dashboard("d1", idempotency_key="fv-1")
    svc.unfavorite_dashboard("d1")
    svc.bookmark_dashboard("d1", idempotency_key="bm-1")
    svc.unbookmark_dashboard("d1")
    svc.record_dashboard_view("d1", idempotency_key="vw-1")
    svc.delete_dashboard("d1")

    assert http.calls[0][0] == "GET"
    assert http.calls[0][1] == "/api/v1/visualization/dashboards"
    assert http.calls[0][2]["params"]["orgId"] == "o1"
    assert http.calls[0][2]["params"]["view"] == "favorites"
    assert http.calls[1][:2] == ("POST", "/api/v1/visualization/dashboards")
    _assert_idempotency_header(http.calls[1][2], "cd-1")
    assert http.calls[2][:2] == ("GET", "/api/v1/visualization/dashboards/d1")
    assert http.calls[3][:2] == ("PUT", "/api/v1/visualization/dashboards/d1")
    _assert_idempotency_header(http.calls[3][2], "ud-1")
    assert http.calls[4][:2] == ("POST", "/api/v1/visualization/dashboards/d1/share")
    assert http.calls[5][:2] == ("POST", "/api/v1/visualization/dashboards/d1/favorite")
    assert http.calls[6][:2] == ("DELETE", "/api/v1/visualization/dashboards/d1/favorite")
    assert http.calls[7][:2] == ("POST", "/api/v1/visualization/dashboards/d1/bookmark")
    assert http.calls[8][:2] == ("DELETE", "/api/v1/visualization/dashboards/d1/bookmark")
    assert http.calls[9][:2] == ("POST", "/api/v1/visualization/dashboards/d1/view")
    assert http.calls[10][:2] == ("DELETE", "/api/v1/visualization/dashboards/d1")


def test_visualization_data_and_export_paths():
    http = FakeHttpClient()
    svc = VisualizationService(http)

    svc.list_widgets(dashboard_id="d1", chart_type="line", page=2)
    svc.run_query({"dataSourceId": "ds1", "query": {"id": "q", "sourceId": "ds1", "query": "select 1"}})
    svc.export({"widgetId": "w1", "format": "png"}, idempotency_key="x-1")

    assert http.calls[0][0] == "GET"
    assert http.calls[0][1] == "/api/v1/visualization/data"
    assert http.calls[0][2]["params"] == {"dashboardId": "d1", "chartType": "line", "page": 2}
    assert http.calls[1][:2] == ("POST", "/api/v1/visualization/data")
    assert http.calls[2][:2] == ("POST", "/api/v1/visualization/export")
    _assert_idempotency_header(http.calls[2][2], "x-1")


def test_visualization_scheduled_exports_paths():
    http = FakeHttpClient()
    svc = VisualizationService(http)

    svc.list_exports(status="active", limit=5)
    svc.create_export({"dashboardId": "d1", "name": "Weekly", "format": "pdf"}, idempotency_key="ce-1")
    svc.update_export("e1", {"status": "paused"}, idempotency_key="ue-1")
    svc.run_export("e1", {"settings": {"dpi": 300}}, idempotency_key="re-1")
    svc.get_export_history("e1", limit=20)
    svc.download_export("e1", org_id="org-1")
    svc.delete_export("e1")

    assert http.calls[0][0] == "GET"
    assert http.calls[0][1] == "/api/visualization/exports"
    assert http.calls[0][2]["params"] == {"status": "active", "limit": 5}
    assert http.calls[1][:2] == ("POST", "/api/visualization/exports")
    _assert_idempotency_header(http.calls[1][2], "ce-1")
    assert http.calls[2][:2] == ("PATCH", "/api/visualization/exports?id=e1")
    assert http.calls[3][:2] == ("POST", "/api/visualization/exports/e1/run")
    assert http.calls[3][2]["data"] == {"settings": {"dpi": 300}}
    assert http.calls[4][0] == "GET"
    assert http.calls[4][1] == "/api/visualization/exports/e1/history"
    assert http.calls[4][2]["params"] == {"limit": 20}
    assert http.calls[5][0] == "GET"
    assert http.calls[5][1] == "/api/visualization/exports/e1/download"
    assert http.calls[5][2]["params"] == {"orgId": "org-1"}
    assert http.calls[6][:2] == ("DELETE", "/api/visualization/exports?id=e1")


# ------------------------------------------------------------------ capacity


def test_capacity_utilization_path():
    http = FakeHttpClient()
    svc = CapacityService(http)
    svc.get_utilization(org_id="o1", range="30d")
    method, path, kw = http.calls[0]
    assert method == "GET"
    assert path == "/api/v1/capacity/utilization"
    assert kw["params"] == {"orgId": "o1", "range": "30d"}


# ------------------------------------------------------ client service wiring


def test_sync_client_exposes_readmission_services():
    from aura_one import AuraOneClient
    from aura_one.types import ClientConfig

    client = AuraOneClient(ClientConfig(api_key="ak_" + "0" * 8 + "_" + "f" * 64))
    assert isinstance(client.attention, AttentionService)
    assert isinstance(client.optimization, OptimizationService)
    assert isinstance(client.autopilot, AutopilotService)
    assert isinstance(client.visualization, VisualizationService)
    assert isinstance(client.capacity, CapacityService)


def test_async_client_exposes_readmission_services():
    from aura_one import AsyncAuraOneClient
    from aura_one.types import ClientConfig

    client = AsyncAuraOneClient(ClientConfig(api_key="ak_" + "0" * 8 + "_" + "f" * 64))
    assert isinstance(client.attention, AsyncAttentionService)
    assert isinstance(client.optimization, AsyncOptimizationService)
    assert isinstance(client.autopilot, AsyncAutopilotService)
    assert isinstance(client.visualization, AsyncVisualizationService)
    assert isinstance(client.capacity, AsyncCapacityService)


def test_async_service_paths():
    import asyncio

    http = FakeAsyncHttpClient()
    svc = AsyncAttentionService(http)
    asyncio.run(svc.get_evidence(model_id="m1"))
    assert http.calls[0][0] == "GET"
    assert http.calls[0][1] == "/api/v1/algorithms/attention"
    assert http.calls[0][2]["params"] == {"modelId": "m1"}
