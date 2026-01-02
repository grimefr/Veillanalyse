"""
Doppelganger Tracker - Analyzers Module
========================================
Comprehensive analysis components for disinformation detection:

- NLPAnalyzer: Sentiment, entities, keywords, propaganda detection
- NetworkAnalyzer: Graph analysis, community detection, superspreaders
- D3ltaAnalyzer: Copycat/CIB detection using VIGINUM's D3lta library
- BERTopicAnalyzer: Topic modeling and thematic analysis

Each analyzer is modular and can be used independently or combined.
"""

# Core analyzers
from .nlp_analyzer import NLPAnalyzer
from .network_analyzer import NetworkAnalyzer

# D3lta integration (CIB/Copycat detection)
from .d3lta_analyzer import (
    D3ltaAnalyzer,
    D3ltaConfig,
    DuplicateType,
    CIBIndicator,
    DuplicateMatch,
    ContentCluster,
    CIBDetectionResult,
    detect_copycats,
    find_duplicates_in_corpus,
    D3LTA_AVAILABLE,
)

# BERTopic integration (Topic modeling)
from .topic_analyzer import (
    BERTopicAnalyzer,
    BERTopicConfig,
    Topic,
    DocumentTopicAssignment,
    TopicEvolution,
    TopicModelResult,
    extract_topics,
    find_similar_topics,
    BERTOPIC_AVAILABLE,
)

__all__ = [
    # Core analyzers
    "NLPAnalyzer",
    "NetworkAnalyzer",
    
    # D3lta (CIB/Copycat)
    "D3ltaAnalyzer",
    "D3ltaConfig",
    "DuplicateType",
    "CIBIndicator",
    "DuplicateMatch",
    "ContentCluster",
    "CIBDetectionResult",
    "detect_copycats",
    "find_duplicates_in_corpus",
    "D3LTA_AVAILABLE",
    
    # BERTopic (Topics)
    "BERTopicAnalyzer",
    "BERTopicConfig",
    "Topic",
    "DocumentTopicAssignment",
    "TopicEvolution",
    "TopicModelResult",
    "extract_topics",
    "find_similar_topics",
    "BERTOPIC_AVAILABLE",
]
