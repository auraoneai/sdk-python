"""AuraOne Python SDK.

This package provides the AuraOne client, CLI helpers, GraphQL service, and integration shims.
"""

from aura_one.version import VERSION, __version__

from .client import AuraClient
from .enterprise_intelligence import EnterpriseIntelligenceService
from .services.graphql import (
    GRAPHQL_PERSISTED_QUERIES,
    AsyncGraphQLClient,
    AsyncGraphQLService,
    GraphQLClient,
    GraphQLExecutionError,
    GraphQLService,
)
from .services.integrations import (
    SUPPORTED_CONNECTOR_NAMESPACES,
    AsyncIntegrationsService,
    IntegrationsService,
)

DEFAULT_CONFIG = {
    "base_url": "https://api.auraone.ai",
    "timeout": 30.0,
    "max_retries": 3,
    "rate_limit_retry": True,
    "debug": False,
}

__all__ = [
    "VERSION",
    "__version__",
    "DEFAULT_CONFIG",
    "AuraClient",
    "EnterpriseIntelligenceService",
    "GraphQLService",
    "AsyncGraphQLService",
    "GraphQLClient",
    "AsyncGraphQLClient",
    "GraphQLExecutionError",
    "GRAPHQL_PERSISTED_QUERIES",
    "IntegrationsService",
    "AsyncIntegrationsService",
    "SUPPORTED_CONNECTOR_NAMESPACES",
]
