"""
Airflow operator helper for AuraOne.

Provides a simple callable that can be wrapped by a PythonOperator to trigger
AuraOne evaluation runs inside Airflow DAGs.
"""

from typing import Any, Dict


def trigger_aura_evaluation(client: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not hasattr(client, "run_evaluation"):
        raise AttributeError("client is missing run_evaluation")
    return client.run_evaluation(payload)


__all__ = ["trigger_aura_evaluation"]
