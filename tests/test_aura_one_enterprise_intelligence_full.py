"""Enterprise Intelligence full-surface contract tests (no network).

Every operation is called once on a recording fake HTTP client and checked
against the platform route it must hit. The same table runs against the
async service, and against the App Router route files when the monorepo is
present.
"""

import asyncio
import re
from pathlib import Path

import pytest

from aura_one.exceptions import ServerError
from aura_one.services.enterprise_intelligence import (
    AsyncEnterpriseIntelligenceService,
    EnterpriseIntelligenceService,
    EnterpriseIntelligenceUnavailableError,
    build_ingest_parts,
    is_truncated,
)
from aura_one.types import RequestConfig

EI = "/api/v1/enterprise-intelligence"
ROUTES = (
    Path(__file__).resolve().parents[3]
    / "apps/src/app/api/v1/enterprise-intelligence"
)


class RecordingHttp:
    def __init__(self):
        self.calls = []

    def _record(self, method, path, body=None, config=None, params=None, files=None):
        self.calls.append(
            {"method": method, "path": path, "body": body, "config": config,
             "params": params, "files": files}
        )
        return {"data": {}}

    def get(self, path, params=None, config=None):
        return self._record("GET", path, config=config, params=params)

    def post(self, path, data=None, config=None, files=None):
        return self._record("POST", path, body=data, config=config, files=files)

    def patch(self, path, data=None, config=None):
        return self._record("PATCH", path, body=data, config=config)

    def delete(self, path, config=None, data=None):
        return self._record("DELETE", path, body=data, config=config)


class AsyncRecordingHttp(RecordingHttp):
    async def get(self, path, params=None, config=None):
        return RecordingHttp.get(self, path, params, config)

    async def post(self, path, data=None, config=None, files=None):
        return RecordingHttp.post(self, path, data, config, files)

    async def patch(self, path, data=None, config=None):
        return RecordingHttp.patch(self, path, data, config)

    async def delete(self, path, config=None, data=None):
        return RecordingHttp.delete(self, path, config, data)


CONTRACT = {
    "schemaVersion": "auraone.enterprise-ingestion.v1",
    "allowedMediaTypes": ["text/csv"],
    "spreadsheetMode": "ROW_PER_ITEM",
    "governance": {
        "dataClassification": "CONFIDENTIAL",
        "trainingRights": "NO_TRAINING",
        "retentionUntil": None,
        "legalHold": False,
    },
}
SOURCE = {"sourceId": "sheet", "fileName": "menu.csv", "mediaType": "text/csv", "content": "a,b"}

