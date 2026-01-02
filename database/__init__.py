"""
Doppelganger Tracker - Database Module
======================================
Database models, DTOs, and session management.
"""

from .models import (
    # Engine and session
    get_engine,
    get_session,
    init_db,
    drop_db,
    Base,
    
    # Models
    Source,
    Content,
    Propagation,
    NLPAnalysis,
    CognitiveMarker,
    Factcheck,
    Domain,
    Narrative,
    ContentNarrative,
    CollectionRun,
)

from .dto import (
    # Enums
    SourceType,
    ContentType,
    SentimentLabel,
    Severity,
    PropagationType,
    MutationType,
    
    # DTOs
    SourceDTO,
    ContentDTO,
    EntityDTO,
    SentimentResult,
    NLPAnalysisResult,
    CognitiveMarkerDTO,
    NarrativeMatch,
    PropagationLink,
    SimilarContentMatch,
    NetworkNode,
    NetworkEdge,
    SuperspreaderInfo,
    NetworkStats,
    CoordinatedBehaviorEvent,
    CollectionResult,
    AnalysisResult,
    DashboardStats,
    TimelineDataPoint,
    AlertInfo,
    TelegramChannelConfig,
    RSSFeedConfig,
)

__all__ = [
    # Engine and session
    "get_engine",
    "get_session",
    "init_db",
    "drop_db",
    "Base",
    
    # Models
    "Source",
    "Content",
    "Propagation",
    "NLPAnalysis",
    "CognitiveMarker",
    "Factcheck",
    "Domain",
    "Narrative",
    "ContentNarrative",
    "CollectionRun",
    
    # Enums
    "SourceType",
    "ContentType",
    "SentimentLabel",
    "Severity",
    "PropagationType",
    "MutationType",
    
    # DTOs
    "SourceDTO",
    "ContentDTO",
    "EntityDTO",
    "SentimentResult",
    "NLPAnalysisResult",
    "CognitiveMarkerDTO",
    "NarrativeMatch",
    "PropagationLink",
    "SimilarContentMatch",
    "NetworkNode",
    "NetworkEdge",
    "SuperspreaderInfo",
    "NetworkStats",
    "CoordinatedBehaviorEvent",
    "CollectionResult",
    "AnalysisResult",
    "DashboardStats",
    "TimelineDataPoint",
    "AlertInfo",
    "TelegramChannelConfig",
    "RSSFeedConfig",
]
