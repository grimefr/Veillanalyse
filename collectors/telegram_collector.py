"""
Doppelganger Tracker - Telegram Collector
==========================================
Collects messages from public Telegram channels using Telethon.
Monitors channels associated with the Doppelganger operation.

Usage:
    from collectors.telegram_collector import TelegramCollector
    
    collector = TelegramCollector()
    await collector.connect()
    result = await collector.collect_all()
    await collector.disconnect()
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from loguru import logger
from telethon import TelegramClient
from telethon.tl.types import Channel, Message
from telethon.errors import (
    ChannelPrivateError,
    UsernameNotOccupiedError,
    FloodWaitError,
    ChannelInvalidError
)

from collectors.base import BaseCollector
from database import (
    Content,
    CollectionResult,
    SourceType,
    ContentType,
    TelegramChannelConfig
)
from config.settings import settings


class TelegramCollector(BaseCollector):
    """
    Collector for Telegram public channels.
    
    Uses Telethon to access the Telegram API and collect
    messages from configured public channels.
    
    Features:
    - Automatic authentication handling
    - Rate limiting with backoff
    - Forward detection
    - Media type extraction
    - Deduplication via content hash
    
    Attributes:
        client: Telethon client instance
        connected: Connection status flag
    """
    
    def __init__(self, config_path: str = "config/sources.yaml"):
        """
        Initialize Telegram collector.
        
        Args:
            config_path: Path to sources configuration
        """
        super().__init__(config_path)
        self.client: Optional[TelegramClient] = None
        self.connected = False
        
        # Validate credentials
        if not settings.telegram_configured:
            logger.warning(
                "Telegram credentials not configured. "
                "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
            )
    
    @property
    def collector_type(self) -> str:
        """Return collector type identifier."""
        return "telegram"
    
    async def connect(self) -> bool:
        """
        Establish connection to Telegram API.
        
        Returns:
            bool: True if connection successful
        """
        if not settings.telegram_configured:
            logger.error("Telegram API credentials not configured")
            return False
        
        try:
            # Create session path
            session_dir = Path(settings.data_dir)
            session_dir.mkdir(parents=True, exist_ok=True)
            session_path = session_dir / settings.telegram_session_name
            
            # Initialize client
            self.client = TelegramClient(
                str(session_path),
                int(settings.telegram_api_id),
                settings.telegram_api_hash
            )
            
            await self.client.start()
            
            # Verify connection
            me = await self.client.get_me()
            logger.info(f"Connected to Telegram as: {me.username or me.phone}")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Telegram API."""
        if self.client:
            await self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from Telegram")
    
    def _parse_channel_config(self, config: dict) -> TelegramChannelConfig:
        """
        Parse channel configuration from dict.
        
        Args:
            config: Channel configuration dict
            
        Returns:
            TelegramChannelConfig: Parsed configuration
        """
        return TelegramChannelConfig(
            name=config.get("name", "Unknown"),
            channel=config.get("channel", "").replace("@", ""),
            language=config.get("language", "unknown"),
            channel_type=config.get("type", "monitor"),
            priority=config.get("priority", "medium")
        )
    
    def _get_configured_channels(self) -> List[TelegramChannelConfig]:
        """
        Get all configured Telegram channels.
        
        Returns:
            List[TelegramChannelConfig]: List of channel configurations
        """
        channels = []
        telegram_config = self.config.get("telegram", {})
        
        for category, channel_list in telegram_config.items():
            if not isinstance(channel_list, list):
                continue
            
            for channel_dict in channel_list:
                if isinstance(channel_dict, dict):
                    channels.append(self._parse_channel_config(channel_dict))
        
        return channels
    
    async def collect_channel(
        self,
        channel_config: TelegramChannelConfig,
        lookback_days: int = 7,
        limit: int = 100
    ) -> int:
        """
        Collect messages from a single channel.
        
        Args:
            channel_config: Channel configuration
            lookback_days: Number of days to look back
            limit: Maximum messages to collect
            
        Returns:
            int: Number of new messages collected
        """
        channel_id = channel_config.channel
        if not channel_id:
            logger.warning(f"Missing channel ID for {channel_config.name}")
            return 0
        
        collected_count = 0
        
        try:
            # Get channel entity
            entity = await self.client.get_entity(channel_id)
            
            if not isinstance(entity, Channel):
                logger.warning(f"{channel_id} is not a channel")
                return 0
            
            # Get or create source
            source = self.get_or_create_source(
                name=channel_config.name,
                source_type=SourceType.TELEGRAM,
                platform="telegram",
                url=f"https://t.me/{entity.username}" if entity.username else None,
                language=channel_config.language,
                telegram_channel_id=entity.id,
                is_doppelganger=channel_config.channel_type == "doppelganger",
                is_amplifier=channel_config.channel_type == "amplifier"
            )
            
            # Calculate date limit
            min_date = datetime.utcnow() - timedelta(days=lookback_days)
            
            # Iterate through messages
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                offset_date=datetime.utcnow()
            ):
                # Skip old messages
                if message.date.replace(tzinfo=None) < min_date:
                    break
                
                # Skip empty messages
                if not message.text:
                    continue
                
                # Compute hash for deduplication
                text_hash = Content.compute_hash(message.text)
                
                # Skip if already collected
                if self.content_exists(text_hash):
                    continue
                
                # Determine content type (forward or regular message)
                content_type = (
                    ContentType.FORWARD.value 
                    if message.fwd_from 
                    else ContentType.MESSAGE.value
                )
                
                # Extract media types
                media_types = []
                has_media = message.media is not None
                
                if message.photo:
                    media_types.append("image")
                if message.video:
                    media_types.append("video")
                if message.document:
                    media_types.append("document")
                if message.audio:
                    media_types.append("audio")
                
                # Create content record
                content = Content(
                    source_id=source.id,
                    external_id=str(message.id),
                    content_type=content_type,
                    text_content=message.text,
                    text_hash=text_hash,
                    has_media=has_media,
                    media_types=media_types if media_types else None,
                    language=channel_config.language,
                    views_count=message.views,
                    shares_count=message.forwards,
                    published_at=message.date,
                    collected_at=datetime.utcnow()
                )
                
                if self.add_content(content):
                    collected_count += 1
            
            # Commit batch
            self.commit()
            
            logger.info(
                f"Channel {channel_id}: collected {collected_count} new messages"
            )
            
        except ChannelPrivateError:
            self.record_error(f"Channel {channel_id} is private")
        except UsernameNotOccupiedError:
            self.record_error(f"Channel {channel_id} does not exist")
        except ChannelInvalidError:
            self.record_error(f"Invalid channel: {channel_id}")
        except FloodWaitError as e:
            logger.warning(f"Rate limited, waiting {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            self.record_error(f"Error collecting {channel_id}: {str(e)}")
            self.session.rollback()
        
        return collected_count
    
    async def collect_all(
        self,
        lookback_days: Optional[int] = None,
        limit_per_channel: Optional[int] = None
    ) -> CollectionResult:
        """
        Collect from all configured channels.
        
        Args:
            lookback_days: Override default lookback period
            limit_per_channel: Override default message limit
            
        Returns:
            CollectionResult: Summary of collection run
        """
        if not self.connected:
            if not await self.connect():
                return CollectionResult(
                    run_id="",
                    collector_type=self.collector_type,
                    status="failed",
                    error_messages=["Failed to connect to Telegram"]
                )
        
        # Get settings
        lookback = lookback_days or settings.initial_lookback_days
        limit = limit_per_channel or settings.max_messages_per_channel
        
        # Start run
        self.start_run()
        
        # Get channels
        channels = self._get_configured_channels()
        logger.info(f"Collecting from {len(channels)} Telegram channels")
        
        # Collect from each channel
        for channel in channels:
            try:
                await self.collect_channel(
                    channel,
                    lookback_days=lookback,
                    limit=limit
                )
                
                # Rate limiting delay between channels
                await asyncio.sleep(1)
                
            except Exception as e:
                self.record_error(f"{channel.name}: {str(e)}")
        
        # Determine final status
        status = "completed"
        if self._errors:
            status = "completed_with_errors"
        
        return self.end_run(status)


async def main():
    """Entry point for standalone execution."""
    logger.info("=== Doppelganger Tracker - Telegram Collector ===")
    
    collector = TelegramCollector()
    
    try:
        if await collector.connect():
            result = await collector.collect_all()
            logger.info(f"Collection result: {result}")
        else:
            logger.error("Failed to connect to Telegram")
    finally:
        await collector.disconnect()
        collector.close()


if __name__ == "__main__":
    asyncio.run(main())
