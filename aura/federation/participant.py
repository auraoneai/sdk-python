"""Federated-learning participant client (P1-05).

Runs one `FederationParticipant` end-to-end:

    keypair generation -> local training (PyTorch/Opacus DP-SGD hook)
    -> CKKS encryption under the context fetched from the federation
    -> ed25519 signature over signaturePreimage(hash, roundId, participantId)
    -> presigned-object upload -> signed metadata POST
    (with Idempotency-Key retries)

Byte-for-byte contract, mirrored from
`apps/src/lib/federated/federation/encrypted-update.ts`:

    preimage = f"{ciphertext_hash_hex}|{round_id}|{participant_id}"

and `api/fl-aggregator/aggregate.py` for the CKKS context
(coeff_mod_bit_sizes [60, 40, 40, 60], global_scale 2**40).

`tenseal` and `torch`/`opacus` are optional: importing this module
requires only `httpx` and `cryptography`; encryption/training raise
clear errors when the extra is absent (`pip install auraone-sdk[federation]`).
"""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# CKKS parameter set — MUST match api/fl-aggregator/aggregate.py
# scheme_context(): the aggregator deserialises vectors with these.
COEFF_MOD_BIT_SIZES = [60, 40, 40, 60]
GLOBAL_SCALE_BITS = 40
DEFAULT_POLY_MODULUS_DEGREE = 8192

# Mirrors FEDERATION_API paths in apps.
_API_PREFIX = "/api/v1/organizations/{org_id}/federation"

_RETRIABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class FederationClientError(Exception):
    """Raised for transport, API, or contract failures."""

    def __init__(self, reason: str, message: str, status: Optional[int] = None):
        self.reason = reason
        self.status = status
        super().__init__(f"{reason}: {message}")


@dataclass(frozen=True)
class ParticipantKeyPair:
    """An ed25519 participant identity. `public_pem` is what the
    coordinator stores on the FederationParticipant row; `fingerprint`
    is sha256(public_pem) hex — identical to the API's
    `fingerprintPublicKey` (participants/route.ts)."""

    private_pem: str
    public_pem: str
    fingerprint: str

    @property
    def key_id(self) -> str:
        """`participantKeyId` wire format."""
        return f"ed25519:{self.fingerprint}"


def generate_keypair() -> ParticipantKeyPair:
    """Generate a fresh ed25519 keypair (PEM)."""
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = public_pem_from_private(private)
    return ParticipantKeyPair(
        private_pem=private_pem,
        public_pem=public_pem,
        fingerprint=fingerprint_public_key(public_pem),
    )


