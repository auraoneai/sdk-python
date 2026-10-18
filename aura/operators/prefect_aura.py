"""
Prefect task helper for AuraOne.

Wraps AuraOne evaluation execution so it can be used directly inside Prefect
flows without coupling the SDK to Prefect runtime imports.
"""

from typing import Any, Dict


def run_aura_task(client: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not hasattr(client, "evaluate"):
        raise AttributeError("client is missing evaluate")
    return client.evaluate(
        template_id=payload["template_id"],
        agent_bundle_url=payload["agent_bundle_url"],
        reward_spec_id=payload.get("reward_spec_id"),
        config=payload.get("config"),
        wait=payload.get("wait", True),
    )


__all__ = ["run_aura_task"]
