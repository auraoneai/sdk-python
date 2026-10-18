"""PR-19 T-P2-03: plugins/operators dispatch evaluate() with the real signature."""

import pytest

from aura.plugins.langchain import AuraLangChainPlugin
from aura.plugins.llamaindex import AuraLlamaIndexPlugin
from aura.operators.airflow_aura import trigger_aura_evaluation
from aura.operators.prefect_aura import run_aura_task


class RecordingClient:
    def __init__(self):
        self.calls = []

    def evaluate(self, template_id, agent_bundle_url, reward_spec_id=None, config=None, wait=True):
        self.calls.append(
            {
                "template_id": template_id,
                "agent_bundle_url": agent_bundle_url,
                "reward_spec_id": reward_spec_id,
                "config": config,
                "wait": wait,
            }
        )
        return {"id": "eval_x"}


PAYLOAD = {
    "template_id": "tpl_1",
    "agent_bundle_url": "https://x/bundle",
    "config": {"inputs": {"a": 1}},
}


def _assert_dispatched(client):
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["template_id"] == "tpl_1"
    assert call["agent_bundle_url"] == "https://x/bundle"
    assert call["config"] == {"inputs": {"a": 1}}


def test_langchain_plugin_dispatches_evaluate():
    client = RecordingClient()
    assert AuraLangChainPlugin(client).run(PAYLOAD) == {"id": "eval_x"}
    _assert_dispatched(client)


def test_llamaindex_plugin_dispatches_evaluate():
    client = RecordingClient()
    assert AuraLlamaIndexPlugin(client).run(PAYLOAD) == {"id": "eval_x"}
    _assert_dispatched(client)


def test_airflow_operator_dispatches_evaluate():
    client = RecordingClient()
    assert trigger_aura_evaluation(client, PAYLOAD) == {"id": "eval_x"}
    _assert_dispatched(client)


def test_prefect_operator_dispatches_evaluate():
    client = RecordingClient()
    assert run_aura_task(client, PAYLOAD) == {"id": "eval_x"}
    _assert_dispatched(client)


def test_plugin_raises_without_evaluate():
    with pytest.raises(AttributeError):
        AuraLangChainPlugin(object()).run(PAYLOAD)
    with pytest.raises(AttributeError):
        trigger_aura_evaluation(object(), PAYLOAD)


def test_plugin_with_real_client_and_mocked_transport():
    """A real AuraClient + httpx MockTransport: the plugin must hit
    POST /api/v1/evaluations and propagate the response."""
    import httpx
    from aura.client import AuraClient

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["api_key_header"] = request.headers.get("x-api-key")
        return httpx.Response(
            201,
            json={"id": "eval_real", "status": "pending"},
        )

    client = AuraClient(
        api_key="ak_" + "ab12cd34" + "_" + "f" * 64,
        base_url="https://api.auraone.ai",
        org_id="org_contract",
    )
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    plugin = AuraLangChainPlugin(client)
    result = plugin.run({**PAYLOAD, "wait": False})

    assert seen["path"] == "/api/v1/evaluations"
    assert seen["api_key_header"] == client.api_key
    assert getattr(result, "id", None) == "eval_real"