# (method, path template, call)
OPERATIONS = [
    ("GET", "/workflows", lambda ei: ei.workflows.list()),
    ("POST", "/workflows", lambda ei: ei.workflows.create(key="k", name="n")),
    ("GET", "/workflows/{p}", lambda ei: ei.workflows.get("w1")),
    ("POST", "/workflows/{p}/versions", lambda ei: ei.workflows.create_version("w1", {})),
    ("POST", "/workflows/{p}/versions/{p}/retire", lambda ei: ei.workflows.retire_version("w1", "v1", expected_version=1, expected_definition_revision=1, reason="replaced by v2")),
    ("POST", "/workflows/{p}/versions/{p}/context-package", lambda ei: ei.workflows.bind_context_package("w1", "v1", {})),
    ("POST", "/workflows/{p}/approval-requests", lambda ei: ei.workflows.create_approval_request("w1", version_id="v1", evaluation_evidence_ref="e1")),
    ("GET", "/workflows/{p}/approval-requests/{p}", lambda ei: ei.workflows.get_approval_request("w1", "r1")),
    ("POST", "/workflows/{p}/approval-requests/{p}/customer", lambda ei: ei.workflows.decide_approval_request("w1", "r1", "customer", decision="APPROVED", evidence={"n": 1})),
    ("POST", "/workflows/{p}/approval-requests/{p}/auraone", lambda ei: ei.workflows.decide_approval_request("w1", "r1", "auraone", decision="REJECTED", evidence={"n": 1})),
    ("DELETE", "/workflows/{p}/approval-requests/{p}/customer", lambda ei: ei.workflows.revoke_approval_decision("w1", "r1", "customer", evidence={"n": 1})),
    ("DELETE", "/workflows/{p}/approval-requests/{p}/auraone", lambda ei: ei.workflows.revoke_approval_decision("w1", "r1", "auraone", evidence={"n": 1})),
    ("POST", "/workflows/{p}/activations", lambda ei: ei.workflows.activate_version("w1", version_id="v1", approval_request_id="r1")),
    ("POST", "/workflows/{p}/evaluations", lambda ei: ei.workflows.record_evaluation("w1", {})),
    ("POST", "/workflows/{p}/release-gate", lambda ei: ei.workflows.evaluate_release_gate("w1", workflow_version_id="v1", evidence_id="e1")),
    ("GET", "/runs", lambda ei: ei.runs.list()),
    ("POST", "/runs", lambda ei: ei.runs.create(workflow_version_id="v1", input_content_id="c1", environment_version="e1")),
    ("GET", "/runs/{p}", lambda ei: ei.runs.get("r1")),
    ("GET", "/runs/{p}/output", lambda ei: ei.runs.get_output("r1")),
    ("GET", "/runs/{p}/trace", lambda ei: ei.runs.get_trace("r1")),
    ("GET", "/runs/{p}/delivery", lambda ei: ei.runs.get_delivery("r1")),
    ("GET", "/run-inputs", lambda ei: ei.runs.get_inputs()),
    ("GET", "/runs/{p}/commercial", lambda ei: ei.runs.get_commercial("r1")),
    ("POST", "/runs/{p}/acceptance", lambda ei: ei.runs.decide_acceptance("r1", decision="accepted")),
    ("POST", "/runs/{p}/cancel", lambda ei: ei.runs.cancel("r1")),
    ("POST", "/runs/{p}/compensations", lambda ei: ei.runs.request_compensation("r1", side_effect_receipt_id="s1", reason="wrong record")),
    ("POST", "/compensations/{p}/execute", lambda ei: ei.runs.execute_compensation("c1")),
    ("POST", "/runs/{p}/incidents", lambda ei: ei.runs.report_incident("r1", workflow_version_id="v1", trigger="HUMAN_OVERRIDE", summary="s", rights="NO_TRAINING", evidence=[])),
    ("POST", "/runs/{p}/replay", lambda ei: ei.runs.replay("r1", workflow_version_id="v1", limits={"maxTurns": 1, "maxTokens": 1, "maxCostMicros": 0, "maxWallTimeMs": 1})),
    ("GET", "/batches", lambda ei: ei.batches.list()),
    ("POST", "/batches", lambda ei: ei.batches.submit(workflow_version_id="v1", input_contract={}, items=[])),
    ("POST", "/batches/ingest", lambda ei: ei.batches.ingest(workflow_version_id="v1", contract=CONTRACT, sources=[SOURCE])),
    ("GET", "/batches/{p}", lambda ei: ei.batches.get("b1")),
    ("GET", "/batches/{p}/items", lambda ei: ei.batches.list_items("b1")),
    ("POST", "/batches/{p}/retry", lambda ei: ei.batches.retry("b1")),
    ("POST", "/batches/{p}/cancel", lambda ei: ei.batches.cancel("b1")),
    ("POST", "/batches/{p}/acceptance", lambda ei: ei.batches.decide_acceptance("b1", selections=[])),
    ("GET", "/deliveries", lambda ei: ei.deliveries.list()),
    ("GET", "/deliveries/{p}", lambda ei: ei.deliveries.get("d1")),
    ("PATCH", "/deliveries/{p}", lambda ei: ei.deliveries.dispose("d1", action="accept")),
    ("GET", "/human-tasks", lambda ei: ei.human_tasks.list()),
    ("GET", "/human-tasks/{p}", lambda ei: ei.human_tasks.get("t1")),
    ("POST", "/human-tasks/{p}/complete", lambda ei: ei.human_tasks.complete("t1", action="APPROVE", output_content_id="o1", evidence=None, expected_lock_version=0)),
    ("GET", "/connectors", lambda ei: ei.connectors.list()),
    ("POST", "/connectors", lambda ei: ei.connectors.create(name="crm", provider="hubspot", secret_reference_id="sr1")),
    ("GET", "/connectors/{p}", lambda ei: ei.connectors.get("c1")),
    ("PATCH", "/connectors/{p}", lambda ei: ei.connectors.apply_action("c1")),
    ("POST", "/connectors/{p}/authorize", lambda ei: ei.connectors.authorize("c1", {"action": "REVOKE"})),
    ("POST", "/connectors/{p}/test", lambda ei: ei.connectors.test("c1")),
    ("POST", "/connectors/{p}/revoke", lambda ei: ei.connectors.revoke("c1")),
    ("GET", "/connectors/{p}/receipts", lambda ei: ei.connectors.list_receipts("c1")),
    ("GET", "/connectors/{p}/receipts/{p}", lambda ei: ei.connectors.get_receipt("c1", "x1")),
    ("GET", "/tool-bindings", lambda ei: ei.tool_bindings.list()),
    ("POST", "/tool-bindings", lambda ei: ei.tool_bindings.create({})),
    ("GET", "/tool-bindings/{p}", lambda ei: ei.tool_bindings.get("tb1")),
    ("PATCH", "/tool-bindings/{p}", lambda ei: ei.tool_bindings.update("tb1", {"enabled": False})),
    ("DELETE", "/tool-bindings/{p}", lambda ei: ei.tool_bindings.disable("tb1")),
    ("GET", "/context-sources", lambda ei: ei.context_sources.list()),
    ("POST", "/context-sources", lambda ei: ei.context_sources.register({})),
    ("GET", "/context-sources/{p}", lambda ei: ei.context_sources.get("s1")),
    ("POST", "/context-sources/{p}/retry", lambda ei: ei.context_sources.ingest("s1", normalization={"version": "1", "recordType": "r", "fields": {}})),
    ("POST", "/context-sources/{p}/withdraw", lambda ei: ei.context_sources.withdraw("s1")),
    ("PATCH", "/context-sources/{p}", lambda ei: ei.context_sources.apply_action("s1", action="delete")),
    ("DELETE", "/context-sources/{p}", lambda ei: ei.context_sources.delete("s1")),
    ("GET", "/historical-sets", lambda ei: ei.historical_sets.list()),
    ("POST", "/historical-sets", lambda ei: ei.historical_sets.import_set({})),
    ("GET", "/historical-sets/{p}", lambda ei: ei.historical_sets.get("h1")),
    ("GET", "/historical-sets/{p}/examples", lambda ei: ei.historical_sets.list_examples("h1")),
    ("POST", "/historical-sets/{p}/validate", lambda ei: ei.historical_sets.validate("h1")),
    ("POST", "/historical-sets/{p}/accept", lambda ei: ei.historical_sets.accept("h1")),
    ("POST", "/historical-sets/{p}/dataset", lambda ei: ei.historical_sets.create_dataset("h1", purpose="EVALUATION")),
    ("GET", "/historical-sets/{p}/baseline", lambda ei: ei.historical_sets.list_baselines("h1")),
    ("POST", "/historical-sets/{p}/baseline", lambda ei: ei.historical_sets.prepare_baseline("h1", split="test")),
    ("GET", "/improvement-items", lambda ei: ei.improvement.list_items()),
    ("POST", "/improvement-items", lambda ei: ei.improvement.create_item({})),
    ("GET", "/evaluations", lambda ei: ei.improvement.list_evaluations()),
    ("GET", "/regression-candidates", lambda ei: ei.regression.list_candidates()),
    ("POST", "/regression-candidates", lambda ei: ei.regression.create_candidate(incident_id="i1", evaluation_suite_id="s1")),
    ("POST", "/regression-candidates/{p}/review", lambda ei: ei.regression.review_candidate("rc1", decision="APPROVE", purpose="EVALUATION", reason="matches")),
    ("GET", "/regression-suites", lambda ei: ei.regression.list_suites()),
    ("POST", "/regression-suites/{p}/run", lambda ei: ei.regression.run_suite("rs1", workflow_version_id="v1", evidence_id="e1")),
    ("GET", "/regression-suites/{p}/export", lambda ei: ei.regression.export_suite("rs1")),
    ("GET", "/operations/metrics", lambda ei: ei.operations.get_metrics(program_id="p", workflow_id="w", workflow_version_id="v")),
    ("GET", "/operations/slos", lambda ei: ei.operations.list_slos(program_id="p", workflow_id="w")),
    ("POST", "/operations/slos", lambda ei: ei.operations.create_slo(program_id="p", workflow_id="w", thresholds={})),
    ("POST", "/operations/slos/{p}/approve", lambda ei: ei.operations.approve_slo("slo1")),
    ("POST", "/operations/slos/{p}/activate", lambda ei: ei.operations.activate_slo("slo1", effective_from="2026-11-01T00:00:00Z")),
    ("GET", "/operations/slos/release-gate", lambda ei: ei.operations.get_slo_release_gate(program_id="p", workflow_id="w")),
    ("GET", "/registry/node-options", lambda ei: ei.registry.get_node_options()),
    ("POST", "/registry/models", lambda ei: ei.registry.models({"action": "create", "key": "k", "name": "n"})),
    ("POST", "/registry/policies", lambda ei: ei.registry.policies({"action": "approve", "versionId": "v"})),
    ("POST", "/registry/prompts", lambda ei: ei.registry.prompts({"action": "create", "key": "k", "name": "n", "purpose": "p"})),
    ("POST", "/registry/tools", lambda ei: ei.registry.tools({"action": "create", "key": "k", "name": "n"})),
    ("GET", "/settings", lambda ei: ei.get_settings()),
    ("GET", "/dashboard", lambda ei: ei.get_dashboard()),
    ("GET", "/health", lambda ei: ei.get_health()),
]

