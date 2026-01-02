"""
Doppelganger Tracker - Collectors Module
========================================
Content collection from various sources.
"""

from .base import BaseCollector, SyncCollector
from .telegram_collector import TelegramCollector
from .media_collector import MediaCollector

__all__ = [
    "BaseCollector",
    "SyncCollector",
    "TelegramCollector",
    "MediaCollector",
]
