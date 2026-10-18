"""Request body types for the Enterprise Intelligence routes.

Each TypedDict mirrors a route's zod schema and uses the wire field names
(camelCase), so a dict built from it is sent unchanged. Dates are ISO-8601
strings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

ContentRights = Literal[
    "NO_TRAINING", "EVALUATION_ONLY", "CUSTOMER_MODEL_ONLY", "AURAONE_MODEL_ALLOWED"
]
AcceptanceDecision = Literal["accepted", "rejected", "rework"]
ApprovalSide = Literal["customer", "auraone"]
DatasetPurpose = Literal["EVALUATION", "CUSTOMER_MODEL", "AURAONE_MODEL"]
HeldOutSplit = Literal["validation", "test"]
ToolSideEffect = Literal["READ_ONLY", "REVERSIBLE_WRITE", "IRREVERSIBLE"]
IngestionMediaType = Literal[
    "image/jpeg",
    "image/png",
    "application/pdf",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "application/json",
]


class PermissionRules(TypedDict):
    allowedActorIds: List[str]
    allowedRoles: List[str]
    allowedWorkflowVersionIds: List[str]


class _WorkflowVersionRequired(TypedDict):
    inputSchema: Any
    outputSchema: Any
    graph: Any
    policyVersionId: str
    promptVersionIds: List[str]
    modelVersionIds: List[str]
    toolVersionIds: List[str]
    humanTaskDefinitions: List[Dict[str, Any]]
    retryPolicy: Any
    timeoutPolicy: Any
    toolsetVersion: str
    programId: str
    programBriefVersionId: str
    pricingVersionId: str
    rubricVersionRef: str
    acceptanceContractVersion: str


class WorkflowVersionCreate(_WorkflowVersionRequired):
    """``POST /workflows/{id}/versions``. Every key is required."""


class ContextPackage(TypedDict, total=False):
    """``POST /workflows/{id}/versions/{vid}/context-package``."""

    sourceVersionIds: List[str]
    retrievalConfiguration: Dict[str, Any]
    policyVersionIds: List[str]
    exclusions: List[str]
    permissionRules: PermissionRules
    historicalCaseSetVersion: Optional[str]
    evaluationCaseSetVersion: Optional[str]


class EvaluationCriterion(TypedDict):
    criterionId: str
    score: float
    confidence: float
    evidenceIds: List[str]


class EvaluationCaseResult(TypedDict):
    caseId: str
    passed: bool
    criticalFailure: bool
    criteria: List[EvaluationCriterion]
    costMicros: str
    latencyMs: int
    humanIntervention: bool


class WorkflowEvaluation(TypedDict):
    """``POST /workflows/{id}/evaluations`` (strict body)."""

    evidenceId: str
    workflowVersionId: str
    suiteId: str
    expiresAt: str
    results: List[EvaluationCaseResult]


class IncidentEvidence(TypedDict):
    evidenceId: str
    evidenceType: Literal[
        "RUN_EVENT",
        "CUSTOMER_DISPOSITION",
        "HUMAN_DECISION",
        "ALERT",
        "TOOL_RECEIPT",
        "EVALUATION_RESULT",
    ]
    referenceId: str
    sha256: str
    observedAt: str


class ReplayLimits(TypedDict):
    maxTurns: int
    maxTokens: int
    maxCostMicros: int
    maxWallTimeMs: int


class BatchItem(TypedDict):
    inputContentId: str
    inputDescriptor: Any
    inputSha256: str


class _AcceptanceSelectionRequired(TypedDict):
    itemId: str
    deliveryId: str
    expectedDeliveryVersion: int
    decision: AcceptanceDecision


class BatchAcceptanceSelection(_AcceptanceSelectionRequired, total=False):
    reason: str


class IngestionGovernance(TypedDict):
    dataClassification: str
    trainingRights: ContentRights
    retentionUntil: Optional[str]
    legalHold: bool


class IngestionContract(TypedDict):
    schemaVersion: Literal["auraone.enterprise-ingestion.v1"]
    allowedMediaTypes: List[IngestionMediaType]
    spreadsheetMode: Literal["ROW_PER_ITEM", "WHOLE_FILE"]
    governance: IngestionGovernance


class IngestionSource(TypedDict):
    """One uploaded file. ``content`` is bytes or text."""

    sourceId: str
    fileName: str
    mediaType: IngestionMediaType
    content: Any


class ToolBinding(TypedDict, total=False):
    """``POST /tool-bindings`` / ``PATCH /tool-bindings/{id}``."""

    name: str
    implementationRef: str
    connectorId: str
    toolVersionId: str
    toolId: str
    toolVersion: str
    workflowVersionId: str
    provider: str
    secretReferenceId: str
    requiredScopes: List[str]
    defaultObject: str
    allowedObjects: List[str]
    allowedFields: Dict[str, List[str]]
    allowedActions: List[str]
    sideEffect: ToolSideEffect
    approvalRequired: bool
    idempotency: Literal["NONE", "REQUIRED"]
    rateLimitPerMinute: int
    maxConcurrency: int
    callbackRequired: bool
    endpoint: str
    timeoutMs: int
    sandboxProbeEndpoint: str
    allowedHosts: List[str]
    enabled: bool


class ContextSourceRegistration(TypedDict, total=False):
    """``POST /context-sources``."""

    programId: str
    sourceType: Literal["FILE", "STRUCTURED_EXPORT", "POLICY", "HISTORICAL_CASES"]
    classification: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
    processingRights: Literal[True]
    objectReference: str
    storageReceiptId: str
    sha256: str
    mediaType: str
    byteSize: int
    customerOwnerId: str
    improvementPurposes: List[str]
    retentionUntil: Optional[str]
    deletionPolicy: Literal["ON_REQUEST", "AT_RETENTION_END"]
    permissions: PermissionRules


class NormalizationField(TypedDict):
    sourceField: str
    type: Literal["string", "number", "boolean"]
    required: bool


class Normalization(TypedDict):
    version: str
    recordType: str
    fields: Dict[str, NormalizationField]


class HistoricalImport(TypedDict, total=False):
    """``POST /historical-sets``: ``records`` or ``sourceText`` + ``format``."""

    workflowDefinitionId: Optional[str]
    taskDescriptor: Any
    sourceDeclaration: Any
    rights: ContentRights
    splitSeed: Optional[str]
    records: List[Dict[str, Any]]
    sourceText: str
    format: Literal["csv", "jsonl"]


class BaselineOutput(TypedDict):
    exampleId: str
    output: Any
    evidenceRef: str


class ImprovementItem(TypedDict, total=False):
    """``POST /improvement-items``. The idempotency key is a header only."""

    incidentId: str
    regressionCandidateId: Optional[str]
    proposedChange: str
    ownerId: str
    sourceWorkflowVersionId: str
    targetWorkflowVersionId: str
    targetPromptVersionId: Optional[str]
    targetModelVersionId: Optional[str]
    requiredEvaluationSuiteId: str
    requiredEvaluationVersion: str
    requiredEvaluationThreshold: float
    evaluationResultId: Optional[str]
    evaluationScore: Optional[float]
    expectedMetric: Dict[str, Any]
    releaseDisposition: Literal["HOLD", "REJECT", "SHIP", "ROLLBACK"]


class SloThreshold(TypedDict):
    metric: str
    operator: Literal["LTE", "GTE"]
    value: float
    unit: Literal["MS", "RATE", "COUNT"]


SLO_AREAS = ("CONTROL_PLANE", "QUEUE", "WORKFLOW", "HUMAN_TASK", "CONNECTOR", "DELIVERY")

__all__ = [
    "AcceptanceDecision",
    "ApprovalSide",
    "BaselineOutput",
    "BatchAcceptanceSelection",
    "BatchItem",
    "ContentRights",
    "ContextPackage",
    "ContextSourceRegistration",
    "DatasetPurpose",
    "EvaluationCaseResult",
    "EvaluationCriterion",
    "HeldOutSplit",
    "HistoricalImport",
    "ImprovementItem",
    "IncidentEvidence",
    "IngestionContract",
    "IngestionGovernance",
    "IngestionMediaType",
    "IngestionSource",
    "Normalization",
    "NormalizationField",
    "PermissionRules",
    "ReplayLimits",
    "SLO_AREAS",
    "SloThreshold",
    "ToolBinding",
    "ToolSideEffect",
    "WorkflowEvaluation",
    "WorkflowVersionCreate",
]
