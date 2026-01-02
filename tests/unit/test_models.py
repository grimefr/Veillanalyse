"""
Unit Tests - Database Models
=============================
"""
import pytest
from datetime import datetime

from database.models import Source, Content


def test_source_creation(db_session):
    """Test source model creation."""
    source = Source(
        name="Test Source",
        source_type="media",
        platform="web",
        url="https://example.com",
        language="en",
        is_active=True
    )
    db_session.add(source)
    db_session.commit()

    assert source.id is not None
    assert source.name == "Test Source"
    assert source.is_active is True


def test_content_creation(db_session):
    """Test content model creation."""
    # Create source first
    source = Source(
        name="Test Source",
        source_type="media",
        platform="web",
        language="en"
    )
    db_session.add(source)
    db_session.flush()

    # Create content
    content = Content(
        source_id=source.id,
        title="Test Article",
        text_content="Test content",
        content_type="article",
        language="en",
        published_at=datetime.utcnow()
    )
    db_session.add(content)
    db_session.commit()

    assert content.id is not None
    assert content.title == "Test Article"
    assert content.source_id == source.id
