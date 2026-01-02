"""
Doppelganger Tracker - Base Collector
=====================================
Abstract base class for all collectors.
Provides common functionality for content collection.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

import yaml
from loguru import logger

from database import (
    get_session,
    Source,
    Content,
    CollectionRun,
    CollectionResult,
    SourceType,
)
from config.settings import settings


class BaseCollector(ABC):
    """
    Abstract base class for content collectors.
    
    Provides common functionality for all collector implementations:
    - Configuration loading
    - Database session management
    - Collection run tracking
    - Deduplication
    - Error handling
    
    Subclasses must implement:
    - collect_all(): Main collection method
    - collector_type: Property returning collector type string
    
    Attributes:
        config: Loaded YAML configuration
        session: Database session
        run: Current collection run record
    """
    
    def __init__(self, config_path: str = "config/sources.yaml"):
        """
        Initialize collector with configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config = self._load_config(config_path)
        self.session = get_session()
        self.run: Optional[CollectionRun] = None
        self._items_new = 0
        self._items_updated = 0
        self._errors: List[str] = []
    
    @property
    @abstractmethod
    def collector_type(self) -> str:
        """Return the collector type identifier."""
        pass
    
    @abstractmethod
    async def collect_all(self) -> CollectionResult:
        """
        Execute collection for all configured sources.
        
        Returns:
            CollectionResult: Summary of collection run
        """
        pass
    
    def _load_config(self, path: str) -> dict:
        """
        Load configuration from YAML file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            dict: Parsed configuration
            
        Raises:
            FileNotFoundError: If config file not found
        """
        config_file = Path(path)
        
        # Try multiple locations
        if not config_file.exists():
            config_file = Path(__file__).parent.parent / path
        if not config_file.exists():
            config_file = Path(settings.config_dir) / Path(path).name
        if not config_file.exists():
            logger.warning(f"Config file not found: {path}, using empty config")
            return {}
        
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            logger.debug(f"Loaded config from {config_file}")
            return config or {}
    
    def start_run(self) -> CollectionRun:
        """
        Start a new collection run.
        
        Returns:
            CollectionRun: New collection run record
        """
        self.run = CollectionRun(
            collector_type=self.collector_type,
            started_at=datetime.utcnow(),
            status="running"
        )
        self.session.add(self.run)
        self.session.commit()
        
        self._items_new = 0
        self._items_updated = 0
        self._errors = []
        
        logger.info(f"Started collection run: {self.run.id}")
        return self.run
    
    def end_run(self, status: str = "completed") -> CollectionResult:
        """
        End the current collection run.
        
        Args:
            status: Final status (completed, completed_with_errors, failed)
            
        Returns:
            CollectionResult: Summary of collection run
        """
        if not self.run:
            raise ValueError("No active collection run")
        
        self.run.finished_at = datetime.utcnow()
        self.run.status = status
        self.run.items_new = self._items_new
        self.run.items_updated = self._items_updated
        self.run.errors_count = len(self._errors)
        self.run.error_messages = self._errors if self._errors else None
        
        self.session.commit()
        
        duration = (self.run.finished_at - self.run.started_at).total_seconds()
        
        logger.info(
            f"Collection run completed: {self._items_new} new, "
            f"{self._items_updated} updated, {len(self._errors)} errors "
            f"in {duration:.1f}s"
        )
        
        return CollectionResult(
            run_id=str(self.run.id),
            collector_type=self.collector_type,
            status=status,
            items_collected=self._items_new + self._items_updated,
            items_new=self._items_new,
            items_updated=self._items_updated,
            errors_count=len(self._errors),
            duration_seconds=duration,
            error_messages=self._errors
        )
    
    def record_error(self, error: str):
        """
        Record an error during collection.
        
        Args:
            error: Error message
        """
        self._errors.append(error)
        logger.error(f"Collection error: {error}")
    
    def get_or_create_source(
        self,
        name: str,
        source_type: SourceType,
        platform: Optional[str] = None,
        url: Optional[str] = None,
        language: Optional[str] = None,
        telegram_channel_id: Optional[int] = None,
        is_doppelganger: bool = False,
        is_amplifier: bool = False,
        is_factchecker: bool = False
    ) -> Source:
        """
        Get existing source or create new one.
        
        Args:
            name: Source display name
            source_type: Source type category
            platform: Platform identifier
            url: Source URL
            language: Content language
            telegram_channel_id: Telegram channel ID
            is_doppelganger: Doppelganger flag
            is_amplifier: Amplifier flag
            is_factchecker: Fact-checker flag
            
        Returns:
            Source: Existing or newly created source
        """
        # Try to find existing source
        source = None
        
        if telegram_channel_id:
            source = self.session.query(Source).filter(
                Source.telegram_channel_id == telegram_channel_id
            ).first()
        elif url:
            source = self.session.query(Source).filter(
                Source.url == url
            ).first()
        else:
            source = self.session.query(Source).filter(
                Source.name == name,
                Source.source_type == source_type.value
            ).first()
        
        if source:
            # Update last collected timestamp
            source.last_collected_at = datetime.utcnow()
            self.session.commit()
            return source
        
        # Create new source
        source = Source(
            name=name,
            source_type=source_type.value,
            platform=platform,
            url=url,
            language=language,
            telegram_channel_id=telegram_channel_id,
            is_doppelganger=is_doppelganger,
            is_amplifier=is_amplifier,
            is_factchecker=is_factchecker,
            is_active=True,
            first_seen_at=datetime.utcnow(),
            last_collected_at=datetime.utcnow()
        )
        
        self.session.add(source)
        self.session.commit()
        
        logger.info(f"Created new source: {name} ({source_type.value})")
        return source
    
    def content_exists(self, text_hash: str) -> bool:
        """
        Check if content with given hash already exists.
        
        Args:
            text_hash: SHA256 hash of content text
            
        Returns:
            bool: True if content exists
        """
        return self.session.query(Content).filter(
            Content.text_hash == text_hash
        ).first() is not None
    
    def add_content(self, content: Content) -> bool:
        """
        Add content if not already exists.
        
        Args:
            content: Content entity to add
            
        Returns:
            bool: True if content was added (new)
        """
        # Check for duplicate
        if self.content_exists(content.text_hash):
            return False
        
        self.session.add(content)
        self._items_new += 1
        return True
    
    def commit(self):
        """Commit current transaction."""
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e
    
    def close(self):
        """Close database session."""
        self.session.close()


class SyncCollector(BaseCollector):
    """
    Base class for synchronous collectors.
    
    Provides sync-friendly interface for collectors that
    don't require async operations (e.g., RSS feeds).
    """
    
    def collect_all_sync(self) -> CollectionResult:
        """
        Synchronous collection method.
        
        Returns:
            CollectionResult: Summary of collection run
        """
        raise NotImplementedError("Subclasses must implement collect_all_sync")
    
    async def collect_all(self) -> CollectionResult:
        """
        Async wrapper for sync collection.
        
        Returns:
            CollectionResult: Summary of collection run
        """
        return self.collect_all_sync()
