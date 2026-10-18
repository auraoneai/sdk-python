"""Enterprise Intelligence service for the AuraOne SDK.

See :mod:`.service` for the surface overview. The import path
``aura_one.services.enterprise_intelligence`` is unchanged from the former
single-module layout.
"""

from ._common import (
    IDEMPOTENCY_HEADER,
    EnterpriseIntelligenceUnavailableError,
    RequestSpec,
    _with_idempotency,
    is_enterprise_intelligence_unavailable,
    is_truncated,
)
from ._ops_data import (
    ContextSourceOps,
    HistoricalSetOps,
    ImprovementOps,
    OperationsOps,
    RegistryOps,
    RegressionOps,
)
from ._ops_work import (
    BatchOps,
    ConnectorOps,
    DeliveryOps,
    HumanTaskOps,
    ToolBindingOps,
    build_ingest_parts,
)
from ._ops_workflows import RunOps, WorkflowOps
from ._types import SLO_AREAS
from .service import AsyncEnterpriseIntelligenceService, EnterpriseIntelligenceService

__all__ = [
    "IDEMPOTENCY_HEADER",
    "SLO_AREAS",
    "AsyncEnterpriseIntelligenceService",
    "BatchOps",
    "ConnectorOps",
    "ContextSourceOps",
    "DeliveryOps",
    "EnterpriseIntelligenceService",
    "EnterpriseIntelligenceUnavailableError",
    "HistoricalSetOps",
    "HumanTaskOps",
    "ImprovementOps",
    "OperationsOps",
    "RegistryOps",
    "RegressionOps",
    "RequestSpec",
    "RunOps",
    "ToolBindingOps",
    "WorkflowOps",
    "build_ingest_parts",
    "is_enterprise_intelligence_unavailable",
    "is_truncated",
]
