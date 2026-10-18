"""AuraOne-hosted FL participant runner (P1-05).

Entrypoint for `Dockerfile.fl-participant` / the `flParticipantRunner`
Helm chart: one pod per participant, per-participant namespace.

Environment:

    AURA_BASE_URL            coordinator base URL (required)
    AURAONE_ORG_ID           coordinator organization id (required)
    AURA_ORG_ID              deprecated fallback for AURAONE_ORG_ID
                             (warns when used)
    FL_PARTICIPANT_API_KEY   participant credential ak_ key (required)
    FL_FEDERATION_ID         federation id (required)
    FL_PARTICIPANT_ID        participant id (required)
    FL_PRIVATE_KEY_PEM       ed25519 private key PEM (required, or path)
    FL_PRIVATE_KEY_PATH      alternative to the inline PEM
    FL_ROUND_ID              round id to submit to (required for --once;
                             in loop mode, re-read per iteration)
    FL_TRAINER_MODULE        module holding the trainer callable
    FL_TRAINER_CALLABLE      callable name inside the module
                             (default "train"); returns
                             (vector, sample_count) or a flat vector
    FL_SAMPLE_COUNT          explicit sample count when the trainer
                             returns only a vector (default 1)
    FL_TRAIN_ONCE            "true" = submit once and exit (default)
    FL_POLL_SECONDS          loop interval (default 300)
    FL_ATTESTATION_TOKEN     optional control-plane attestation token

The trainer contract is intentionally minimal: any callable returning
a flat list of floats (or ``(vector, sample_count)``) so customer code
plugs its own PyTorch/Opacus training loop in via FL_TRAINER_MODULE
without touching the transport layer.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
import warnings
from typing import Any, Callable, Sequence

from .participant import (
    FederationClientError,
    ParticipantClient,
)


def _env(name: str, required: bool = True, default: str | None = None) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        if required:
            raise FederationClientError(
                "config_missing", f"environment variable {name} is required"
            )
        return default or ""
    return value


def _org_id_env() -> str:
    """Coordinator org id: AURAONE_ORG_ID, with AURA_ORG_ID kept only as a
    deprecated fallback that warns (PR-19 T-P0-12, CC-28 R4)."""
    value = os.environ.get("AURAONE_ORG_ID", "").strip()
    if value:
        return value
    legacy = os.environ.get("AURA_ORG_ID", "").strip()
    if legacy:
        warnings.warn(
            "AURA_ORG_ID is deprecated; set AURAONE_ORG_ID instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy
    raise FederationClientError(
        "config_missing", "environment variable AURAONE_ORG_ID is required"
    )


def _load_private_key_pem() -> str:
    pem = os.environ.get("FL_PRIVATE_KEY_PEM", "").strip()
    if pem:
        return pem
    path = os.environ.get("FL_PRIVATE_KEY_PATH", "").strip()
    if path:
        with open(path, "r", encoding="utf8") as handle:
            return handle.read().strip()
    raise FederationClientError(
        "config_missing",
        "set FL_PRIVATE_KEY_PEM or FL_PRIVATE_KEY_PATH",
    )


def _load_trainer() -> Callable[..., Any] | None:
    module_name = os.environ.get("FL_TRAINER_MODULE", "").strip()
    if not module_name:
        return None
    module = importlib.import_module(module_name)
    callable_name = os.environ.get("FL_TRAINER_CALLABLE", "train").strip()
    trainer = getattr(module, callable_name, None)
    if not callable(trainer):
        raise FederationClientError(
            "trainer_missing",
            f"{module_name}.{callable_name} is not callable",
        )
    return trainer


def _run_once(client: ParticipantClient, round_id: str) -> None:
    trainer = _load_trainer()
    vector: Sequence[float]
    sample_count: int
    if trainer is None:
        raise FederationClientError(
            "trainer_missing",
            "no trainer configured — set FL_TRAINER_MODULE/FL_TRAINER_CALLABLE",
        )
    result = trainer()
    if isinstance(result, tuple) and len(result) == 2:
        vector, sample_count = result[0], int(result[1])
    else:
        vector = result  # type: ignore[assignment]
        sample_count = int(os.environ.get("FL_SAMPLE_COUNT", "1"))
    attestation = os.environ.get("FL_ATTESTATION_TOKEN", "").strip() or None
    submitted = client.submit_update(
        round_id=round_id,
        vector=vector,
        sample_count=sample_count,
        attestation_token=attestation,
    )
    print(
        json.dumps(
            {
                "event": "federation_update_submitted",
                "roundId": round_id,
                "participantId": submitted.contribution_id
                or os.environ.get("FL_PARTICIPANT_ID"),
                "objectKey": submitted.object_key,
            }
        ),
        flush=True,
    )


def main() -> int:
    client = ParticipantClient(
        base_url=_env("AURA_BASE_URL"),
        org_id=_org_id_env(),
        api_key=_env("FL_PARTICIPANT_API_KEY"),
        federation_id=_env("FL_FEDERATION_ID"),
        participant_id=_env("FL_PARTICIPANT_ID"),
        private_key_pem=_load_private_key_pem(),
    )
    once = os.environ.get("FL_TRAIN_ONCE", "true").strip().lower() == "true"
    poll_seconds = float(os.environ.get("FL_POLL_SECONDS", "300") or 300)
    try:
        while True:
            round_id = _env("FL_ROUND_ID")
            try:
                _run_once(client, round_id)
            except FederationClientError as error:
                print(
                    json.dumps(
                        {
                            "event": "federation_update_failed",
                            "reason": error.reason,
                            "status": error.status,
                            "detail": str(error),
                        }
                    ),
                    file=sys.stderr,
                    flush=True,
                )
                if once:
                    return 1
            if once:
                return 0
            time.sleep(poll_seconds)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
