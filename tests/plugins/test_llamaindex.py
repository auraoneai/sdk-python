from aura.plugins.llamaindex import AuraLlamaIndexPlugin


class DummyClient:
    def __init__(self):
        self.calls = []

    def evaluate(self, template_id, agent_bundle_url, reward_spec_id=None, config=None, wait=True):
        self.calls.append({
            "template_id": template_id,
            "agent_bundle_url": agent_bundle_url,
            "reward_spec_id": reward_spec_id,
            "config": config,
            "wait": wait,
        })
        return {"ok": True}


def test_llamaindex_plugin_runs():
    client = DummyClient()
    plugin = AuraLlamaIndexPlugin(client)

    result = plugin.run({"template_id": "tpl_1", "agent_bundle_url": "https://x/bundle"})

    assert result["ok"] is True
    assert client.calls[0]["template_id"] == "tpl_1"


def test_llamaindex_plugin_uses_callback():
    captured = {}

    def hook(payload):
        captured["payload"] = payload
        return {"ok": True}

    plugin = AuraLlamaIndexPlugin(client=None, run_callback=hook)
    result = plugin.run({"template_id": "tpl_1", "agent_bundle_url": "x"})

    assert result["ok"] is True
    assert captured["payload"]["template_id"] == "tpl_1"
