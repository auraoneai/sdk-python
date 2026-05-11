"""
Prefect task helper for AuraOne.

Wraps AuraOne evaluation execution so it can be used directly inside Prefect
flows without coupling the SDK to Prefect runtime imports.
"""

from typing import Any, Dict


def run_aura_task(client: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not hasattr(client, "run_evaluation"):
        raise AttributeError("client is missing run_evaluation")
    return client.run_evaluation(payload)


__all__ = ["run_aura_task"]
