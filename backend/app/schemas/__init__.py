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
from app.schemas.git import FeatureTimelineItem, GitCommitRead
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
from app.schemas.portfolio import FeatureMatrix, PortfolioCandidate, PortfolioScoreRead
from app.schemas.project import (
    ProjectDetail,
    ProjectFileRead,
    ProjectHealth,
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
    SecurityFindingCreate,
    SecurityFindingRead,
)
from app.schemas.test import TestResultRead, TestRunResponse
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
    "ArchitectureNode",
    "BuildLogRead",
    "BuildTrigger",
    "FeatureMatrix",
    "FeatureTimelineItem",
    "GalaxyGraph",
    "GalaxyLink",
    "GalaxyNode",
    "GitCommitRead",
    "JobEnvelope",
    "JobStatus",
    "KnowledgeSummaryRead",
    "PortfolioCandidate",
    "PortfolioScoreRead",
    "ProjectDetail",
    "ProjectFileRead",
    "ProjectHealth",
    "ProjectList",
    "ProjectRead",
    "RagIndexRequest",
    "RagQueryRequest",
    "RagResponse",
    "RagResult",
    "RagSearchRequest",
    "RagSearchResponse",
    "ScanResponse",
    "SecurityFindingCreate",
    "SecurityFindingRead",
    "TestResultRead",
    "TestRunResponse",
    "Timeline",
    "TimelineEvent",
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
