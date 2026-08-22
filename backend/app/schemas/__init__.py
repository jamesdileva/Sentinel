"""Pydantic response/request schemas.

Response schemas map to the SQLModel tables in `app.db.models` via
`from_attributes`, so API handlers can return ORM objects directly.
"""

from app.schemas.build import (
    BuildLogRead,
    BuildTrigger,
    JobStatus,
    build_status_from_log,
)
from app.schemas.chat import ChatMessageCreate, ChatMessageRead
from app.schemas.git import GitCommitRead
from app.schemas.job import JobEnvelope
from app.schemas.knowledge import KnowledgeSummaryRead
from app.schemas.observatory import (
    ArchitectureNode,
    GalaxyGraph,
    GalaxyLink,
    GalaxyNode,
    Timeline,
    TimelineEvent,
)
from app.schemas.portfolio import (
    FeatureMatrix,
    PortfolioCandidate,
    PortfolioScoreRead,
    PortfolioSummary,
)
from app.schemas.project import (
    ProjectFileRead,
    ProjectList,
    ProjectRead,
)
from app.schemas.rag import (
    RagIndexRequest,
    RagQueryRequest,
    RagResponse,
    RagResult,
    RagSearchRequest,
    RagSearchResponse,
)
from app.schemas.security import (
    ScanResponse,
    SecurityClearRead,
    SecurityFindingCreate,
    SecurityFindingRead,
)
from app.schemas.session import (
    SessionCheckpointCreate,
    SessionCheckpointRead,
    SessionCreate,
    SessionEndRequest,
    SessionExportRead,
    SessionRead,
    SessionScreenshotCreate,
    SessionScreenshotRead,
    SessionUpdate,
)
from app.schemas.system import (
    ActivityEventRead,
    ActivityResponse,
    ComponentStatusRead,
    OllamaRecentQuery,
    OllamaStatusRead,
    SyncLastRun,
    SyncStatusRead,
    SystemOverview,
)
from app.schemas.test import TestResultRead, TestRunResponse
from app.schemas.tester import TesterDescriptor, TesterRunRequest
from app.schemas.triage import TriageEvidence, TriageFrame, TriageRead, TriageSourceLine
from app.schemas.world_sim import (
    WorldAccelerateRequest,
    WorldDisasterRequest,
    WorldDisasterResponse,
    WorldEventRead,
    WorldResetRequest,
    WorldRoadRead,
    WorldSettlementDetailRead,
    WorldSettlementRead,
    WorldSimStateRead,
    WorldStatsRead,
    WorldTickRequest,
    WorldTickResponse,
)

__all__ = [
    "ActivityEventRead",
    "ActivityResponse",
    "ArchitectureNode",
    "BuildLogRead",
    "BuildTrigger",
    "ChatMessageCreate",
    "ChatMessageRead",
    "ComponentStatusRead",
    "FeatureMatrix",
    "GalaxyGraph",
    "GalaxyLink",
    "GalaxyNode",
    "GitCommitRead",
    "JobEnvelope",
    "JobStatus",
    "KnowledgeSummaryRead",
    "OllamaRecentQuery",
    "OllamaStatusRead",
    "PortfolioCandidate",
    "PortfolioScoreRead",
    "PortfolioSummary",
    "ProjectFileRead",
    "ProjectList",
    "ProjectRead",
    "RagIndexRequest",
    "RagQueryRequest",
    "RagResponse",
    "RagResult",
    "RagSearchRequest",
    "RagSearchResponse",
    "ScanResponse",
    "SecurityClearRead",
    "SecurityFindingCreate",
    "SecurityFindingRead",
    "SessionCheckpointCreate",
    "SessionCheckpointRead",
    "SessionCreate",
    "SessionEndRequest",
    "SessionExportRead",
    "SessionRead",
    "SessionScreenshotCreate",
    "SessionScreenshotRead",
    "SessionUpdate",
    "SyncLastRun",
    "SyncStatusRead",
    "SystemOverview",
    "TestResultRead",
    "TestRunResponse",
    "TesterDescriptor",
    "TesterRunRequest",
    "Timeline",
    "TimelineEvent",
    "TriageEvidence",
    "TriageFrame",
    "TriageRead",
    "TriageSourceLine",
    "WorldAccelerateRequest",
    "WorldDisasterRequest",
    "WorldDisasterResponse",
    "WorldEventRead",
    "WorldResetRequest",
    "WorldRoadRead",
    "WorldSettlementDetailRead",
    "WorldSettlementRead",
    "WorldSimStateRead",
    "WorldStatsRead",
    "WorldTickRequest",
    "WorldTickResponse",
    "build_status_from_log",
]