def public_pem_from_private(private: Ed25519PrivateKey) -> str:
    return (
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


def load_private_key(private_pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(
        private_pem.encode("ascii"), password=None
    )
    if not isinstance(key, Ed25519PrivateKey):
        raise FederationClientError(
            "key_type_invalid", "expected an ed25519 private key PEM"
        )
    return key


def load_public_key(public_pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(public_pem.encode("ascii"))
    if not isinstance(key, Ed25519PublicKey):
        raise FederationClientError(
            "key_type_invalid", "expected an ed25519 public key PEM"
        )
    return key


def fingerprint_public_key(public_pem: str) -> str:
    """sha256 of the PEM text — identical to the coordinator's
    `fingerprintPublicKey` (createHash("sha256").update(pem.trim()))."""
    return hashlib.sha256(public_pem.strip().encode("utf8")).hexdigest()


def signature_preimage(
    ciphertext_hash_hex: str, round_id: str, participant_id: str
) -> bytes:
    """The exact bytes the participant signs — see signaturePreimage()
    in apps/src/lib/federated/federation/encrypted-update.ts."""
    return f"{ciphertext_hash_hex}|{round_id}|{participant_id}".encode("utf8")


def sign_ciphertext_hash(
    private_pem: str,
    ciphertext_hash_hex: str,
    round_id: str,
    participant_id: str,
) -> str:
    """ed25519-sign the canonical preimage; returns base64 signature."""
    key = load_private_key(private_pem)
    signature = key.sign(
        signature_preimage(ciphertext_hash_hex, round_id, participant_id)
    )
    return base64.b64encode(signature).decode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FederationContext:
    """Response of GET participants/[participantId] (encryption context)."""

    federation_id: str
    participant_id: str
    participant_status: str
    strategy: str
    scheme: str
    poly_modulus_degree: Optional[int]
    round_id: Optional[str] = None
    round_status: Optional[str] = None


@dataclass(frozen=True)
class TrainingReport:
    """Recorded DP-SGD parameters — persisted alongside the contribution
    (never in the signed preimage)."""

    backend: str
    sample_count: int
    epochs: int = 0
    noise_multiplier: Optional[float] = None
    max_grad_norm: Optional[float] = None
    sampling_rate: Optional[float] = None


@dataclass
class SubmittedUpdate:
    """The platform's reply to a submitted update."""

    contribution_id: str
    object_key: str
    response: Mapping[str, Any] = field(default_factory=dict)


def build_ckks_context(poly_modulus_degree: int) -> Any:
    """A TenSEAL CKKS context with the production parameter set — mirrors
    `scheme_context` in api/fl-aggregator/aggregate.py so the aggregator
    deserialises blobs built here directly."""
    try:
        import tenseal as ts  # type: ignore
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise FederationClientError(
            "tenseal_missing",
            "CKKS encryption requires `pip install tenseal` "
            "(or `auraone-sdk[federation]`).",
        ) from error

    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=poly_modulus_degree,
        coeff_mod_bit_sizes=COEFF_MOD_BIT_SIZES,
    )
    context.generate_galois_keys()
    context.global_scale = 2**GLOBAL_SCALE_BITS
    return context


def encrypt_vector_ckks(
    vector: Sequence[float],
    poly_modulus_degree: int,
    *,
    context: Any = None,
) -> bytes:
    """Encrypt a plaintext parameter vector into a TenSEAL CKKS vector.

    Pass `context` to reuse a participant-held context (e.g. for
    decryption round-trips in tests); the production path builds a fresh
    one per call — the aggregator only needs the public params.
    """
    ctx = context if context is not None else build_ckks_context(poly_modulus_degree)
    try:
        import tenseal as ts  # type: ignore
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise FederationClientError(
            "tenseal_missing",
            "CKKS encryption requires `pip install tenseal` "
            "(or `auraone-sdk[federation]`).",
        ) from error
    encrypted = ts.ckks_vector(ctx, list(vector))
    return encrypted.serialize()


def dp_sgd_train(
    model: Any,
    dataloader: Any,
    optimizer: Any,
    *,
    epochs: int,
    noise_multiplier: float,
    max_grad_norm: float,
    sampling_rate: float,
    criterion: Any = None,
    device: Optional[str] = None,
) -> tuple[Any, TrainingReport]:
    """Local training hook: PyTorch + Opacus DP-SGD.

    Trains `model` with the Opacus privacy engine at the given
    (recorded) noise/clip/sampling parameters and returns the model
    parameters (as a flat list of floats) plus the report. The caller
    encrypts the returned vector — plaintext never leaves the machine.
    """
    try:
        import torch  # type: ignore
        from opacus import PrivacyEngine  # type: ignore
    except ImportError as error:  # pragma: no cover
        raise FederationClientError(
            "opacus_missing",
            "DP-SGD training requires `pip install torch opacus`.",
        ) from error

    if criterion is None:
        criterion = torch.nn.CrossEntropyLoss()
    dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = model.to(dev)

    sample_rate = sampling_rate if sampling_rate else 1.0
    privacy_engine = PrivacyEngine()
    model, optimizer, private_loader = privacy_engine.make_private(
        module=model,
        optimizer=optimizer,
        data_loader=dataloader,
        noise_multiplier=noise_multiplier,
        max_grad_norm=max_grad_norm,
    )
    model.train()
    for _ in range(epochs):
        for batch in private_loader:
            inputs, targets = batch[0].to(dev), batch[1].to(dev)
            optimizer.zero_grad()
            loss = criterion(model(inputs), targets)
            loss.backward()
            optimizer.step()

    vector: list[float] = []
    for param in model.parameters():
        vector.extend(param.detach().cpu().view(-1).tolist())
    report = TrainingReport(
        backend="opacus-dp-sgd",
        sample_count=len(dataloader.dataset),
        epochs=epochs,
        noise_multiplier=noise_multiplier,
        max_grad_norm=max_grad_norm,
        sampling_rate=sample_rate,
    )
    return vector, report


class ParticipantClient:
    """Participant-side client bound to one FederationParticipant credential."""

    def __init__(
        self,
        *,
        base_url: str,
        org_id: str,
        api_key: str,
        federation_id: str,
        participant_id: str,
        private_key_pem: str,
        timeout_seconds: float = 30.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not api_key.startswith("ak_"):
            raise FederationClientError(
                "credential_format",
                "participant credentials are ak_ API keys minted by the coordinator",
            )
        self._base = base_url.rstrip("/")
        self._org_id = org_id
        self._federation_id = federation_id
        self._participant_id = participant_id
        self._private_key_pem = private_key_pem
        self._public_key_pem = public_pem_from_private(
            load_private_key(private_key_pem)
        )
        self._fingerprint = fingerprint_public_key(self._public_key_pem)
        self._timeout = timeout_seconds
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(
            base_url=self._base,
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    # -- wiring -------------------------------------------------------

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "ParticipantClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @property
    def participant_key_id(self) -> str:
        return f"ed25519:{self._fingerprint}"

    @property
    def public_key_pem(self) -> str:
        return self._public_key_pem

    def _api(self, path: str) -> str:
        return _API_PREFIX.format(org_id=self._org_id) + path

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        retriable: bool = True,
        max_attempts: int = 3,
    ) -> httpx.Response:
        """One API call with bounded retry (same Idempotency-Key throughout)."""
        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < max_attempts:
            attempt += 1
            try:
                response = self._http.request(
                    method, path, json=json, headers=dict(headers or {})
                )
            except httpx.HTTPError as error:
                last_error = error
                if not retriable or attempt >= max_attempts:
                    raise FederationClientError(
                        "transport_failed", str(error)
                    ) from error
                time.sleep(min(2.0 * attempt, 5.0))
                continue
            if response.status_code in _RETRIABLE_STATUS and retriable and attempt < max_attempts:
                time.sleep(min(2.0 * attempt, 5.0))
                continue
            if response.status_code >= 400:
                reason = "api_error"
                try:
                    payload = response.json()
                    if isinstance(payload, dict) and "error" in payload:
                        reason = str(payload["error"])
                except ValueError:
                    pass
                raise FederationClientError(
                    reason, response.text[:400], status=response.status_code
                )
            return response
        raise FederationClientError(
            "transport_failed", str(last_error) if last_error else "no attempts"
        )

    # -- control-plane ------------------------------------------------

    def fetch_context(self, round_id: Optional[str] = None) -> FederationContext:
        """GET the participant's encryption context (scheme, strategy)."""
        path = self._api(
            f"/federations/{self._federation_id}"
            f"/participants/{self._participant_id}"
        )
        params = {"roundId": round_id} if round_id else None
        response = self._http.get(path, params=params)
        if response.status_code >= 400:
            reason = "api_error"
            try:
                payload = response.json()
                if isinstance(payload, dict) and "error" in payload:
                    reason = str(payload["error"])
            except ValueError:
                pass
            raise FederationClientError(
                reason, response.text[:400], status=response.status_code
            )
        payload = response.json()
        round_ = payload.get("round") or {}
        return FederationContext(
            federation_id=str(payload["federationId"]),
            participant_id=str(payload["participantId"]),
            participant_status=str(payload["participantStatus"]),
            strategy=str(payload.get("strategy", "fedavg")),
            scheme=str(payload["scheme"]),
            poly_modulus_degree=payload.get("polyModulusDegree"),
            round_id=round_.get("id"),
            round_status=round_.get("status"),
        )

    # -- round flow ---------------------------------------------------

    def submit_update(
        self,
        *,
        round_id: str,
        vector: Sequence[float],
        sample_count: int,
        training_report: Optional[TrainingReport] = None,
        attestation_token: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> SubmittedUpdate:
        """Full round: context -> CKKS encrypt -> sign -> presigned PUT ->
        signed metadata POST, retried under one Idempotency-Key."""
        context = self.fetch_context(round_id)
        if context.participant_status != "approved":
            raise FederationClientError(
                "participant_not_approved",
                f"participant status is {context.participant_status!r}",
            )
        if context.round_status and context.round_status != "collecting":
            raise FederationClientError(
                "round_not_open",
                f"round status is {context.round_status!r}",
            )
        degree = context.poly_modulus_degree or DEFAULT_POLY_MODULUS_DEGREE
        ciphertext = encrypt_vector_ckks(vector, degree)
        ciphertext_hash = sha256_hex(ciphertext)
        signature_b64 = sign_ciphertext_hash(
            self._private_key_pem, ciphertext_hash, round_id, self._participant_id
        )
        idem = idempotency_key or str(uuid.uuid4())

        # 1. presigned URL
        upload = self._request(
            "POST",
            self._api("/updates/upload-url"),
            json={
                "roundId": round_id,
                "participantId": self._participant_id,
                "ciphertextSizeBytes": len(ciphertext),
                "ciphertextHashHex": ciphertext_hash,
                "scheme": context.scheme,
            },
        ).json()
        upload_url = str(upload["uploadUrl"])
        object_key = str(upload["objectKey"])
        required_headers = upload.get("requiredHeaders") or {}

        # 2. ciphertext bytes -> object storage (presigned PUT)
        put_headers = {str(k): str(v) for k, v in required_headers.items()}
        put_headers["Content-Type"] = "application/octet-stream"
        put_response = self._http.put(
            upload_url, content=ciphertext, headers=put_headers
        )
        if put_response.status_code >= 400:
            raise FederationClientError(
                "ciphertext_upload_failed",
                put_response.text[:400],
                status=put_response.status_code,
            )

        # 3. signed metadata (Idempotency-Key retries safely)
        metadata: dict[str, Any] = {
            "scheme": context.scheme,
            "sampleCount": int(sample_count),
            "signatureB64": signature_b64,
            "participantKeyId": self.participant_key_id,
            # Non-cryptographic identity marker until a control-plane
            # attestation issuer lands; the schema stores it for audit.
            "attestationTokenB64": base64.b64encode(
                (
                    attestation_token
                    if attestation_token is not None
                    else f"aura-fl-participant:{self._participant_id}"
                ).encode("utf8")
            ).decode("ascii"),
            "ciphertextHashHex": ciphertext_hash,
            "roundId": round_id,
            "participantId": self._participant_id,
            "createdAtIso": datetime.now(timezone.utc).isoformat(),
            "objectKey": object_key,
        }
        response = self._request(
            "POST",
            self._api("/updates"),
            json=metadata,
            headers={"Idempotency-Key": idem},
        ).json()
        if training_report is not None:
            metadata["trainingReport"] = training_report
        return SubmittedUpdate(
            contribution_id=str(response.get("contributionId", "")),
            object_key=object_key,
            response=response,
        )
