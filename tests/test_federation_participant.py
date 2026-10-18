"""P1-05: participant SDK tests — keypair, signing contract, context
parsing, upload flow (mocked transport), retry/idempotency."""

import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura.federation import (  # noqa: E402
    FederationClientError,
    ParticipantClient,
    fingerprint_public_key,
    generate_keypair,
    sha256_hex,
    sign_ciphertext_hash,
    signature_preimage,
)

ORG = "org_coord"
FED = "fed_1"
PART = "part_1"
ROUND = "round_1"


def _context_payload(**over):
    payload = {
        "federationId": FED,
        "participantId": PART,
        "participantStatus": "approved",
        "strategy": "fedavg",
        "scheme": "CKKS-TenSEAL/8192",
        "polyModulusDegree": 8192,
        "round": {"id": ROUND, "status": "collecting", "scheme": "CKKS-TenSEAL/8192"},
    }
    payload.update(over)
    return payload


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text or (json.dumps(payload) if payload else "")

    def json(self):
        return self._payload


class StubClient:
    """Duck-typed httpx.Client for ParticipantClient injection."""

    def __init__(self, handlers):
        self._handlers = handlers
        self.calls = []

    def _find(self, method, url):
        for (m, needle), handler in self._handlers.items():
            if m == method and needle in str(url):
                return handler(self, method, url)
        raise AssertionError(f"unexpected {method} {url}")

    def request(self, method, url, json=None, headers=None):  # noqa: A002
        self.calls.append((method, str(url), json, headers))
        return self._find(method, url)

    def get(self, url, params=None):
        self.calls.append(("GET", str(url)))
        return self._find("GET", url)

    def put(self, url, content=None, headers=None):
        self.calls.append(("PUT", str(url), headers, len(content or b"")))
        return self._find("PUT", url)

    def close(self):
        pass


def _client(stub):
    keypair = generate_keypair()
    return ParticipantClient(
        base_url="https://api.test",
        org_id=ORG,
        api_key="ak_12345678_" + "ab" * 32,
        federation_id=FED,
        participant_id=PART,
        private_key_pem=keypair.private_pem,
        http_client=stub,
    ), keypair


def test_generate_keypair_pem_and_fingerprint():
    kp = generate_keypair()
    assert kp.private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert kp.public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert len(kp.fingerprint) == 64
    assert kp.fingerprint == fingerprint_public_key(kp.public_pem)
    assert kp.key_id.startswith("ed25519:")


def test_signature_preimage_is_byte_exact():
    # Mirrors signaturePreimage() in encrypted-update.ts.
    assert (
        signature_preimage("abc123", "round_1", "part_1")
        == b"abc123|round_1|part_1"
    )


def test_sign_ciphertext_hash_verifies_locally():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization

    kp = generate_keypair()
    sig_b64 = sign_ciphertext_hash(kp.private_pem, "deadbeef" * 8, ROUND, PART)
    pub = serialization.load_pem_public_key(kp.public_pem.encode())
    assert isinstance(pub, Ed25519PublicKey)
    pub.verify(
        base64.b64decode(sig_b64),
        signature_preimage("deadbeef" * 8, ROUND, PART),
    )


def test_fetch_context_parses_round():
    stub = StubClient(
        {
            ("GET", f"/federations/{FED}/participants/{PART}"): lambda s, m, u: FakeResponse(
                200, _context_payload()
            ),
        }
    )
    client, _ = _client(stub)
    ctx = client.fetch_context(ROUND)
    assert ctx.scheme == "CKKS-TenSEAL/8192"
    assert ctx.poly_modulus_degree == 8192
    assert ctx.round_status == "collecting"


