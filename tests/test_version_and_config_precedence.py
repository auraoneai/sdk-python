from __future__ import annotations

import json
import pytest

import aura
import aura_one
from aura import cli
from aura.client import AuraClient
from aura_one import AuraOneClient


VALID_KEY_ENV = "ak_" + "11111111" + "_" + "a" * 64
VALID_KEY_FLAG = "ak_" + "22222222" + "_" + "b" * 64


def test_version_and_default_config_exports():
    assert isinstance(aura.VERSION, str) and len(aura.VERSION) > 0
    assert isinstance(aura_one.VERSION, str) and len(aura_one.VERSION) > 0
    assert aura.VERSION == aura_one.VERSION == aura_one.__version__
    assert aura.DEFAULT_CONFIG["base_url"] == "https://api.auraone.ai"
    assert aura_one.DEFAULT_CONFIG["base_url"] == "https://api.auraone.ai"


def test_client_env_and_explicit_argument_precedence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AURAONE_API_KEY", VALID_KEY_ENV)
    monkeypatch.setenv("AURAONE_BASE_URL", "https://env.auraone.test")
    monkeypatch.setenv("AURAONE_ORG_ID", "org_from_env")

    env_client = AuraClient()
    assert env_client.api_key == VALID_KEY_ENV
    assert env_client.base_url == "https://env.auraone.test"
    assert env_client.org_id == "org_from_env"

    explicit_client = AuraClient(
        api_key=VALID_KEY_FLAG,
        base_url="https://explicit.auraone.test/",
        org_id="org_explicit",
    )
    assert explicit_client.api_key == VALID_KEY_FLAG
    assert explicit_client.base_url == "https://explicit.auraone.test"
    assert explicit_client.org_id == "org_explicit"

    sdk_env_client = AuraOneClient.from_environment()
    assert sdk_env_client.config.base_url == "https://env.auraone.test"
    assert sdk_env_client.config.organization_id == "org_from_env"

    sdk_override_client = AuraOneClient.from_environment(
        api_key=VALID_KEY_FLAG,
        base_url="https://override.auraone.test",
        organization_id="org_override",
    )
    assert sdk_override_client.config.api_key == VALID_KEY_FLAG
    assert sdk_override_client.config.base_url == "https://override.auraone.test"
    assert sdk_override_client.config.organization_id == "org_override"


def test_cli_flag_and_environment_precedence_and_output_modes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    recorded = {}

    class StubClient:
        def __init__(self, **kwargs):
            recorded.update(kwargs)
            self._client = None

        def get_quotas(self):
            return {"remaining": 42, "org": recorded.get("org_id")}

    monkeypatch.setattr(cli, "AuraClient", StubClient)
    monkeypatch.setenv("AURAONE_API_KEY", VALID_KEY_ENV)
    monkeypatch.setenv("AURAONE_BASE_URL", "https://env.auraone.test")
    monkeypatch.setenv("AURAONE_ORG_ID", "org_env")

    assert cli.run_cli(["quotas", "--output", "json"]) == cli.EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out == {"org": "org_env", "remaining": 42}
    assert recorded == {
        "api_key": VALID_KEY_ENV,
        "base_url": "https://env.auraone.test",
        "org_id": "org_env",
    }

    assert (
        cli.run_cli(
            [
                "--api-key",
                VALID_KEY_FLAG,
                "--base-url",
                "https://flag.auraone.test",
                "--org-id",
                "org_flag",
                "quotas",
                "--output",
                "jsonl",
            ]
        )
        == cli.EXIT_OK
    )
    line = json.loads(capsys.readouterr().out.strip())
    assert line == {"org": "org_flag", "remaining": 42}
    assert recorded == {
        "api_key": VALID_KEY_FLAG,
        "base_url": "https://flag.auraone.test",
        "org_id": "org_flag",
    }
