"""Auth service for AuraOne SDK."""

from typing import Optional, List, Dict, Any
from ..types import RequestConfig
from ..utils import HttpClientProtocol


class AuthService:
    """Synchronous auth service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def list_api_keys(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """List API keys."""
        return self.http_client.get("/api/auth/api-keys", config=config)

    def create_api_key(self, name: str, permissions: List[str], config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Create API key."""
        data = {"action": "create", "name": name, "permissions": permissions}
        return self.http_client.post("/api/auth/api-keys", data=data, config=config)


class AsyncAuthService:
    """Asynchronous auth service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def list_api_keys(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """List API keys."""
        return await self.http_client.get("/api/auth/api-keys", config=config)

    async def create_api_key(self, name: str, permissions: List[str], config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Create API key."""
        data = {"action": "create", "name": name, "permissions": permissions}
        return await self.http_client.post("/api/auth/api-keys", data=data, config=config)