def test_submit_update_flow_and_idempotent_retry(monkeypatch):
    ciphertext_blobs = []

    def upload_url(stub, method, url):
        return FakeResponse(
            200,
            {
                "uploadUrl": "https://s3.test/presigned",
                "objectKey": "federation/org/fed/round/part/contrib.bin",
                "contributionId": "contrib_1",
                "expiresInSeconds": 900,
                "requiredHeaders": {"x-amz-server-side-encryption": "aws:kms"},
            },
        )

    def put_s3(stub, method, url):
        return FakeResponse(200, {})

    attempts = {"updates": 0}

    def updates(stub, method, url):
        attempts["updates"] += 1
        if attempts["updates"] == 1:
            return FakeResponse(503, {"error": "transient"})
        return FakeResponse(200, {"contributionId": "contrib_1", "status": "accepted"})

    monkeypatch.setattr(
        "aura.federation.participant.encrypt_vector_ckks",
        lambda vector, degree: b"cipher-" + bytes([len(vector)]),
    )
    stub = StubClient(
        {
            ("GET", f"/federations/{FED}/participants/{PART}"): lambda s, m, u: FakeResponse(
                200, _context_payload()
            ),
            ("POST", "/updates/upload-url"): upload_url,
            ("PUT", "s3.test"): put_s3,
            ("POST", "/updates"): updates,
        }
    )
    client, kp = _client(stub)
    submitted = client.submit_update(
        round_id=ROUND, vector=[1.0, 2.0, 3.0], sample_count=42
    )
    assert submitted.contribution_id == "contrib_1"
    assert submitted.object_key.startswith("federation/")
    # retry: two POST /updates attempts, same Idempotency-Key
    update_calls = [
        c for c in stub.calls if c[0] == "POST" and str(c[1]).endswith("/updates")
    ]
    assert len(update_calls) == 2
    keys = {c[3]["Idempotency-Key"] for c in update_calls}
    assert len(keys) == 1
    # metadata carried the real sha256 of the ciphertext
    metadata = update_calls[-1][2]
    assert metadata["ciphertextHashHex"] == sha256_hex(b"cipher-\x03")
    assert metadata["participantKeyId"] == f"ed25519:{kp.fingerprint}"
    assert metadata["objectKey"] == "federation/org/fed/round/part/contrib.bin"


def test_submit_update_refuses_unapproved_participant(monkeypatch):
    monkeypatch.setattr(
        "aura.federation.participant.encrypt_vector_ckks",
        lambda vector, degree: b"x",
    )
    stub = StubClient(
        {
            ("GET", f"/federations/{FED}/participants/{PART}"): lambda s, m, u: FakeResponse(
                200, _context_payload(participantStatus="pending")
            ),
        }
    )
    client, _ = _client(stub)
    with pytest.raises(FederationClientError) as exc_info:
        client.submit_update(round_id=ROUND, vector=[1.0], sample_count=1)
    assert exc_info.value.reason == "participant_not_approved"


def test_submit_update_refuses_closed_round(monkeypatch):
    monkeypatch.setattr(
        "aura.federation.participant.encrypt_vector_ckks",
        lambda vector, degree: b"x",
    )
    stub = StubClient(
        {
            ("GET", f"/federations/{FED}/participants/{PART}"): lambda s, m, u: FakeResponse(
                200,
                _context_payload(
                    round={"id": ROUND, "status": "completed", "scheme": "CKKS-TenSEAL/8192"}
                ),
            ),
        }
    )
    client, _ = _client(stub)
    with pytest.raises(FederationClientError) as exc_info:
        client.submit_update(round_id=ROUND, vector=[1.0], sample_count=1)
    assert exc_info.value.reason == "round_not_open"


def test_api_error_reason_surfaces():
    stub = StubClient(
        {
            ("GET", f"/federations/{FED}/participants/{PART}"): lambda s, m, u: FakeResponse(
                403, {"error": "participant_credential_mismatch"}
            ),
        }
    )
    client, _ = _client(stub)
    with pytest.raises(FederationClientError) as exc_info:
        client.fetch_context(ROUND)
    assert exc_info.value.reason == "participant_credential_mismatch"
    assert exc_info.value.status == 403


def test_ckks_encrypt_roundtrip():
    tenseal = pytest.importorskip("tenseal")
    from aura.federation.participant import (
        build_ckks_context,
        encrypt_vector_ckks,
    )

    # CKKS contexts generate a fresh secret key each build — the
    # encrypting context (or its secret-bearing serialisation) is the
    # only one that can decrypt. Pass the context in to round-trip.
    ctx = build_ckks_context(8192)
    blob = encrypt_vector_ckks([0.5, -0.25, 1.0], 8192, context=ctx)
    assert isinstance(blob, bytes) and len(blob) > 100
    vec = tenseal.ckks_vector_from(ctx, blob)
    out = vec.decrypt()
    assert pytest.approx(out[:3], abs=1e-3) == [0.5, -0.25, 1.0]


def test_ckks_blob_deserialises_under_aggregator_context():
    tenseal = pytest.importorskip("tenseal")
    from aura.federation.participant import (
        build_ckks_context,
        encrypt_vector_ckks,
    )

    # Aggregator-side contract (aggregate.py): the sidecar rebuilds a
    # public-params-only context — no secret key — and deserialises each
    # contribution for the homomorphic sum. The blob must load there.
    blob_a = encrypt_vector_ckks([1.0, 2.0], 8192)
    blob_b = encrypt_vector_ckks([3.0, 4.0], 8192)
    aggregator_ctx = tenseal.context(
        tenseal.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60],
    )
    aggregator_ctx.global_scale = 2**40
    va = tenseal.ckks_vector_from(aggregator_ctx, blob_a)
    vb = tenseal.ckks_vector_from(aggregator_ctx, blob_b)
    assert (va + vb) is not None
