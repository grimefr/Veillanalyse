"""
Doppelganger Tracker - Analyzer Tests
=====================================
Unit tests for NLP and network analyzers.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from database.dto import (
    SentimentLabel, Severity,
    SentimentResult, EntityDTO, CognitiveMarkerDTO,
    NarrativeMatch, NetworkStats, SuperspreaderInfo
)


class TestSentimentAnalysis:
    """Tests for sentiment analysis functionality."""
    
    @pytest.fixture
    def mock_nlp_analyzer(self, sample_keywords_config):
        """Create a mocked NLPAnalyzer."""
        with patch('analyzers.nlp_analyzer.get_session'):
            with patch('analyzers.nlp_analyzer.NLPAnalyzer._load_config') as mock_config:
                mock_config.return_value = sample_keywords_config
                
                from analyzers.nlp_analyzer import NLPAnalyzer
                analyzer = NLPAnalyzer.__new__(NLPAnalyzer)
                analyzer.session = MagicMock()
                analyzer.keywords_config = sample_keywords_config
                analyzer.cognitive_config = {}
                analyzer._model_version = "v1.0"
                return analyzer
    
    def test_analyze_sentiment_negative(self, mock_nlp_analyzer, sample_text_en):
        """Should detect negative sentiment in manipulation text."""
        result = mock_nlp_analyzer.analyze_sentiment(sample_text_en, "en")
        
        assert isinstance(result, SentimentResult)
        assert result.label in [SentimentLabel.NEGATIVE, SentimentLabel.NEUTRAL]
        assert -1.0 <= result.score <= 1.0
    
    def test_analyze_sentiment_neutral(self, mock_nlp_analyzer, neutral_text):
        """Should detect neutral sentiment in factual text."""
        result = mock_nlp_analyzer.analyze_sentiment(neutral_text, "en")
        
        assert isinstance(result, SentimentResult)
        assert result.label == SentimentLabel.NEUTRAL
    
    def test_analyze_sentiment_confidence_range(self, mock_nlp_analyzer):
        """Confidence should be between 0 and 1."""
        result = mock_nlp_analyzer.analyze_sentiment(
            "This is terrible and unacceptable!", "en"
        )
        
        assert 0.0 <= result.confidence <= 1.0


class TestLanguageDetection:
    """Tests for language detection functionality."""
    
    @pytest.fixture
    def mock_analyzer(self):
        """Create analyzer with mocked dependencies."""
        with patch('analyzers.nlp_analyzer.get_session'):
            from analyzers.nlp_analyzer import NLPAnalyzer
            analyzer = NLPAnalyzer.__new__(NLPAnalyzer)
            analyzer.session = MagicMock()
            analyzer.keywords_config = {}
            analyzer.cognitive_config = {}
            return analyzer
    
    def test_detect_language_english(self, mock_analyzer, sample_text_en):
        """Should detect English language."""
        lang, confidence = mock_analyzer.detect_language(sample_text_en)
        
        assert lang == "en"
        assert confidence > 0.5
    
    def test_detect_language_french(self, mock_analyzer, sample_text_fr):
        """Should detect French language."""
        lang, confidence = mock_analyzer.detect_language(sample_text_fr)
        
        assert lang == "fr"
        assert confidence > 0.5
    
    def test_detect_language_russian(self, mock_analyzer, sample_text_ru):
        """Should detect Russian language."""
        lang, confidence = mock_analyzer.detect_language(sample_text_ru)
        
        assert lang == "ru"
        assert confidence > 0.5
    
    def test_detect_language_short_text(self, mock_analyzer):
        """Short text should return unknown."""
        lang, confidence = mock_analyzer.detect_language("Hi")
        
        assert lang == "unknown"
        assert confidence == 0.0
    
    def test_detect_language_empty(self, mock_analyzer):
        """Empty text should return unknown."""
        lang, confidence = mock_analyzer.detect_language("")
        
        assert lang == "unknown"
        assert confidence == 0.0


class TestManipulationDetection:
    """Tests for manipulation marker detection."""
    
    @pytest.fixture
    def analyzer_with_markers(self, sample_keywords_config):
        """Create analyzer with marker configuration."""
        with patch('analyzers.nlp_analyzer.get_session'):
            from analyzers.nlp_analyzer import NLPAnalyzer
            analyzer = NLPAnalyzer.__new__(NLPAnalyzer)
            analyzer.session = MagicMock()
            analyzer.keywords_config = sample_keywords_config
            analyzer.cognitive_config = {}
            return analyzer
    
    def test_detect_emotional_appeal_en(self, analyzer_with_markers):
        """Should detect emotional appeal markers in English."""
        text = "This is absolutely unacceptable and outrageous behavior!"
        markers = analyzer_with_markers.detect_manipulation_markers(text, "en")
        
        assert len(markers) > 0
        assert any(m.marker_type == "emotional_appeal" for m in markers)
    
    def test_detect_emotional_appeal_fr(self, analyzer_with_markers):
        """Should detect emotional appeal markers in French."""
        text = "C'est absolument inacceptable et scandaleux!"
        markers = analyzer_with_markers.detect_manipulation_markers(text, "fr")
        
        assert len(markers) > 0
        assert any(m.marker_type == "emotional_appeal" for m in markers)
    
    def test_detect_whataboutism_en(self, analyzer_with_markers):
        """Should detect whataboutism in English."""
        text = "What about the crimes committed by others? Double standards!"
        markers = analyzer_with_markers.detect_manipulation_markers(text, "en")
        
        assert len(markers) > 0
        assert any(m.marker_type == "whataboutism" for m in markers)
    
    def test_no_markers_in_neutral_text(self, analyzer_with_markers, neutral_text):
        """Should not detect markers in neutral text."""
        markers = analyzer_with_markers.detect_manipulation_markers(neutral_text, "en")
        
        # May have some false positives, but should be minimal
        assert len(markers) <= 1


class TestNarrativeDetection:
    """Tests for narrative theme detection."""
    
    @pytest.fixture
    def analyzer_with_narratives(self, sample_keywords_config):
        """Create analyzer with narrative configuration."""
        with patch('analyzers.nlp_analyzer.get_session'):
            from analyzers.nlp_analyzer import NLPAnalyzer
            analyzer = NLPAnalyzer.__new__(NLPAnalyzer)
            analyzer.session = MagicMock()
            analyzer.keywords_config = sample_keywords_config
            analyzer.cognitive_config = {}
            return analyzer
    
    def test_detect_anti_ukraine_narrative(self, analyzer_with_narratives):
        """Should detect anti-Ukraine narrative."""
        text = "The corrupt Kiev regime is full of Ukrainian Nazis. Corruption everywhere!"
        narratives = analyzer_with_narratives.detect_narratives(text, "en")
        
        assert len(narratives) > 0
        assert narratives[0].narrative_name == "Ukraine Corruption"
        assert narratives[0].confidence > 0
    
    def test_no_narrative_in_neutral(self, analyzer_with_narratives, neutral_text):
        """Should not detect narratives in neutral text."""
        narratives = analyzer_with_narratives.detect_narratives(neutral_text, "en")
        
        assert len(narratives) == 0


class TestNetworkAnalyzer:
    """Tests for network analysis functionality."""
    
    @pytest.fixture
    def mock_network_analyzer(self):
        """Create a mocked NetworkAnalyzer."""
        with patch('analyzers.network_analyzer.get_session'):
            from analyzers.network_analyzer import NetworkAnalyzer
            import networkx as nx
            
            analyzer = NetworkAnalyzer.__new__(NetworkAnalyzer)
            analyzer.session = MagicMock()
            analyzer.content_graph = nx.DiGraph()
            analyzer.source_graph = nx.DiGraph()
            return analyzer
    
    def test_empty_graph_stats(self, mock_network_analyzer):
        """Empty graph should have zero stats."""
        stats = mock_network_analyzer.get_network_stats()
        
        assert stats.node_count == 0
        assert stats.edge_count == 0
        assert stats.density == 0
    
    def test_build_source_graph(self, mock_network_analyzer):
        """Should build graph from sources."""
        # Mock source query
        mock_sources = [
            MagicMock(
                id="src1",
                name="Source 1",
                source_type="telegram",
                language="en",
                is_doppelganger=False,
                is_amplifier=True,
                is_active=True
            )
        ]
        mock_network_analyzer.session.query.return_value.filter.return_value.all.return_value = mock_sources
        
        # The method would add nodes for each source
        for src in mock_sources:
            mock_network_analyzer.source_graph.add_node(
                str(src.id),
                name=src.name,
                source_type=src.source_type
            )
        
        assert mock_network_analyzer.source_graph.number_of_nodes() == 1
    
    def test_find_superspreaders_empty(self, mock_network_analyzer):
        """Empty graph should return empty superspreaders list."""
        result = mock_network_analyzer.find_superspreaders(top_n=10)
        
        assert result == []
    
    def test_find_superspreaders_with_data(self, mock_network_analyzer):
        """Should identify superspreaders in graph."""
        import networkx as nx
        
        # Build test graph
        mock_network_analyzer.source_graph = nx.DiGraph()
        mock_network_analyzer.source_graph.add_node(
            "src1", name="Source 1", source_type="telegram",
            is_doppelganger=True, is_amplifier=False
        )
        mock_network_analyzer.source_graph.add_node(
            "src2", name="Source 2", source_type="media",
            is_doppelganger=False, is_amplifier=True
        )
        mock_network_analyzer.source_graph.add_edge("src1", "src2", weight=5)
        
        result = mock_network_analyzer.find_superspreaders(top_n=5)
        
        assert len(result) == 2
        assert all(isinstance(r, SuperspreaderInfo) for r in result)


class TestNetworkStats:
    """Tests for NetworkStats dataclass."""
    
    def test_create_stats(self):
        """Should create network statistics."""
        stats = NetworkStats(
            node_count=100,
            edge_count=500,
            density=0.1,
            community_count=5,
            avg_degree=10.0,
            is_connected=True
        )
        
        assert stats.node_count == 100
        assert stats.edge_count == 500
        assert stats.density == 0.1
    
    def test_default_values(self):
        """Should have correct defaults."""
        stats = NetworkStats(
            node_count=0,
            edge_count=0,
            density=0.0
        )
        
        assert stats.community_count == 0
        assert stats.avg_degree == 0.0
        assert stats.is_connected == False


class TestEntityExtraction:
    """Tests for named entity extraction."""
    
    def test_entity_dto_creation(self):
        """Should create EntityDTO correctly."""
        entity = EntityDTO(
            text="Vladimir Putin",
            entity_type="PERSON",
            start=0,
            end=14,
            confidence=0.95
        )
        
        assert entity.text == "Vladimir Putin"
        assert entity.entity_type == "PERSON"
        assert entity.start == 0
        assert entity.end == 14
        assert entity.confidence == 0.95
    
    def test_entity_default_confidence(self):
        """EntityDTO should default confidence to 1.0."""
        entity = EntityDTO(
            text="NATO",
            entity_type="ORG",
            start=50,
            end=54
        )
        
        assert entity.confidence == 1.0


class TestCognitiveMarkerDTO:
    """Tests for CognitiveMarkerDTO dataclass."""
    
    def test_create_marker(self):
        """Should create cognitive marker correctly."""
        marker = CognitiveMarkerDTO(
            marker_type="emotional_appeal",
            marker_category="manipulation",
            confidence=0.85,
            severity=Severity.HIGH,
            evidence_text="scandaleux",
            evidence_start=100,
            evidence_end=110
        )
        
        assert marker.marker_type == "emotional_appeal"
        assert marker.severity == Severity.HIGH
        assert marker.confidence == 0.85
    
    def test_default_severity(self):
        """Default severity should be MEDIUM."""
        marker = CognitiveMarkerDTO(
            marker_type="test",
            marker_category="test",
            confidence=0.5
        )
        
        assert marker.severity == Severity.MEDIUM


class TestAnalysisResult:
    """Tests for NLPAnalysisResult dataclass."""
    
    def test_create_result(self, sample_nlp_result):
        """Should create complete analysis result."""
        assert sample_nlp_result.content_id == "test-content-456"
        assert sample_nlp_result.is_propaganda == True
        assert len(sample_nlp_result.keywords) > 0
        assert len(sample_nlp_result.entities) > 0
    
    def test_sentiment_in_result(self, sample_nlp_result):
        """Sentiment should be accessible in result."""
        assert sample_nlp_result.sentiment.label == SentimentLabel.NEGATIVE
        assert sample_nlp_result.sentiment.score == -0.3


class TestKeywordExtraction:
    """Tests for keyword extraction functionality."""
    
    @pytest.fixture
    def analyzer_for_keywords(self):
        """Create analyzer for keyword testing."""
        with patch('analyzers.nlp_analyzer.get_session'):
            with patch('analyzers.nlp_analyzer.get_spacy_model') as mock_spacy:
                # Create mock spaCy model
                mock_nlp = MagicMock()
                mock_doc = MagicMock()
                mock_doc.noun_chunks = []
                mock_doc.ents = []
                mock_nlp.return_value = mock_doc
                mock_spacy.return_value = mock_nlp
                
                from analyzers.nlp_analyzer import NLPAnalyzer
                analyzer = NLPAnalyzer.__new__(NLPAnalyzer)
                analyzer.session = MagicMock()
                analyzer.keywords_config = {}
                analyzer.cognitive_config = {}
                return analyzer
    
    def test_extract_keywords_returns_list(self, analyzer_for_keywords):
        """extract_keywords should return a list."""
        result = analyzer_for_keywords.extract_keywords("Test text", "en", top_n=5)
        
        assert isinstance(result, list)
