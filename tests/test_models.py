"""
Doppelganger Tracker - Database Model Tests
============================================
Unit tests for database models and DTOs.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from database.models import (
    Source, Content, Propagation, NLPAnalysis,
    CognitiveMarker, Factcheck, Domain, Narrative,
    ContentNarrative, CollectionRun, generate_uuid
)
from database.dto import (
    SourceType, ContentType, SentimentLabel, Severity,
    PropagationType, MutationType,
    SourceDTO, ContentDTO, EntityDTO, SentimentResult,
    NLPAnalysisResult, CognitiveMarkerDTO, NarrativeMatch,
    PropagationLink, NetworkNode, NetworkStats, DashboardStats
)


class TestGenerateUUID:
    """Tests for UUID generation."""
    
    def test_generate_uuid_returns_string(self):
        """UUID should be returned as string."""
        result = generate_uuid()
        assert isinstance(result, str)
    
    def test_generate_uuid_is_valid_format(self):
        """UUID should have valid format."""
        result = generate_uuid()
        # UUID format: 8-4-4-4-12 hexadecimal characters
        assert len(result) == 36
        assert result.count("-") == 4
    
    def test_generate_uuid_is_unique(self):
        """Each call should generate unique UUID."""
        uuids = [generate_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100


class TestContentModel:
    """Tests for Content model."""
    
    def test_compute_hash_consistent(self):
        """Same text should produce same hash."""
        text = "Test content for hashing"
        hash1 = Content.compute_hash(text)
        hash2 = Content.compute_hash(text)
        assert hash1 == hash2
    
    def test_compute_hash_different_text(self):
        """Different text should produce different hash."""
        hash1 = Content.compute_hash("Text one")
        hash2 = Content.compute_hash("Text two")
        assert hash1 != hash2
    
    def test_compute_hash_length(self):
        """Hash should be 64 characters (SHA256 hex)."""
        result = Content.compute_hash("Any text")
        assert len(result) == 64
    
    def test_compute_hash_handles_unicode(self):
        """Hash should handle unicode text."""
        result = Content.compute_hash("Тест на русском 测试中文")
        assert len(result) == 64


class TestSourceDTO:
    """Tests for SourceDTO dataclass."""
    
    def test_create_minimal(self):
        """Create with minimal required fields."""
        dto = SourceDTO(
            name="Test Source",
            source_type=SourceType.TELEGRAM
        )
        assert dto.name == "Test Source"
        assert dto.source_type == SourceType.TELEGRAM
        assert dto.is_active == True  # Default
    
    def test_create_full(self):
        """Create with all fields."""
        dto = SourceDTO(
            name="Full Source",
            source_type=SourceType.MEDIA,
            id="test-id",
            platform="web",
            url="https://example.com",
            language="en",
            is_doppelganger=True,
            is_amplifier=False,
            is_factchecker=True,
            is_active=False,
            content_count=100,
            telegram_channel_id=123456789
        )
        assert dto.id == "test-id"
        assert dto.is_doppelganger == True
        assert dto.content_count == 100


class TestContentDTO:
    """Tests for ContentDTO dataclass."""
    
    def test_create_minimal(self):
        """Create with minimal required fields."""
        dto = ContentDTO(
            text_content="Test text",
            content_type=ContentType.ARTICLE
        )
        assert dto.text_content == "Test text"
        assert dto.content_type == ContentType.ARTICLE
        assert dto.has_media == False  # Default
        assert dto.media_urls == []  # Default factory
    
    def test_media_urls_default_factory(self):
        """Each instance should have separate media_urls list."""
        dto1 = ContentDTO(text_content="Text 1", content_type=ContentType.POST)
        dto2 = ContentDTO(text_content="Text 2", content_type=ContentType.POST)
        
        dto1.media_urls.append("url1")
        assert "url1" not in dto2.media_urls


class TestEntityDTO:
    """Tests for EntityDTO dataclass."""
    
    def test_create(self):
        """Create entity with all fields."""
        entity = EntityDTO(
            text="Vladimir Putin",
            entity_type="PERSON",
            start=0,
            end=14,
            confidence=0.95
        )
        assert entity.text == "Vladimir Putin"
        assert entity.entity_type == "PERSON"
        assert entity.confidence == 0.95
    
    def test_default_confidence(self):
        """Default confidence should be 1.0."""
        entity = EntityDTO(
            text="Test",
            entity_type="ORG",
            start=0,
            end=4
        )
        assert entity.confidence == 1.0


class TestSentimentResult:
    """Tests for SentimentResult dataclass."""
    
    def test_create(self):
        """Create sentiment result."""
        result = SentimentResult(
            score=-0.5,
            label=SentimentLabel.NEGATIVE,
            confidence=0.85
        )
        assert result.score == -0.5
        assert result.label == SentimentLabel.NEGATIVE
        assert result.confidence == 0.85
    
    def test_sentiment_labels(self):
        """Test all sentiment label values."""
        assert SentimentLabel.POSITIVE.value == "positive"
        assert SentimentLabel.NEGATIVE.value == "negative"
        assert SentimentLabel.NEUTRAL.value == "neutral"


class TestCognitiveMarkerDTO:
    """Tests for CognitiveMarkerDTO dataclass."""
    
    def test_create_minimal(self):
        """Create with minimal fields."""
        marker = CognitiveMarkerDTO(
            marker_type="emotional_appeal",
            marker_category="manipulation",
            confidence=0.7
        )
        assert marker.severity == Severity.MEDIUM  # Default
    
    def test_severity_levels(self):
        """Test severity level values."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"