IDS = r"/(w1|v1|r1|c1|x1|b1|d1|t1|tb1|s1|h1|rc1|rs1|slo1)(?=/|$)"


def _template(path):
    return re.sub(IDS, "/{p}", path[len(EI):])


def _check(call, method, path):
    assert call["method"] == method
    assert call["path"].startswith(EI)
    assert _template(call["path"]) == path
    config = call["config"]
    if method == "GET":
        assert config is None or "idempotency-key" not in (config.headers or {})
    else:
        assert isinstance(config, RequestConfig)
        assert 8 <= len(config.headers["idempotency-key"].strip()) <= 255


@pytest.mark.parametrize("method,path,invoke", OPERATIONS, ids=[f"{m} {p}" for m, p, _ in OPERATIONS])
def test_sync_operation_hits_route(method, path, invoke):
    http = RecordingHttp()
    invoke(EnterpriseIntelligenceService(http))
    assert len(http.calls) == 1
    _check(http.calls[0], method, path)


@pytest.mark.parametrize("method,path,invoke", OPERATIONS, ids=[f"{m} {p}" for m, p, _ in OPERATIONS])
def test_async_operation_hits_route(method, path, invoke):
    http = AsyncRecordingHttp()

    async def run():
        return await invoke(AsyncEnterpriseIntelligenceService(http))

    asyncio.run(run())
    assert len(http.calls) == 1
    _check(http.calls[0], method, path)


