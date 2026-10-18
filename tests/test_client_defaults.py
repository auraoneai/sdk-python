"""PR-19 T-P0-13: the Python client has no unsafe defaults.

AuraClient() with no argument and a clean environment raises, so no request
can be sent without a credential; the org id is never defaulted.
"""

import warnings

import pytest

from aura.client import AuraClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("AURAONE_API_KEY", raising=False)
    monkeypatch.delenv("AURA_API_KEY", raising=False)


def test_client_without_credential_raises():
    with pytest.raises(ValueError, match="requires an API key"):
        AuraClient()


def test_empty_string_key_is_not_a_credential():
    with pytest.raises(ValueError, match="requires an API key"):
        AuraClient(api_key="")


def test_auraone_api_key_env_is_used(monkeypatch):
    monkeypatch.setenv("AURAONE_API_KEY", "ak_test_from_env")
    client = AuraClient()
    assert client.api_key == "ak_test_from_env"
    assert client.org_id is None


def test_legacy_env_key_warns(monkeypatch):
    monkeypatch.setenv("AURA_API_KEY", "ak_test_legacy")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = AuraClient()
    assert client.api_key == "ak_test_legacy"
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)


def test_argument_wins_over_environment(monkeypatch):
    monkeypatch.setenv("AURAONE_API_KEY", "ak_test_from_env")
    assert AuraClient(api_key="ak_test_argument").api_key == "ak_test_argument"
