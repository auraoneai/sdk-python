from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
import pytest

from aura import cli
from aura.client import EvaluationResult, EvaluationStatus, Template
from aura_one.exceptions import AuthenticationError, RateLimitError


class FakeTransport:
    def close(self) -> None:
        pass


class FakeClient:
    last_kwargs: Dict[str, Any] = {}
    templates: List[Template] = [
        Template(id="robotics-v1", name="Robotics Safety", version="1.2.0", domain="robotics"),
        Template(id="agent-v1", name="Agent Reliability", version="2.0.0"),
    ]
    error: Optional[Exception] = None

    def __init__(self, **kwargs: Any) -> None:
        type(self).last_kwargs = kwargs
        self._client = FakeTransport()

    def _result(self, value: Any) -> Any:
        if type(self).error is not None:
            raise type(self).error
        return value

    def list_templates(self, **kwargs: Any) -> List[Template]:
        type(self).last_kwargs.update(kwargs)
        return self._result(self.templates)

    def evaluate(self, **kwargs: Any) -> EvaluationResult:
        type(self).last_kwargs.update(kwargs)
        return self._result(EvaluationResult(id="eval_123", status=EvaluationStatus.QUEUED))

    def evaluate_robust(self, **kwargs: Any) -> EvaluationResult:
        type(self).last_kwargs["robust"] = True
        return self.evaluate(**kwargs)

    def get_quotas(self) -> Dict[str, Any]:
        return self._result({"remaining": 7, "unlimited": False})

    def get_system_health(self) -> Dict[str, Any]:
        return self._result({"status": "healthy", "services": ["api", "runner"]})


@pytest.fixture(autouse=True)
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.error = None
    FakeClient.last_kwargs = {}
    monkeypatch.setattr(cli, "AuraClient", FakeClient)


def test_list_templates_renders_professional_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.run_cli(["list-templates", "--domain", "robotics"]) == cli.EXIT_OK

    captured = capsys.readouterr()
    assert "ID" in captured.out
    assert "Robotics Safety" in captured.out
    assert "EvaluationStatus" not in captured.out
    assert captured.err == ""
    assert FakeClient.last_kwargs["domain"] == "robotics"


def test_json_output_serializes_dataclasses_and_enums(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.run_cli(
        [
            "evaluate",
            "--template-id",
            "robotics-v1",
            "--agent-bundle-url",
            "https://example.com/agent.zip",
            "--output",
            "json",
        ]
    )

    assert exit_code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {
        "artifacts_url": None,
        "id": "eval_123",
        "metrics": None,
        "score": None,
        "status": "queued",
    }


def test_jsonl_emits_one_template_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.run_cli(["--output", "jsonl", "list-templates"]) == cli.EXIT_OK

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["id"] for record in records] == ["robotics-v1", "agent-v1"]


def test_global_configuration_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AURAONE_API_KEY", "secret")
    monkeypatch.setenv("AURAONE_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("AURAONE_ORG_ID", "org_test")

    assert cli.run_cli(["quotas", "--output", "json"]) == cli.EXIT_OK
    capsys.readouterr()
    assert FakeClient.last_kwargs["api_key"] == "secret"
    assert FakeClient.last_kwargs["base_url"] == "https://api.example.test"
    assert FakeClient.last_kwargs["org_id"] == "org_test"


def test_no_color_flag_and_environment_disable_ansi(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    FakeClient.error = AuthenticationError("invalid key")
    monkeypatch.setattr(cli.sys.stderr, "isatty", lambda: True)

    assert cli.run_cli(["--no-color", "quotas"]) == cli.EXIT_AUTHENTICATION
    assert "\033[" not in capsys.readouterr().err

    monkeypatch.setenv("NO_COLOR", "")
    assert cli.run_cli(["quotas"]) == cli.EXIT_AUTHENTICATION
    assert "\033[" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("error", "expected_exit", "expected_type"),
    [
        (AuthenticationError("invalid key"), cli.EXIT_AUTHENTICATION, "authentication_error"),
        (RateLimitError("slow down", retry_after=12), cli.EXIT_RATE_LIMIT, "rate_limit_error"),
        (httpx.ConnectError("connection refused"), cli.EXIT_NETWORK, "network_error"),
    ],
)
def test_machine_readable_errors_have_stable_contract(
    error: Exception,
    expected_exit: int,
    expected_type: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    FakeClient.error = error

    assert cli.run_cli(["quotas", "--output", "json"]) == expected_exit
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error"]["type"] == expected_type
    assert payload["error"]["exit_code"] == expected_exit
    assert payload["error"]["hint"]


def test_invalid_pagination_has_usage_exit_and_actionable_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.run_cli(["list-templates", "--page", "0"]) == cli.EXIT_USAGE

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--page must be at least 1" in captured.err
    assert "aura --help" in captured.err


def test_robust_evaluation_selects_retrying_client_method(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.run_cli(
        [
            "evaluate",
            "--template-id",
            "robotics-v1",
            "--agent-bundle-url",
            "https://example.com/agent.zip",
            "--robust",
            "--output",
            "jsonl",
        ]
    )

    assert exit_code == cli.EXIT_OK
    capsys.readouterr()
    assert FakeClient.last_kwargs["robust"] is True


def test_version_matches_package(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.run_cli(["--version"])

    assert exc_info.value.code == 0
    assert cli.__version__ in capsys.readouterr().out
