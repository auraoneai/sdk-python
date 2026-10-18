"""
Airflow operator helper for AuraOne.

Provides a simple callable that can be wrapped by a PythonOperator to trigger
AuraOne evaluation runs inside Airflow DAGs.
"""

from typing import Any, Dict


def trigger_aura_evaluation(client: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not hasattr(client, "evaluate"):
        raise AttributeError("client is missing evaluate")
    return client.evaluate(
        template_id=payload["template_id"],
        agent_bundle_url=payload["agent_bundle_url"],
        reward_spec_id=payload.get("reward_spec_id"),
        config=payload.get("config"),
        wait=payload.get("wait", True),
    )


__all__ = ["trigger_aura_evaluation"]
