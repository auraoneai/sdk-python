"""Collaboration service for AuraOne SDK."""

from typing import Optional, Dict, Any
from ..types import RequestConfig
from ..utils import HttpClientProtocol


class CollaborationService:
    """Synchronous collaboration service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def get_active_collaborations(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get active collaborations."""
        return self.http_client.get("/api/collaboration/active", config=config)


class AsyncCollaborationService:
    """Asynchronous collaboration service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def get_active_collaborations(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get active collaborations."""
        return await self.http_client.get("/api/collaboration/active", config=config)