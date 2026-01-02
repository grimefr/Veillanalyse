"""
Doppelganger Tracker - Database Models
======================================
SQLAlchemy 2.0 ORM models for PostgreSQL database.
Defines all entities for tracking disinformation content.

Models:
    - Source: Content sources (Telegram channels, domains, media)
    - Content: Collected articles, posts, messages
    - Propagation: Links between related content
    - NLPAnalysis: NLP processing results
    - CognitiveMarker: Detected manipulation markers
    - Factcheck: Fact-checking records
    - Domain: Tracked domains (typosquatting)
    - Narrative: Tracked narrative themes
    - ContentNarrative: Many-to-many link
    - CollectionRun: Collection execution logs
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, List, Any
from uuid import uuid4
from dataclasses import dataclass, field

from sqlalchemy import (
    create_engine, Column, String, Text, Boolean, Integer, Float,
    DateTime, ForeignKey, ARRAY, BigInteger, Index, UniqueConstraint, CheckConstraint,
    event
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
    sessionmaker, Session
)
from sqlalchemy.pool import QueuePool

from config.settings import settings


# =============================================================================
# DATABASE ENGINE & SESSION
# =============================================================================

def get_engine():
    """
    Create SQLAlchemy engine with connection pooling.
    
    Returns:
        Engine: Configured SQLAlchemy engine
    """
    return create_engine(
        settings.get_database_url(),
        poolclass=QueuePool,
        pool_size=20,              # Increased from 5 for production use
        max_overflow=30,           # Increased from 10 to handle burst traffic
        pool_timeout=30,           # Wait time for connection acquisition
        pool_recycle=3600,         # Recycle connections after 1 hour
        pool_pre_ping=True,        # Check connection health before use
        echo=settings.debug,
        echo_pool=settings.debug   # Log pool events in debug mode
    )


# Create engine and session factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """
    Get a new database session.
    
    Returns:
        Session: SQLAlchemy session instance
        
    Example:
        session = get_session()
        try:
            # ... database operations
            session.commit()
        finally:
            session.close()
    """
    return SessionLocal()


# =============================================================================
# BASE MODEL
# =============================================================================

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


# =============================================================================
# MODELS
# =============================================================================

class Source(Base):
    """
    Content source entity (Telegram channel, domain, media outlet).
    
    Attributes:
        id: Unique identifier (UUID)
        name: Source display name
        source_type: Type category (telegram, domain, media, factcheck)
        platform: Platform identifier (telegram, x, facebook, web)
        url: Source URL if applicable
        telegram_channel_id: Telegram channel ID (BigInt for large IDs)
        language: Primary language code (fr, en, ru)
        is_doppelganger: Flag for confirmed Doppelganger sources
        is_amplifier: Flag for known amplifier accounts
        is_factchecker: Flag for fact-checking sources
        is_active: Whether source is being actively collected
        first_seen_at: First observation timestamp
        last_collected_at: Last successful collection timestamp
        created_at: Record creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "sources"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), 
        primary_key=True, 
        default=generate_uuid
    )
    
    # Identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Metadata
    url: Mapped[Optional[str]] = mapped_column(Text)
    telegram_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    
    # Classification flags
    is_doppelganger: Mapped[bool] = mapped_column(Boolean, default=False)
    is_amplifier: Mapped[bool] = mapped_column(Boolean, default=False)
    is_factchecker: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    contents: Mapped[List["Content"]] = relationship(
        "Content", 
        back_populates="source",
        lazy="dynamic"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_sources_type", "source_type"),
        Index("idx_sources_language", "language"),
        Index("idx_sources_telegram_id", "telegram_channel_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Source(name='{self.name}', type='{self.source_type}')>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "platform": self.platform,
            "language": self.language,
            "is_doppelganger": self.is_doppelganger,
            "is_amplifier": self.is_amplifier,
            "is_active": self.is_active
        }


class Content(Base):
    """
    Collected content entity (article, post, message).
    
    Attributes:
        id: Unique identifier (UUID)
        source_id: Reference to source
        external_id: Original platform ID
        content_type: Type (article, post, message, forward)
        title: Content title if available
        text_content: Full text content
        text_hash: SHA256 hash for deduplication
        has_media: Whether content includes media
        media_urls: Array of media URLs
        media_types: Array of media type identifiers
        url: Original content URL
        author: Author name/handle
        author_id: Author platform ID
        language: Detected language code
        views_count: View/impression count
        shares_count: Share/repost count
        comments_count: Comment count
        reactions_count: Reaction/like count
        published_at: Original publication time
        collected_at: Collection timestamp
        is_analyzed: Whether NLP analysis completed
        analysis_version: Analysis version number
    """
    
    __tablename__ = "content"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    # Source reference
    source_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    
    # Identification
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Content
    title: Mapped[Optional[str]] = mapped_column(Text)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Media
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    media_urls: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    media_types: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String(50)))
    
    # Metadata
    url: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    author_id: Mapped[Optional[str]] = mapped_column(String(255))
    language: Mapped[Optional[str]] = mapped_column(String(10))
    
    # Engagement metrics
    views_count: Mapped[Optional[int]] = mapped_column(Integer)
    shares_count: Mapped[Optional[int]] = mapped_column(Integer)
    comments_count: Mapped[Optional[int]] = mapped_column(Integer)
    reactions_count: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    # Analysis status
    is_analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_version: Mapped[int] = mapped_column(Integer, default=0)
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Table arguments for indexes
    __table_args__ = (
        # Individual indexes for frequently queried columns
        Index('ix_content_source_id', 'source_id'),
        Index('ix_content_collected_at', 'collected_at'),
        Index('ix_content_published_at', 'published_at'),
        Index('ix_content_language', 'language'),
        Index('ix_content_is_analyzed', 'is_analyzed'),

        # Composite indexes for common query patterns
        Index('ix_content_source_collected', 'source_id', 'collected_at'),
        Index('ix_content_source_published', 'source_id', 'published_at'),
        Index('ix_content_analyzed_version', 'is_analyzed', 'analysis_version'),

        # Partial index for unanalyzed content (PostgreSQL specific)
        Index(
            'ix_content_unanalyzed',
            'id', 'collected_at',
            postgresql_where=(is_analyzed == False)
        ),
    )

    # Relationships
    source: Mapped[Optional["Source"]] = relationship(
        "Source",
        back_populates="contents"
    )
    nlp_analysis: Mapped[Optional["NLPAnalysis"]] = relationship(
        "NLPAnalysis",
        back_populates="content",
        uselist=False,
        cascade="all, delete-orphan"
    )
    cognitive_markers: Mapped[List["CognitiveMarker"]] = relationship(
        "CognitiveMarker",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    factchecks: Mapped[List["Factcheck"]] = relationship(
        "Factcheck",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_content_published", "published_at"),
        Index("idx_content_type", "content_type"),
        Index("idx_content_language", "language"),
        Index("idx_content_analyzed", "is_analyzed"),
    )
    
    def __repr__(self) -> str:
        return f"<Content(id='{self.id[:8]}...', type='{self.content_type}')>"
    
    @staticmethod
    def compute_hash(text: str) -> str:
        """
        Compute SHA256 hash for text content.
        
        Args:
            text: Text to hash
            
        Returns:
            str: Hexadecimal hash string
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "content_type": self.content_type,
            "language": self.language,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "is_analyzed": self.is_analyzed
        }


class Propagation(Base):
    """
    Propagation link between content items.
    
    Tracks how content spreads between sources, including
    mutations and time delays.
    
    Attributes:
        id: Unique identifier
        source_content_id: Original content ID
        target_content_id: Propagated content ID
        propagation_type: Type (forward, quote, repost, mention, link, similar)
        similarity_score: Text similarity (0.0-1.0)
        mutation_detected: Whether content was modified
        mutation_type: Type of mutation detected
        mutation_description: Details of detected changes
        time_delta_seconds: Time between source and target
    """
    
    __tablename__ = "propagation"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    # Content references
    source_content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False
    )
    target_content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Type classification
    propagation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Similarity analysis
    similarity_score: Mapped[Optional[float]] = mapped_column(Float)
    mutation_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    mutation_type: Mapped[Optional[str]] = mapped_column(String(50))
    mutation_description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timing
    time_delta_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    __table_args__ = (
        # Individual indexes
        Index("idx_propagation_source", "source_content_id"),
        Index("idx_propagation_target", "target_content_id"),
        Index("idx_propagation_type", "propagation_type"),
        Index("idx_propagation_created", "created_at"),

        # Composite indexes for common queries
        Index(
            "idx_propagation_source_similarity",
            "source_content_id",
            "similarity_score",
            postgresql_ops={'similarity_score': 'DESC'}
        ),
        Index(
            "idx_propagation_target_similarity",
            "target_content_id",
            "similarity_score",
            postgresql_ops={'similarity_score': 'DESC'}
        ),
        Index("idx_propagation_source_created", "source_content_id", "created_at"),

        # Unique constraint
        UniqueConstraint("source_content_id", "target_content_id", name="uq_propagation_link"),
    )
    
    def __repr__(self) -> str:
        return f"<Propagation(type='{self.propagation_type}', similarity={self.similarity_score:.2f})>"


class NLPAnalysis(Base):
    """
    NLP analysis results for content.
    
    Stores sentiment analysis, entity extraction, and
    propaganda classification results.
    
    Attributes:
        id: Unique identifier
        content_id: Reference to analyzed content
        sentiment_score: Sentiment value (-1.0 to 1.0)
        sentiment_label: Categorical sentiment (positive, negative, neutral)
        sentiment_confidence: Confidence in sentiment classification
        entities: Extracted named entities (JSONB)
        keywords: Extracted keywords
        topics: Detected topics
        embedding: Text embedding vector
        is_propaganda: Propaganda classification
        propaganda_confidence: Propaganda detection confidence
        propaganda_techniques: Detected manipulation techniques
        detected_language: Detected language code
        language_confidence: Language detection confidence
        analyzed_at: Analysis timestamp
        model_version: Model version used
    """
    
    __tablename__ = "nlp_analysis"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("content.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    
    # Sentiment analysis
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(20))
    sentiment_confidence: Mapped[Optional[float]] = mapped_column(Float)
    
    # Entity extraction
    entities: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Keywords and topics
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    topics: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    
    # Embeddings
    embedding: Mapped[Optional[List[float]]] = mapped_column(ARRAY(Float))
    
    # Propaganda classification
    is_propaganda: Mapped[Optional[bool]] = mapped_column(Boolean)
    propaganda_confidence: Mapped[Optional[float]] = mapped_column(Float)
    propaganda_techniques: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    
    # Language detection
    detected_language: Mapped[Optional[str]] = mapped_column(String(10))
    language_confidence: Mapped[Optional[float]] = mapped_column(Float)
    
    # Metadata
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    model_version: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Relationship
    content: Mapped["Content"] = relationship(
        "Content",
        back_populates="nlp_analysis"
    )
    
    __table_args__ = (
        # Individual indexes
        Index("idx_nlp_propaganda", "is_propaganda"),
        Index("idx_nlp_sentiment", "sentiment_label"),
        Index("idx_nlp_analyzed_at", "analyzed_at"),
        Index("idx_nlp_language", "detected_language"),

        # Composite indexes for common queries
        Index("idx_nlp_propaganda_analyzed", "is_propaganda", "analyzed_at"),
        Index("idx_nlp_propaganda_confidence", "is_propaganda", "propaganda_confidence",
              postgresql_ops={'propaganda_confidence': 'DESC'}),
        Index("idx_nlp_sentiment_analyzed", "sentiment_label", "analyzed_at"),

        # Check constraints for data validation
        CheckConstraint(
            'sentiment_score >= -1.0 AND sentiment_score <= 1.0',
            name='ck_nlp_sentiment_range'
        ),
        CheckConstraint(
            'sentiment_confidence >= 0.0 AND sentiment_confidence <= 1.0',
            name='ck_nlp_sentiment_conf_range'
        ),
        CheckConstraint(
            'propaganda_confidence >= 0.0 AND propaganda_confidence <= 1.0',
            name='ck_nlp_propaganda_conf_range'
        ),
        CheckConstraint(
            'language_confidence >= 0.0 AND language_confidence <= 1.0',
            name='ck_nlp_language_conf_range'
        ),
    )
    
    def __repr__(self) -> str:
        return f"<NLPAnalysis(sentiment='{self.sentiment_label}', propaganda={self.is_propaganda})>"


class CognitiveMarker(Base):
    """
    Detected cognitive warfare marker.
    
    Records manipulation techniques and propaganda
    indicators found in content.
    
    Attributes:
        id: Unique identifier
        content_id: Reference to content
        marker_type: Specific marker type identifier
        marker_category: Broad category (DISARM phase)
        confidence: Detection confidence (0.0-1.0)
        severity: Severity level (low, medium, high)
        evidence_text: Text evidence for marker
        evidence_start: Start position in text
        evidence_end: End position in text
        context_notes: Additional context
        detected_at: Detection timestamp
        detector_version: Detector version used
    """
    
    __tablename__ = "cognitive_markers"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Marker identification
    marker_type: Mapped[str] = mapped_column(String(100), nullable=False)
    marker_category: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Scoring
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Evidence
    evidence_text: Mapped[Optional[str]] = mapped_column(Text)
    evidence_start: Mapped[Optional[int]] = mapped_column(Integer)
    evidence_end: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Context
    context_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    detector_version: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Relationship
    content: Mapped["Content"] = relationship(
        "Content",
        back_populates="cognitive_markers"
    )
    
    __table_args__ = (
        Index("idx_markers_type", "marker_type"),
        Index("idx_markers_category", "marker_category"),
        Index("idx_markers_severity", "severity"),
    )
    
    def __repr__(self) -> str:
        return f"<CognitiveMarker(type='{self.marker_type}', severity='{self.severity}')>"


class Factcheck(Base):
    """
    Fact-checking record for content.
    
    Attributes:
        id: Unique identifier
        content_id: Reference to checked content
        claim_text: The claim being checked
        verdict: Fact-check verdict
        verdict_details: Detailed explanation
        factcheck_source: Source of fact-check
        factcheck_url: URL to fact-check article
        factcheck_date: Date of fact-check
    """
    
    __tablename__ = "factchecks"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    content_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("content.id", ondelete="SET NULL")
    )
    
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    verdict_details: Mapped[Optional[str]] = mapped_column(Text)
    
    # Source info
    factcheck_source: Mapped[Optional[str]] = mapped_column(String(255))
    factcheck_url: Mapped[Optional[str]] = mapped_column(Text)
    factcheck_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    # Relationship
    content: Mapped[Optional["Content"]] = relationship(
        "Content",
        back_populates="factchecks"
    )
    
    __table_args__ = (
        Index("idx_factchecks_verdict", "verdict"),
    )


class Domain(Base):
    """
    Tracked domain for typosquatting detection.
    
    Attributes:
        id: Unique identifier
        domain: Domain name
        tld: Top-level domain
        impersonates: Legitimate domain being impersonated
        similarity_score: Similarity to legitimate domain
        typosquat_type: Type of typosquatting technique
        is_active: Whether domain is currently active
        first_seen_at: First observation
        last_seen_at: Most recent observation
        ip_addresses: Known IP addresses
        hosting_provider: Hosting provider name
        ssl_issuer: SSL certificate issuer
        is_confirmed_doppelganger: Confirmed attribution
        attribution_source: Source of attribution
    """
    
    __tablename__ = "domains"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tld: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Typosquatting analysis
    impersonates: Mapped[Optional[str]] = mapped_column(String(255))
    similarity_score: Mapped[Optional[float]] = mapped_column(Float)
    typosquat_type: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Technical info
    ip_addresses: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String(45)))
    hosting_provider: Mapped[Optional[str]] = mapped_column(String(255))
    ssl_issuer: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Classification
    is_confirmed_doppelganger: Mapped[bool] = mapped_column(Boolean, default=False)
    attribution_source: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    __table_args__ = (
        Index("idx_domains_impersonates", "impersonates"),
    )


class Narrative(Base):
    """
    Tracked narrative/theme.
    
    Attributes:
        id: Unique identifier
        name: Narrative name
        description: Detailed description
        category: Broad category
        subcategory: Specific subcategory
        first_seen_at: First detection
        last_seen_at: Most recent detection
        content_count: Number of associated content items
        keywords: Associated keywords
        example_claims: Example claims for this narrative
        is_active: Whether actively tracking
    """
    
    __tablename__ = "narratives"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Classification
    category: Mapped[Optional[str]] = mapped_column(String(100))
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Tracking
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    content_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Analysis
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    example_claims: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class ContentNarrative(Base):
    """
    Many-to-many association between Content and Narrative.
    """
    
    __tablename__ = "content_narratives"
    
    content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("content.id", ondelete="CASCADE"),
        primary_key=True
    )
    narrative_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("narratives.id", ondelete="CASCADE"),
        primary_key=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )


class CollectionRun(Base):
    """
    Collection execution log.
    
    Tracks each collection run for monitoring and debugging.
    
    Attributes:
        id: Unique identifier
        collector_type: Type of collector (telegram, media)
        started_at: Start timestamp
        finished_at: End timestamp
        status: Execution status
        items_collected: Total items processed
        items_new: New items added
        items_updated: Existing items updated
        errors_count: Number of errors
        error_messages: Error details
        metadata: Additional metadata
    """
    
    __tablename__ = "collection_runs"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid
    )
    
    collector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Results
    status: Mapped[str] = mapped_column(String(20), default="running")
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Details
    error_messages: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    __table_args__ = (
        Index("idx_runs_type", "collector_type"),
        Index("idx_runs_status", "status"),
    )
    
    def mark_completed(self, items_new: int = 0, items_updated: int = 0):
        """Mark run as completed."""
        self.status = "completed"
        self.finished_at = datetime.utcnow()
        self.items_new = items_new
        self.items_updated = items_updated
    
    def mark_failed(self, error: str):
        """Mark run as failed."""
        self.status = "failed"
        self.finished_at = datetime.utcnow()
        self.errors_count += 1
        if self.error_messages is None:
            self.error_messages = []
        self.error_messages.append(error)


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_db():
    """
    Initialize database tables.
    
    Creates all tables defined in models if they don't exist.
    """
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    Drop all database tables.
    
    Warning: This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")