def test_table_is_complete():
    pairs = [f"{m} {p}" for m, p, _ in OPERATIONS]
    assert len(pairs) == len(set(pairs)) == 96


def test_sync_and_async_expose_the_same_surface():
    sync = EnterpriseIntelligenceService(RecordingHttp())
    async_ = AsyncEnterpriseIntelligenceService(AsyncRecordingHttp())

    def surface(service):
        names = {n for n in dir(service) if not n.startswith("_")}
        groups = {}
        for name in sorted(names):
            value = getattr(service, name)
            if hasattr(value, "_send"):
                groups[name] = {n for n in dir(value) if not n.startswith("_")}
        return names, groups

    assert surface(sync) == surface(async_)


@pytest.mark.skipif(not ROUTES.exists(), reason="monorepo route tree not present")
def test_every_operation_maps_to_a_route_file_exporting_the_method():
    missing = []
    for method, path, _ in OPERATIONS:
        directory = ROUTES
        for segment in [s for s in path.split("/") if s]:
            if segment == "{p}":
                params = [d for d in directory.iterdir() if re.match(r"^\[[^.].*\]$", d.name)]
                directory = params[0] if params else directory / "__missing__"
            else:
                directory = directory / segment
        route = directory / "route.ts"
        source = route.read_text() if route.exists() else ""
        pattern = (
            rf"export\s+(?:async\s+)?(?:function|const)\s+{method}\b"
            rf"|export\s*\{{[^}}]*\b{method}\b"
        )
        if not re.search(pattern, source):
            missing.append(f"{method} {path}")
    assert missing == []


def test_path_segments_are_url_encoded():
    http = RecordingHttp()
    EnterpriseIntelligenceService(http).workflows.get_approval_request("wf/1", "req 2")
    assert http.calls[0]["path"] == f"{EI}/workflows/wf%2F1/approval-requests/req%202"


def test_queue_filters_map_to_q_and_f_status():
    http = RecordingHttp()
    EnterpriseIntelligenceService(http).runs.list(q="claims", status="FAILED")
    assert http.calls[0]["params"] == {"q": "claims", "f.status": "FAILED"}


