"""
Doppelganger Tracker - Data Transfer Objects
=============================================
Dataclasses for type-safe data transfer between layers.
These are decoupled from SQLAlchemy models for flexibility.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class SourceType(str, Enum):
    """Source type categories."""
    TELEGRAM = "telegram"
    DOMAIN = "domain"
    MEDIA = "media"
    FACTCHECK = "factcheck"
    SOCIAL = "social"


class ContentType(str, Enum):
    """Content type categories."""
    ARTICLE = "article"
    POST = "post"
    MESSAGE = "message"
    FORWARD = "forward"
    COMMENT = "comment"


class SentimentLabel(str, Enum):
    """Sentiment classification labels."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Severity(str, Enum):
    """Severity levels for markers."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PropagationType(str, Enum):
    """Types of content propagation."""
    FORWARD = "forward"
    QUOTE = "quote"
    REPOST = "repost"
    MENTION = "mention"
    LINK = "link"
    SIMILAR = "similar"


class MutationType(str, Enum):
    """Types of content mutation during propagation."""
    NONE = "none"
    AMPLIFICATION = "amplification"
    DISTORTION = "distortion"
    SIGNIFICANT_CHANGE = "significant_change"


# =============================================================================
# SOURCE DTOs
# =============================================================================

@dataclass
class SourceDTO:
    """
    Data transfer object for Source entities.
    
    Attributes:
        id: Unique identifier
        name: Display name
        source_type: Type category
        platform: Platform identifier
        url: Source URL
        language: Primary language code
        is_doppelganger: Doppelganger flag
        is_amplifier: Amplifier flag
        is_active: Active status
        content_count: Number of collected items
    """
    name: str
    source_type: SourceType
    id: Optional[str] = None
    platform: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    is_doppelganger: bool = False
    is_amplifier: bool = False
    is_factchecker: bool = False
    is_active: bool = True
    content_count: int = 0
    telegram_channel_id: Optional[int] = None
    first_seen_at: Optional[datetime] = None
    last_collected_at: Optional[datetime] = None


@dataclass
class TelegramChannelConfig:
    """
    Configuration for a Telegram channel to monitor.
    
    Attributes:
        name: Display name
        channel: Channel username (with @)
        language: Content language
        channel_type: Classification type
        priority: Collection priority
    """
    name: str
    channel: str
    language: str = "unknown"
    channel_type: str = "monitor"
    priority: str = "medium"


@dataclass
class RSSFeedConfig:
    """
    Configuration for an RSS feed to monitor.
    
    Attributes:
        name: Display name
        url: Feed URL
        language: Content language
        feed_type: Classification type
    """
    name: str
    url: str
    language: str = "unknown"
    feed_type: str = "media"


# =============================================================================
# CONTENT DTOs
# =============================================================================

@dataclass
class ContentDTO:
    """
    Data transfer object for Content entities.
    
    Attributes:
        text_content: Full text
        content_type: Content type
        id: Unique identifier
        source_id: Reference to source
        title: Title if available
        url: Original URL
        language: Detected language
        published_at: Publication time
        is_analyzed: Analysis status
    """
    text_content: str
    content_type: ContentType
    id: Optional[str] = None
    source_id: Optional[str] = None
    external_id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None
    has_media: bool = False
    media_urls: List[str] = field(default_factory=list)
    views_count: Optional[int] = None
    shares_count: Optional[int] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    is_analyzed: bool = False


@dataclass
class ContentSearchResult:
    """
    Search result with relevance score.
    """
    content: ContentDTO
    relevance_score: float
    matched_terms: List[str] = field(default_factory=list)


# =============================================================================
# ANALYSIS DTOs
# =============================================================================

@dataclass
class EntityDTO:
    """
    Named entity extracted from text.
    
    Attributes:
        text: Entity text
        entity_type: Entity type (PERSON, ORG, GPE, etc.)
        start: Start position in text
        end: End position in text
        confidence: Extraction confidence
    """
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class SentimentResult:
    """
    Sentiment analysis result.
    
    Attributes:
        score: Sentiment score (-1.0 to 1.0)
        label: Categorical label
        confidence: Classification confidence
    """
    score: float
    label: SentimentLabel
    confidence: float


@dataclass
class NLPAnalysisResult:
    """
    Complete NLP analysis result.
    
    Attributes:
        content_id: Analyzed content ID
        sentiment: Sentiment analysis result
        entities: Extracted entities
        keywords: Extracted keywords
        detected_language: Detected language
        language_confidence: Detection confidence
        is_propaganda: Propaganda classification
        propaganda_confidence: Classification confidence
        propaganda_techniques: Detected techniques
    """
    content_id: str
    sentiment: SentimentResult
    entities: List[EntityDTO]
    keywords: List[str]
    detected_language: str
    language_confidence: float
    is_propaganda: bool = False
    propaganda_confidence: float = 0.0
    propaganda_techniques: List[str] = field(default_factory=list)


@dataclass
class CognitiveMarkerDTO:
    """
    Detected cognitive warfare marker.
    
    Attributes:
        marker_type: Specific marker type
        marker_category: DISARM phase category
        confidence: Detection confidence
        severity: Severity level
        evidence_text: Supporting text evidence
        evidence_start: Start position
        evidence_end: End position
    """
    marker_type: str
    marker_category: str
    confidence: float
    severity: Severity = Severity.MEDIUM
    evidence_text: Optional[str] = None
    evidence_start: Optional[int] = None
    evidence_end: Optional[int] = None


@dataclass
class NarrativeMatch:
    """
    Detected narrative match.
    
    Attributes:
        narrative_id: Narrative identifier
        narrative_name: Narrative display name
        confidence: Match confidence
        matched_keywords: Keywords that matched
    """
    narrative_id: str
    narrative_name: str
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)


# =============================================================================
# PROPAGATION DTOs
# =============================================================================

@dataclass
class PropagationLink:
    """
    Link between propagated content.
    
    Attributes:
        source_content_id: Original content
        target_content_id: Propagated content
        propagation_type: Type of propagation
        similarity_score: Text similarity
        mutation_detected: Whether mutation occurred
        mutation_type: Type of mutation
        time_delta_seconds: Time between posts
    """
    source_content_id: str
    target_content_id: str
    propagation_type: PropagationType
    similarity_score: float
    mutation_detected: bool = False
    mutation_type: Optional[MutationType] = None
    time_delta_seconds: Optional[int] = None


@dataclass
class SimilarContentMatch:
    """
    Similar content match result.
    """
    content_id: str
    similarity_score: float
    time_delta_seconds: int
    mutation_type: Optional[MutationType] = None


# =============================================================================
# NETWORK DTOs
# =============================================================================

@dataclass
class NetworkNode:
    """
    Node in the propagation network.
    
    Attributes:
        id: Node identifier
        name: Display name
        node_type: Node type (source, content)
        attributes: Additional attributes
    """
    id: str
    name: str
    node_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkEdge:
    """
    Edge in the propagation network.
    
    Attributes:
        source_id: Source node ID
        target_id: Target node ID
        weight: Edge weight
        edge_type: Edge type
        attributes: Additional attributes
    """
    source_id: str
    target_id: str
    weight: float = 1.0
    edge_type: str = "propagation"
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SuperspreaderInfo:
    """
    Information about a superspreader node.
    
    Attributes:
        id: Node identifier
        name: Display name
        source_type: Source type
        out_degree: Outgoing connections
        pagerank: PageRank score
        betweenness: Betweenness centrality
        score: Combined score
        is_doppelganger: Doppelganger flag
    """
    id: str
    name: str
    source_type: str
    out_degree: int
    pagerank: float
    betweenness: float
    score: float
    is_doppelganger: bool = False


@dataclass
class NetworkStats:
    """
    Network statistics summary.
    
    Attributes:
        node_count: Number of nodes
        edge_count: Number of edges
        density: Graph density
        community_count: Number of communities
        avg_degree: Average node degree
    """
    node_count: int
    edge_count: int
    density: float
    community_count: int = 0
    avg_degree: float = 0.0
    is_connected: bool = False


@dataclass
class CoordinatedBehaviorEvent:
    """
    Detected coordinated behavior event.
    
    Attributes:
        timestamp: Event timestamp
        content_count: Number of related content
        unique_sources: Number of unique sources
        window_seconds: Time window in seconds
        content_ids: IDs of involved content
    """
    timestamp: datetime
    content_count: int
    unique_sources: int
    window_seconds: int
    content_ids: List[str] = field(default_factory=list)


# =============================================================================
# COLLECTION DTOs
# =============================================================================

@dataclass
class CollectionResult:
    """
    Result of a collection run.
    
    Attributes:
        run_id: Collection run identifier
        collector_type: Type of collector
        status: Completion status
        items_collected: Total items processed
        items_new: New items added
        errors_count: Number of errors
        duration_seconds: Run duration
        error_messages: Error details
    """
    run_id: str
    collector_type: str
    status: str
    items_collected: int = 0
    items_new: int = 0
    items_updated: int = 0
    errors_count: int = 0
    duration_seconds: float = 0.0
    error_messages: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """
    Result of an analysis run.
    
    Attributes:
        timestamp: Analysis timestamp
        analyzed_count: Items analyzed
        errors_count: Errors encountered
        remaining_count: Items remaining
        duration_seconds: Run duration
    """
    timestamp: datetime
    analyzed_count: int
    errors_count: int = 0
    remaining_count: int = 0
    duration_seconds: float = 0.0


# =============================================================================
# REPORT DTOs
# =============================================================================

@dataclass
class DashboardStats:
    """
    Dashboard statistics summary.
    
    Attributes:
        total_content: Total content items
        total_sources: Total sources
        analyzed_content: Analyzed content count
        doppelganger_sources: Doppelganger source count
        propaganda_detected: Propaganda content count
        cognitive_markers: Total markers detected
        factchecks: Fact-check count
    """
    total_content: int = 0
    total_sources: int = 0
    analyzed_content: int = 0
    doppelganger_sources: int = 0
    propaganda_detected: int = 0
    cognitive_markers: int = 0
    factchecks: int = 0


@dataclass
class TimelineDataPoint:
    """
    Data point for timeline visualization.
    """
    date: datetime
    count: int
    category: str = "all"


@dataclass
class AlertInfo:
    """
    Alert information for detected issues.
    
    Attributes:
        alert_type: Type of alert
        severity: Alert severity
        content_id: Related content ID
        title: Alert title
        description: Alert description
        detected_at: Detection timestamp
    """
    alert_type: str
    severity: Severity
    title: str
    description: str
    content_id: Optional[str] = None
    detected_at: Optional[datetime] = None
