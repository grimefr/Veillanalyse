"""
Pytest Configuration & Fixtures
================================
Global fixtures for testing.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_engine


@pytest.fixture(scope="session")
def db_engine():
    """Create test database engine."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create database session for test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_content():
    """Sample content data for testing."""
    return {
        "title": "Test Article",
        "text_content": "This is a test article content.",
        "language": "en",
        "published_at": "2026-01-01T10:00:00Z"
    }
