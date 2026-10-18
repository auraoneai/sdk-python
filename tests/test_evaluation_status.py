"""PR-19 T-P1-05: aura EvaluationStatus parses every platform status literal."""

import pytest

from aura.client import AuraClient, EvaluationStatus


def test_all_platform_statuses_parse():
    # Platform statuses (apps/prisma schema + lib/evaluation/service.ts):
    # queued/pending/running/completed/failed/cancelled.
    for raw in ("queued", "pending", "running", "completed", "failed", "cancelled"):
        assert EvaluationStatus(raw).name != "UNKNOWN"


def test_unknown_status_maps_to_unknown_not_valueerror():
    assert EvaluationStatus("some_future_state") is EvaluationStatus.UNKNOWN
    assert EvaluationStatus("mystery") is EvaluationStatus.UNKNOWN


def test_get_status_handles_metrics_array_and_pending():
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "eval_1",
                "status": "pending",
                "metrics": [{"name": "accuracy", "value": 0.9}],
            }

    class FakeClient:
        def request(self, *a, **kw):
            return FakeResp()

    client = AuraClient(api_key="ak_" + "0" * 8 + "_" + "0" * 64)
    client._client = FakeClient()
    res = client.get_status("eval_1")
    assert res.status is EvaluationStatus.PENDING
    assert res.metrics == {"accuracy": 0.9}


def test_cancel_maps_evaluation_id():
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "evaluation_id": "eval_9", "status": "cancelled"}

    class FakeClient:
        def request(self, *a, **kw):
            return FakeResp()

    client = AuraClient(api_key="ak_" + "0" * 8 + "_" + "0" * 64)
    client._client = FakeClient()
    res = client.cancel("eval_9")
    assert res.id == "eval_9"
    assert res.status is EvaluationStatus.CANCELLED