def test_flat_methods_still_pass_params_through():
    http = RecordingHttp()
    svc = EnterpriseIntelligenceService(http)
    svc.list_deliveries(params={"f.status": "AVAILABLE"})
    svc.list_improvement_items(params={"q": "x"})
    assert http.calls[0]["params"] == {"f.status": "AVAILABLE"}
    assert http.calls[1]["params"] == {"q": "x"}


def test_optional_fields_are_omitted_not_sent_as_null():
    http = RecordingHttp()
    EnterpriseIntelligenceService(http).workflows.evaluate_release_gate(
        "w1", workflow_version_id="v1", evidence_id="e1", production=True
    )
    assert http.calls[0]["body"] == {
        "workflowVersionId": "v1",
        "evidenceId": "e1",
        "production": True,
    }


def test_revoke_sends_evidence_body_on_delete():
    http = RecordingHttp()
    EnterpriseIntelligenceService(http).workflows.revoke_approval_decision(
        "w1", "r1", "customer", evidence={"reason": "approver changed"},
        idempotency_key="revoke-key-01",
    )
    call = http.calls[0]
    assert call["method"] == "DELETE"
    assert call["body"] == {"evidence": {"reason": "approver changed"}}
    assert call["config"].headers["idempotency-key"] == "revoke-key-01"


def test_unknown_approval_side_is_rejected():
    with pytest.raises(ValueError):
        EnterpriseIntelligenceService(RecordingHttp()).workflows.decide_approval_request(
            "w1", "r1", "vendor", decision="APPROVED", evidence={"n": 1}
        )


def test_batch_acceptance_uses_selections():
    http = RecordingHttp()
    selection = {
        "itemId": "i1", "deliveryId": "d1", "expectedDeliveryVersion": 2,
        "decision": "rework", "reason": "Needs supplier confirmation",
    }
    EnterpriseIntelligenceService(http).batches.decide_acceptance("b1", selections=[selection])
    assert http.calls[0]["body"] == {"selections": [selection]}


def test_ingest_builds_ordered_multipart_parts():
    form, files = build_ingest_parts(
        "wfv-1",
        CONTRACT,
        [SOURCE, {"sourceId": "photo", "fileName": "menu.jpg", "mediaType": "image/jpeg", "content": b"\xff\xd8"}],
    )
    assert form["workflowVersionId"] == "wfv-1"
    assert '"sourceId": "sheet"' in form["sources"]
    assert files == [
        ("file", ("menu.csv", b"a,b", "text/csv")),
        ("file", ("menu.jpg", b"\xff\xd8", "image/jpeg")),
    ]
    with pytest.raises(ValueError):
        build_ingest_parts("wfv-1", CONTRACT, [])


def test_ingest_sends_form_and_files():
    http = RecordingHttp()
    EnterpriseIntelligenceService(http).batches.ingest(
        workflow_version_id="v1", contract=CONTRACT, sources=[SOURCE],
        idempotency_key="ingest-key-01",
    )
    call = http.calls[0]
    assert call["files"] == [("file", ("menu.csv", b"a,b", "text/csv"))]
    assert set(call["body"]) == {"workflowVersionId", "contract", "sources"}


class Failing503(RecordingHttp):
    def get(self, path, params=None, config=None):
        raise ServerError(
            "Enterprise Intelligence runtime composition is unavailable.",
            "ENTERPRISE_COMPOSITION_UNAVAILABLE",
            None,
            503,
        )


def test_503_is_raised_as_unavailable_error():
    with pytest.raises(EnterpriseIntelligenceUnavailableError) as raised:
        EnterpriseIntelligenceService(Failing503()).list_runs()
    assert raised.value.status_code == 503
    assert raised.value.code == "ENTERPRISE_COMPOSITION_UNAVAILABLE"


def test_other_errors_pass_through_unchanged():
    class Failing500(RecordingHttp):
        def get(self, path, params=None, config=None):
            raise ServerError("Request failed.", "INTERNAL_ERROR", None, 500)

    with pytest.raises(ServerError) as raised:
        EnterpriseIntelligenceService(Failing500()).list_runs()
    assert not isinstance(raised.value, EnterpriseIntelligenceUnavailableError)


def test_is_truncated():
    assert is_truncated({"total": 140, "loaded": 100})
    assert not is_truncated({"total": 100, "loaded": 100})
    assert not is_truncated(None)