class TestPropagationLink:
    """Tests for PropagationLink dataclass."""
    
    def test_create(self):
        """Create propagation link."""
        link = PropagationLink(
            source_content_id="source-id",
            target_content_id="target-id",
            propagation_type=PropagationType.FORWARD,
            similarity_score=0.95,
            mutation_detected=False
        )
        assert link.propagation_type == PropagationType.FORWARD
        assert link.similarity_score == 0.95
    
    def test_with_mutation(self):
        """Create link with mutation."""
        link = PropagationLink(
            source_content_id="src",
            target_content_id="tgt",
            propagation_type=PropagationType.SIMILAR,
            similarity_score=0.6,
            mutation_detected=True,
            mutation_type=MutationType.DISTORTION,
            time_delta_seconds=3600
        )
        assert link.mutation_detected == True
        assert link.mutation_type == MutationType.DISTORTION


class TestNetworkStats:
    """Tests for NetworkStats dataclass."""
    
    def test_create(self):
        """Create network statistics."""
        stats = NetworkStats(
            node_count=100,
            edge_count=250,
            density=0.05,
            community_count=5,
            avg_degree=5.0,
            is_connected=True
        )
        assert stats.node_count == 100
        assert stats.density == 0.05
        assert stats.is_connected == True


class TestDashboardStats:
    """Tests for DashboardStats dataclass."""
    
    def test_default_values(self):
        """All fields should default to 0."""
        stats = DashboardStats()
        assert stats.total_content == 0
        assert stats.total_sources == 0
        assert stats.propaganda_detected == 0


class TestEnums:
    """Tests for enum values."""
    
    def test_source_type_values(self):
        """Verify source type enum values."""
        assert SourceType.TELEGRAM.value == "telegram"
        assert SourceType.DOMAIN.value == "domain"
        assert SourceType.MEDIA.value == "media"
        assert SourceType.FACTCHECK.value == "factcheck"
    
    def test_content_type_values(self):
        """Verify content type enum values."""
        assert ContentType.ARTICLE.value == "article"
        assert ContentType.POST.value == "post"
        assert ContentType.MESSAGE.value == "message"
        assert ContentType.FORWARD.value == "forward"
    
    def test_propagation_type_values(self):
        """Verify propagation type enum values."""
        assert PropagationType.FORWARD.value == "forward"
        assert PropagationType.SIMILAR.value == "similar"
        assert PropagationType.REPOST.value == "repost"
    
    def test_mutation_type_values(self):
        """Verify mutation type enum values."""
        assert MutationType.NONE.value == "none"
        assert MutationType.AMPLIFICATION.value == "amplification"
        assert MutationType.DISTORTION.value == "distortion"
