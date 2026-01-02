"""
Doppelganger Tracker - Collector Tests
=======================================
Unit tests for content collectors.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from collectors.base import BaseCollector, SyncCollector
from collectors.media_collector import MediaCollector
from database import SourceType, ContentType, CollectionResult


class TestMediaCollector:
    """Tests for MediaCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create MediaCollector instance with mocked config."""
        with patch.object(MediaCollector, '_load_config') as mock_config:
            mock_config.return_value = {
                "media": {
                    "mainstream": {
                        "en": [
                            {"name": "Test Feed", "url": "https://example.com/feed"}
                        ]
                    }
                },
                "factcheckers": []
            }
            collector = MediaCollector()
            # Mock the database session
            collector.session = Mock()
            yield collector
            collector.close()
    
    def test_collector_type(self, collector):
        """Verify collector type is 'media'."""
        assert collector.collector_type == "media"
    
    def test_detect_language_short_text(self, collector):
        """Short text should return 'unknown'."""
        result = collector._detect_language("Hi")
        assert result == "unknown"
    
    def test_detect_language_english(self, collector):
        """English text should be detected correctly."""
        text = "This is a long enough sentence to detect the language properly."
        result = collector._detect_language(text)
        assert result == "en"
    
    def test_detect_language_french(self, collector):
        """French text should be detected correctly."""
        text = "Ceci est une phrase suffisamment longue pour détecter la langue correctement."
        result = collector._detect_language(text)
        assert result == "fr"
    
    def test_parse_feed_date_valid(self, collector):
        """Valid date tuple should be parsed correctly."""
        entry = {"published_parsed": (2024, 1, 15, 10, 30, 0, 0, 0, 0)}
        result = collector._parse_feed_date(entry)
        assert result == datetime(2024, 1, 15, 10, 30, 0)
    
    def test_parse_feed_date_missing(self, collector):
        """Missing date should return None."""
        entry = {}
        result = collector._parse_feed_date(entry)
        assert result is None
    
    def test_parse_feed_date_invalid(self, collector):
        """Invalid date should return None."""
        entry = {"published_parsed": None}
        result = collector._parse_feed_date(entry)
        assert result is None


class TestBaseCollector:
    """Tests for BaseCollector functionality."""
    
    def test_content_hash_computation(self):
        """Test that content hashing works correctly."""
        from database import Content
        
        text = "Test content for hashing"
        hash1 = Content.compute_hash(text)
        hash2 = Content.compute_hash(text)
        
        # Same text should produce same hash
        assert hash1 == hash2
        
        # Different text should produce different hash
        hash3 = Content.compute_hash("Different content")
        assert hash1 != hash3
    
    def test_collection_result_dataclass(self):
        """Test CollectionResult dataclass."""
        result = CollectionResult(
            run_id="test-123",
            collector_type="media",
            status="completed",
            items_collected=100,
            items_new=50,
            items_updated=30,
            errors_count=2,
            duration_seconds=15.5,
            error_messages=["Error 1", "Error 2"]
        )
        
        assert result.run_id == "test-123"
        assert result.items_collected == 100
        assert result.items_new == 50
        assert len(result.error_messages) == 2


class TestRSSFeedConfig:
    """Tests for RSS feed configuration."""
    
    def test_parse_feed_config(self):
        """Test parsing of feed configuration dict."""
        from database import RSSFeedConfig
        
        config = RSSFeedConfig(
            name="Test Feed",
            url="https://example.com/feed.xml",
            language="en",
            feed_type="media"
        )
        
        assert config.name == "Test Feed"
        assert config.url == "https://example.com/feed.xml"
        assert config.language == "en"


class TestTelegramChannelConfig:
    """Tests for Telegram channel configuration."""
    
    def test_channel_config_defaults(self):
        """Test default values for channel config."""
        from database import TelegramChannelConfig
        
        config = TelegramChannelConfig(
            name="Test Channel",
            channel="@testchannel"
        )
        
        assert config.name == "Test Channel"
        assert config.channel == "@testchannel"
        assert config.language == "unknown"
        assert config.channel_type == "monitor"
        assert config.priority == "medium"


class TestCollectorErrorHandling:
    """Tests for error handling in collectors."""
    
    @pytest.fixture
    def mock_collector(self):
        """Create a mock collector for testing."""
        with patch.object(MediaCollector, '_load_config') as mock_config:
            mock_config.return_value = {}
            collector = MediaCollector()
            collector.session = Mock()
            collector._errors = []
            yield collector
    
    def test_record_error(self, mock_collector):
        """Test error recording."""
        mock_collector.record_error("Test error message")
        
        assert len(mock_collector._errors) == 1
        assert mock_collector._errors[0] == "Test error message"
    
    def test_multiple_errors(self, mock_collector):
        """Test recording multiple errors."""
        mock_collector.record_error("Error 1")
        mock_collector.record_error("Error 2")
        mock_collector.record_error("Error 3")
        
        assert len(mock_collector._errors) == 3
