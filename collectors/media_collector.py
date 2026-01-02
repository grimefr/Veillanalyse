"""
Doppelganger Tracker - Media & RSS Collector
=============================================
Collects articles from RSS feeds of media outlets and fact-checkers.

Usage:
    from collectors.media_collector import MediaCollector
    
    collector = MediaCollector()
    result = collector.collect_all_sync()
"""

import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
from langdetect import detect, LangDetectException
from loguru import logger

from collectors.base import SyncCollector
from database import (
    Content,
    Factcheck,
    CollectionResult,
    SourceType,
    ContentType,
    RSSFeedConfig
)
from config.settings import settings


class MediaCollector(SyncCollector):
    """
    Collector for RSS feeds from media outlets and fact-checkers.
    
    Parses RSS/Atom feeds, extracts article content, and stores
    in the database with automatic language detection.
    
    Features:
    - RSS/Atom feed parsing
    - Full article text extraction (optional)
    - Language detection
    - Fact-check record creation
    - Rate limiting between requests
    
    Attributes:
        headers: HTTP request headers
        timeout: Request timeout in seconds
    """
    
    def __init__(self, config_path: str = "config/sources.yaml"):
        """
        Initialize media collector.
        
        Args:
            config_path: Path to sources configuration
        """
        super().__init__(config_path)
        
        # HTTP configuration
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5,fr;q=0.3,ru;q=0.2"
        }
        self.timeout = settings.request_timeout
    
    @property
    def collector_type(self) -> str:
        """Return collector type identifier."""
        return "media"
    
    def _detect_language(self, text: str) -> str:
        """
        Detect language of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            str: ISO language code or 'unknown'
        """
        if not text or len(text) < 20:
            return "unknown"
        
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"
    
    def _parse_feed_date(self, entry: dict) -> Optional[datetime]:
        """
        Parse publication date from feed entry.
        
        Args:
            entry: Feedparser entry dict
            
        Returns:
            datetime: Parsed datetime or None
        """
        date_fields = ["published_parsed", "updated_parsed", "created_parsed"]
        
        for field in date_fields:
            parsed = entry.get(field)
            if parsed:
                try:
                    return datetime(*parsed[:6])
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_full_text(self, url: str) -> Optional[str]:
        """
        Extract full text from article URL.
        
        Args:
            url: Article URL
            
        Returns:
            str: Extracted text or None on failure
        """
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, "lxml")
            
            # Remove non-content elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
            
            # Try to find article content
            article = soup.find("article")
            if article:
                return article.get_text(separator=" ", strip=True)
            
            # Fallback to main content
            main = soup.find("main")
            if main:
                return main.get_text(separator=" ", strip=True)
            
            # Last resort: body text (limited)
            body = soup.find("body")
            if body:
                text = body.get_text(separator=" ", strip=True)
                return text[:10000] if len(text) > 10000 else text
            
            return None
            
        except requests.RequestException as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error extracting text from {url}: {e}")
            return None
    
    def _parse_feed_config(self, config: dict) -> RSSFeedConfig:
        """
        Parse feed configuration from dict.
        
        Args:
            config: Feed configuration dict
            
        Returns:
            RSSFeedConfig: Parsed configuration
        """
        return RSSFeedConfig(
            name=config.get("name", "Unknown"),
            url=config.get("url", ""),
            language=config.get("language", "unknown"),
            feed_type=config.get("type", "media")
        )
    
    def collect_feed(
        self,
        feed_config: RSSFeedConfig,
        extract_full_text: bool = False,
        limit: int = 50
    ) -> int:
        """
        Collect articles from a single RSS feed.
        
        Args:
            feed_config: Feed configuration
            extract_full_text: Whether to fetch full article text
            limit: Maximum entries to process
            
        Returns:
            int: Number of new articles collected
        """
        if not feed_config.url:
            logger.warning(f"Missing URL for feed: {feed_config.name}")
            return 0
        
        collected_count = 0
        
        try:
            # Parse feed
            logger.debug(f"Parsing feed: {feed_config.url}")
            feed = feedparser.parse(feed_config.url)
            
            # Check for errors
            if feed.bozo and not feed.entries:
                logger.warning(f"Invalid feed: {feed_config.url}")
                return 0
            
            # Determine source type
            source_type = (
                SourceType.FACTCHECK 
                if feed_config.feed_type == "factcheck" 
                else SourceType.MEDIA
            )
            
            # Get or create source
            source = self.get_or_create_source(
                name=feed_config.name,
                source_type=source_type,
                platform="web",
                url=feed_config.url,
                language=feed_config.language,
                is_factchecker=feed_config.feed_type == "factcheck"
            )
            
            # Process entries
            for entry in feed.entries[:limit]:
                try:
                    # Extract basic info
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", entry.get("description", ""))
                    
                    # Skip if no content
                    if not title and not summary:
                        continue
                    
                    # Build text content
                    text_content = f"{title}\n\n{summary}"
                    
                    # Optionally fetch full text
                    if extract_full_text and link:
                        full_text = self._extract_full_text(link)
                        if full_text:
                            text_content = f"{title}\n\n{full_text}"
                    
                    # Compute hash
                    text_hash = Content.compute_hash(text_content)
                    
                    # Skip duplicates
                    if self.content_exists(text_hash):
                        continue
                    
                    # Parse date
                    published_at = self._parse_feed_date(entry)
                    
                    # Detect language (override config if different)
                    detected_lang = self._detect_language(text_content)
                    language = (
                        detected_lang 
                        if detected_lang != "unknown" 
                        else feed_config.language
                    )
                    
                    # Create content record
                    content = Content(
                        source_id=source.id,
                        external_id=link or entry.get("id", ""),
                        content_type=ContentType.ARTICLE.value,
                        title=title[:500] if title else None,
                        text_content=text_content,
                        text_hash=text_hash,
                        url=link,
                        language=language,
                        published_at=published_at,
                        collected_at=datetime.utcnow()
                    )
                    
                    if self.add_content(content):
                        collected_count += 1
                        
                        # Create factcheck record for fact-checking sources
                        if feed_config.feed_type == "factcheck":
                            factcheck = Factcheck(
                                content_id=content.id,
                                claim_text=title or text_content[:500],
                                verdict="unverified",
                                factcheck_source=feed_config.name,
                                factcheck_url=link,
                                factcheck_date=published_at
                            )
                            self.session.add(factcheck)
                    
                except Exception as e:
                    logger.debug(f"Error processing entry: {e}")
                    continue
            
            # Commit batch
            self.commit()
            
            logger.info(
                f"Feed {feed_config.name}: "
                f"{len(feed.entries)} entries, {collected_count} new"
            )
            
        except Exception as e:
            self.record_error(f"Error collecting {feed_config.name}: {str(e)}")
            self.session.rollback()
        
        return collected_count
    
    def collect_media_feeds(self) -> int:
        """
        Collect from all configured media feeds.
        
        Returns:
            int: Total new articles collected
        """
        total_new = 0
        media_config = self.config.get("media", {})
        
        # Collect mainstream media by language
        mainstream = media_config.get("mainstream", {})
        for lang, feeds in mainstream.items():
            if not isinstance(feeds, list):
                continue
            
            for feed_dict in feeds:
                if isinstance(feed_dict, dict):
                    feed_config = self._parse_feed_config(feed_dict)
                    feed_config.language = lang  # Override with category language
                    total_new += self.collect_feed(feed_config)
                    time.sleep(0.5)  # Rate limiting
        
        # Collect alternative media (with full text extraction)
        alternative = media_config.get("alternative", [])
        for feed_dict in alternative:
            if isinstance(feed_dict, dict):
                feed_config = self._parse_feed_config(feed_dict)
                feed_config.feed_type = "alternative"
                total_new += self.collect_feed(
                    feed_config, 
                    extract_full_text=True
                )
                time.sleep(1)  # Longer delay for full text extraction
        
        return total_new
    
    def collect_factcheckers(self) -> int:
        """
        Collect from all configured fact-checking feeds.
        
        Returns:
            int: Total new fact-checks collected
        """
        total_new = 0
        factcheckers = self.config.get("factcheckers", [])
        
        for feed_dict in factcheckers:
            if isinstance(feed_dict, dict):
                feed_config = self._parse_feed_config(feed_dict)
                feed_config.feed_type = "factcheck"
                total_new += self.collect_feed(
                    feed_config,
                    extract_full_text=True,
                    limit=30
                )
                time.sleep(1)
        
        return total_new
    
    def collect_all_sync(self) -> CollectionResult:
        """
        Collect from all configured sources.
        
        Returns:
            CollectionResult: Summary of collection run
        """
        # Start run
        self.start_run()
        
        try:
            # Collect media
            logger.info("Collecting media feeds...")
            self.collect_media_feeds()
            
            # Collect fact-checkers
            logger.info("Collecting fact-checkers...")
            self.collect_factcheckers()
            
        except Exception as e:
            self.record_error(f"Fatal error: {str(e)}")
        
        # Determine status
        status = "completed" if not self._errors else "completed_with_errors"
        
        return self.end_run(status)


def main():
    """Entry point for standalone execution."""
    logger.info("=== Doppelganger Tracker - Media Collector ===")
    
    collector = MediaCollector()
    
    try:
        result = collector.collect_all_sync()
        logger.info(f"Collection result: {result}")
    finally:
        collector.close()


if __name__ == "__main__":
    main()
