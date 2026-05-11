from aura.plugins.llamaindex import AuraLlamaIndexPlugin


class DummyClient:
    def __init__(self):
        self.calls = []

    def run_evaluation(self, payload):
        self.calls.append(payload)
        return {"ok": True, "payload": payload}


def test_llamaindex_plugin_runs():
    client = DummyClient()
    plugin = AuraLlamaIndexPlugin(client)

    result = plugin.run({"foo": "bar"})

    assert result["ok"] is True
    assert client.calls[0]["foo"] == "bar"


def test_llamaindex_plugin_uses_callback():
    captured = {}

    def hook(payload):
        captured["payload"] = payload
        return {"ok": True}

    plugin = AuraLlamaIndexPlugin(client=None, run_callback=hook)
    result = plugin.run({"baz": 1})

    assert result["ok"] is True
    assert captured["payload"]["baz"] == 1
