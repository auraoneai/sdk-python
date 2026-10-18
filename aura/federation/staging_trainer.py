"""Synthetic DP-SGD trainer for the staging multi-party receipt (P2-07).

Plug-in for ``aura.federation.runner`` (``FL_TRAINER_MODULE=
aura.federation.staging_trainer``). It trains a tiny linear classifier with
Opacus DP-SGD on data generated deterministically from the participant id, so
two participants hold different local data while a rerun reproduces the same
vector. The receipt proves transport, encryption, aggregation, budgeting and
audit — not model quality — so the data is synthetic by design and the module
says so; customer deployments plug their own trainer in through the same hook.

Requires ``torch`` and ``opacus`` (customer-side extras, see pyproject).

Environment:

    FL_PARTICIPANT_ID     seeds the local dataset (required)
    FL_DP_NOISE           noise multiplier (default 1.1)
    FL_DP_CLIP            per-sample clip norm (default 1.0)
    FL_DP_EPOCHS          local epochs (default 2)
    FL_DP_SAMPLES         local sample count (default 256)
"""

from __future__ import annotations

import hashlib
import os
import random
from typing import Sequence

from .participant import FederationClientError, dp_sgd_train

FEATURES = 16
CLASSES = 2
BATCH_SIZE = 32


def _seed_from(participant_id: str) -> int:
    return int.from_bytes(hashlib.sha256(participant_id.encode("utf8")).digest()[:8], "big")


def _synthetic_dataset(participant_id: str, samples: int) -> tuple[list[list[float]], list[int]]:
    rng = random.Random(_seed_from(participant_id))
    inputs: list[list[float]] = []
    labels: list[int] = []
    for _ in range(samples):
        row = [rng.gauss(0.0, 1.0) for _ in range(FEATURES)]
        labels.append(1 if sum(row[: FEATURES // 2]) > sum(row[FEATURES // 2 :]) else 0)
        inputs.append(row)
    return inputs, labels


def train() -> tuple[Sequence[float], int]:
    """Return ``(flat parameter vector, local sample count)``."""
    participant_id = os.environ.get("FL_PARTICIPANT_ID", "").strip()
    if not participant_id:
        raise FederationClientError(
            "config_missing", "FL_PARTICIPANT_ID is required for the staging trainer"
        )
    try:
        import torch  # type: ignore
        from torch.utils.data import DataLoader, TensorDataset  # type: ignore
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise FederationClientError(
            "opacus_missing", "the staging trainer requires `pip install torch opacus`."
        ) from error

    samples = int(os.environ.get("FL_DP_SAMPLES", "256"))
    noise = float(os.environ.get("FL_DP_NOISE", "1.1"))
    clip = float(os.environ.get("FL_DP_CLIP", "1.0"))
    epochs = int(os.environ.get("FL_DP_EPOCHS", "2"))

    inputs, labels = _synthetic_dataset(participant_id, samples)
    torch.manual_seed(_seed_from(participant_id) % (2**31))
    dataset = TensorDataset(
        torch.tensor(inputs, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.long),
    )
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    model = torch.nn.Linear(FEATURES, CLASSES)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

    vector, report = dp_sgd_train(
        model,
        loader,
        optimizer,
        epochs=epochs,
        noise_multiplier=noise,
        max_grad_norm=clip,
        sampling_rate=BATCH_SIZE / samples,
    )
    return list(vector), report.sample_count
