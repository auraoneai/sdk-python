"""
LangChain plugin shim for AuraOne.

Provides a thin wrapper to execute AuraOne evaluation runs inside LangChain
pipelines without introducing a hard dependency on LangChain inside the SDK.
"""

from typing import Any, Dict, Optional, Callable


class AuraLangChainPlugin:
    def __init__(self, client: Any, run_callback: Optional[Callable[..., Dict[str, Any]]] = None):
        """
        client: AuraOne client or transport with a `run_evaluation` method.
        run_callback: Optional hook to override execution (useful for tests).
        """
        self.client = client
        self.run_callback = run_callback

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger an AuraOne evaluation run from LangChain context.
        """
        if self.run_callback:
            return self.run_callback(payload)

        if not hasattr(self.client, "run_evaluation"):
            raise AttributeError("client is missing run_evaluation")

        return self.client.run_evaluation(payload)


__all__ = ["AuraLangChainPlugin"]
