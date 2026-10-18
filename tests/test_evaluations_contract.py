"""PR-19 T-P0-12/T-P1-05: evaluation contract vs shared fixtures.

Same fixtures as the TypeScript contract test
(sdks/contract-fixtures/evaluations/*.json) — both SDKs must agree.
"""

import json
from pathlib import Path

from aura_one.services.evaluations import EvaluationsService

FIXTURES = (
    Path(__file__).resolve().parent.parent.parent
    / "contract-fixtures"
    / "evaluations"
)


def _load(name):
    return json.loads((FIXTURES / name).read_text())


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def _rec(self, method, path, **kw):
        self.calls.append((method, path, kw))
        return self.response

    def get(self, path, **kw):
        return self._rec("GET", path, **kw)

    def post(self, path, **kw):
        return self._rec("POST", path, **kw)


def test_create_uses_platform_route_and_body():
    svc = EvaluationsService(FakeHttpClient(_load("create-response.json")))
    res = svc.create(
        template_id="tpl_123",
        agent_bundle_url="https://x/bundle.tar.gz",
        config={"inputs": {"scenario": "s1"}},
    )
    assert svc.http_client.calls[0][0] == "POST"
    assert svc.http_client.calls[0][1] == "/api/v1/evaluations"
    body = svc.http_client.calls[0][2]["data"]
    assert body["template_id"] == "tpl_123"
    assert res["id"] == "eval_9f1c2d"


def test_get_uses_platform_route():
    svc = EvaluationsService(FakeHttpClient(_load("get-response.json")))
    res = svc.get("eval_9f1c2d")
    method, path, _ = svc.http_client.calls[0]
    assert method == "GET"
    assert path == "/api/v1/evaluations/eval_9f1c2d"
    assert res["status"] in ("queued", "pending", "running", "completed", "failed", "cancelled")
    assert isinstance(res["metrics"], list)


def test_cancel_uses_segment_route_not_colon():
    svc = EvaluationsService(FakeHttpClient(_load("cancel-response.json")))
    res = svc.cancel("eval_9f1c2d")
    method, path, _ = svc.http_client.calls[0]
    assert method == "POST"
    assert path == "/api/v1/evaluations/eval_9f1c2d/cancel"
    assert ":cancel" not in path
    assert res.get("evaluation_id") or res.get("id")
