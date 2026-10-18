"""PR-19 T-P0-03/T-P0-13: platform ak_ key format; no unsafe defaults."""

import json
import re
from pathlib import Path

import pytest

from aura_one.auth import AuthProvider
from aura_one.client import AuraOneClient
from aura_one.exceptions import AuthenticationError

# Mirrors apps/src/lib/security/api-keys.ts generateAPIKey: ak_<8hex>_<64hex>
VALID_KEY = "ak_" + "a1b2c3d4" + "_" + "0123456789abcdef" * 4


def test_valid_ak_key_accepted():
    assert VALID_KEY.startswith("ak_")
    assert len(VALID_KEY.split("_")[1]) == 8
    assert len(VALID_KEY.split("_")[2]) == 64
    assert AuthProvider.is_valid_api_key(VALID_KEY) is True
    assert AuthProvider.is_valid_api_key("ak_" + "0" * 8 + "_" + "f" * 64) is True


def test_legacy_keys_rejected():
    assert AuthProvider.is_valid_api_key("aura_live_" + "a" * 40) is False
    assert AuthProvider.is_valid_api_key("aura_test_" + "a" * 40) is False
    assert AuthProvider.is_valid_api_key("") is False
    assert AuthProvider.is_valid_api_key("ak_short") is False
    assert AuthProvider.is_valid_api_key("ak_" + "G" * 8 + "_" + "0" * 64) is False


def test_compute_aoc_key_rejected_by_platform_client_and_identified():
    # aoc_<8 hex>_<secret>: minted for keyPurpose="compute"; rejected by the
    # platform client validator (R2) but identifiable for error messages.
    compute_key = "aoc_" + "a1b2c3d4" + "_" + "x" * 40
    assert AuthProvider.is_valid_api_key(compute_key) is False
    assert AuthProvider.is_compute_api_key(compute_key) is True
    assert AuthProvider.is_compute_api_key(VALID_KEY) is False
    assert AuthProvider.is_valid_api_key("aoc_" + "x" * 5) is False
    assert AuthProvider.is_valid_api_key("aoc_" + "G" * 8 + "_" + "x" * 40) is False


def test_with_api_key_and_setters_enforce_format():
    with pytest.raises(AuthenticationError):
        AuraOneClient.with_api_key("aura_live_" + "x" * 40)
    with pytest.raises(AuthenticationError):
        AuraOneClient.with_api_key("aoc_" + "x" * 5)

    client = AuraOneClient.with_api_key(VALID_KEY)
    assert client.is_authenticated()
    with pytest.raises(AuthenticationError):
        client.set_api_key("not-a-key")


def test_aura_one_api_key_uses_x_api_key_header():
    from aura_one.types import ClientConfig

    client = AuraOneClient(ClientConfig(api_key=VALID_KEY))
    headers = client.auth_provider.get_auth_headers()
    assert headers["X-API-Key"] == VALID_KEY
    assert "Authorization" not in headers


def test_org_id_sent_as_query_assertion_not_header():
    from aura_one.types import ClientConfig

    client = AuraOneClient(
        ClientConfig(api_key=VALID_KEY, organization_id="org_abc")
    )
    headers = client.http_client._build_headers()
    assert "X-Org-Id" not in headers
    assert "X-Organization-Id" not in headers
    assert "X-AuraOne-Organization-Id" not in headers
    assert client.http_client.organization_id == "org_abc"


def test_shared_issuer_fixture_agrees():
    """FPF-A-028: sdks/fixtures/platform-api-key.json is the contract shared with the issuer and the TypeScript SDK."""
    fixture = json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures" / "platform-api-key.json").read_text()
    )
    assert fixture["pattern"] == "^ak_[a-f0-9]{8}_[a-f0-9]{64}$"
    pattern = re.compile(fixture["pattern"])
    for key in fixture["valid"]:
        assert pattern.match(key)
        assert AuthProvider.is_valid_api_key(key) is True
    for key in fixture["invalid"]:
        assert not pattern.match(key)
        assert AuthProvider.is_valid_api_key(key) is False
