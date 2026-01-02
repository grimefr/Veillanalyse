"""
Doppelganger Tracker - NLP Analyzer
====================================
Performs NLP analysis on collected content including:
- Language detection
- Sentiment analysis
- Named entity recognition
- Keyword extraction
- Propaganda detection
- Narrative classification
- Cognitive warfare marker detection

Usage:
    from analyzers.nlp_analyzer import NLPAnalyzer
    
    analyzer = NLPAnalyzer()
    result = analyzer.analyze_unprocessed(limit=100)
"""

import re
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field

import yaml
import spacy
from langdetect import detect, LangDetectException
from loguru import logger

from database import (
    get_session,
    Content,
    NLPAnalysis,
    CognitiveMarker,
    Narrative,
    ContentNarrative,
    SentimentResult,
    SentimentLabel,
    EntityDTO,
    NLPAnalysisResult,
    CognitiveMarkerDTO,
    NarrativeMatch,
    Severity,
    AnalysisResult,
)
from config.settings import settings


# =============================================================================
# SPACY MODEL MANAGEMENT
# =============================================================================

# Cache for loaded spaCy models (thread-safe)
_SPACY_MODELS: Dict[str, Any] = {}
_SPACY_LOCK = threading.Lock()

# Mapping of language codes to spaCy model names
SPACY_MODEL_MAP = {
    "fr": "fr_core_news_sm",
    "en": "en_core_web_sm",
    "ru": "ru_core_news_sm",
}


def get_spacy_model(lang: str):
    """
    Load and cache spaCy model for language (thread-safe).

    Uses double-check locking pattern to ensure thread safety
    without unnecessary locking overhead.

    Args:
        lang: ISO language code (fr, en, ru)

    Returns:
        spacy.Language: Loaded model
    """
    global _SPACY_MODELS

    # Normalize language code
    lang = lang.lower()[:2] if lang else "en"

    # Fallback to English if language not supported
    if lang not in SPACY_MODEL_MAP:
        lang = "en"

    # First check without lock (fast path)
    if lang in _SPACY_MODELS:
        return _SPACY_MODELS[lang]

    # Acquire lock for loading (slow path)
    with _SPACY_LOCK:
        # Double-check after acquiring lock (another thread may have loaded it)
        if lang in _SPACY_MODELS:
            return _SPACY_MODELS[lang]

        # Load model
        model_name = SPACY_MODEL_MAP[lang]
        try:
            model = spacy.load(model_name)
            _SPACY_MODELS[lang] = model
            logger.info(f"Loaded spaCy model: {model_name}")
            return model
        except OSError:
            # Fallback to English
            logger.warning(f"Model {model_name} not found, falling back to English")
            if "en" not in _SPACY_MODELS:
                _SPACY_MODELS["en"] = spacy.load("en_core_web_sm")
        return _SPACY_MODELS["en"]


# =============================================================================
# SENTIMENT LEXICONS
# =============================================================================

# Simple lexicon-based sentiment for multilingual support
NEGATIVE_LEXICON = {
    "fr": [
        "corruption", "scandale", "honteux", "menace", "danger", "crise",
        "échec", "catastrophe", "horrible", "terrible", "mort", "guerre",
        "destruction", "chaos", "effondrement", "désastre", "tragédie",
        "échec", "faillite", "défaite", "peur", "terreur", "horreur"
    ],
    "en": [
        "corruption", "scandal", "shameful", "threat", "danger", "crisis",
        "failure", "catastrophe", "horrible", "terrible", "death", "war",
        "destruction", "chaos", "collapse", "disaster", "tragedy",
        "defeat", "fear", "terror", "horror", "evil", "attack"
    ],
    "ru": [
        "коррупция", "скандал", "угроза", "опасность", "кризис",
        "катастрофа", "ужасный", "война", "смерть", "разрушение",
        "хаос", "крах", "трагедия", "поражение", "страх", "террор"
    ]
}

POSITIVE_LEXICON = {
    "fr": [
        "succès", "victoire", "progrès", "paix", "liberté", "espoir",
        "prospérité", "unité", "force", "triomphe", "réussite"
    ],
    "en": [
        "success", "victory", "progress", "peace", "freedom", "hope",
        "prosperity", "unity", "strength", "triumph", "achievement"
    ],
    "ru": [
        "успех", "победа", "прогресс", "мир", "свобода", "надежда",
        "процветание", "единство", "сила", "триумф", "достижение"
    ]
}


# =============================================================================
# NLP ANALYZER CLASS
# =============================================================================

class NLPAnalyzer:
    """
    NLP analyzer for content analysis.
    
    Performs comprehensive NLP analysis including sentiment,
    entities, keywords, propaganda detection, and cognitive
    warfare marker identification.
    
    Attributes:
        session: Database session
        keywords_config: Keywords configuration
        cognitive_config: Cognitive warfare configuration
    """
    
    def __init__(
        self,
        keywords_config_path: str = "config/keywords.yaml",
        cognitive_config_path: str = "config/cognitive_warfare.yaml"
    ):
        """
        Initialize NLP analyzer.
        
        Args:
            keywords_config_path: Path to keywords configuration
            cognitive_config_path: Path to cognitive warfare configuration
        """
        self.session = get_session()
        self.keywords_config = self._load_config(keywords_config_path)
        self.cognitive_config = self._load_config(cognitive_config_path)
        self._model_version = "v1.0"
    
    def _load_config(self, path: str) -> dict:
        """
        Load configuration from YAML file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            dict: Parsed configuration or empty dict
        """
        config_file = Path(path)
        
        if not config_file.exists():
            config_file = Path(__file__).parent.parent / path
        if not config_file.exists():
            config_file = Path(settings.config_dir) / Path(path).name
        
        if not config_file.exists():
            logger.warning(f"Config not found: {path}")
            return {}
        
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        Detect language of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple[str, float]: (language_code, confidence)
        """
        if not text or len(text.strip()) < 20:
            return "unknown", 0.0
        
        try:
            lang = detect(text)
            # Estimate confidence based on text length
            confidence = min(0.5 + (len(text) / 1000), 0.95)
            return lang, confidence
        except LangDetectException:
            return "unknown", 0.0
    
    def analyze_sentiment(self, text: str, lang: str) -> SentimentResult:
        """
        Analyze sentiment of text using lexicon-based approach.
        
        Args:
            text: Text to analyze
            lang: Language code
            
        Returns:
            SentimentResult: Sentiment analysis result
        """
        text_lower = text.lower()
        
        # Get lexicons for language (fallback to English)
        lang_key = lang if lang in NEGATIVE_LEXICON else "en"
        negative_words = NEGATIVE_LEXICON.get(lang_key, [])
        positive_words = POSITIVE_LEXICON.get(lang_key, [])
        
        # Count matches
        neg_count = sum(1 for word in negative_words if word in text_lower)
        pos_count = sum(1 for word in positive_words if word in text_lower)
        
        total = neg_count + pos_count
        
        if total == 0:
            return SentimentResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.5
            )
        
        # Calculate score with smoothing
        score = (pos_count - neg_count) / (total + 5)
        
        # Determine label
        if score > 0.1:
            label = SentimentLabel.POSITIVE
        elif score < -0.1:
            label = SentimentLabel.NEGATIVE
        else:
            label = SentimentLabel.NEUTRAL
        
        # Calculate confidence based on evidence
        confidence = min(0.5 + (total * 0.05), 0.9)
        
        return SentimentResult(
            score=round(score, 4),
            label=label,
            confidence=round(confidence, 4)
        )
    
    def extract_entities(self, text: str, lang: str) -> List[EntityDTO]:
        """
        Extract named entities from text using spaCy.
        
        Args:
            text: Text to analyze
            lang: Language code
            
        Returns:
            List[EntityDTO]: Extracted entities
        """
        nlp = get_spacy_model(lang)
        
        # Limit text length for performance
        doc = nlp(text[:10000])
        
        entities = []
        for ent in doc.ents:
            entities.append(EntityDTO(
                text=ent.text,
                entity_type=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                confidence=1.0  # spaCy doesn't provide confidence
            ))
        
        return entities
    
    def extract_keywords(
        self, 
        text: str, 
        lang: str, 
        top_n: int = 10
    ) -> List[str]:
        """
        Extract keywords from text.
        
        Uses noun chunks and named entities to identify
        important terms in the text.
        
        Args:
            text: Text to analyze
            lang: Language code
            top_n: Maximum keywords to return
            
        Returns:
            List[str]: Extracted keywords
        """
        nlp = get_spacy_model(lang)
        doc = nlp(text[:10000])
        
        # Count terms
        term_counts: Dict[str, int] = {}
        
        # Add noun chunks
        for chunk in doc.noun_chunks:
            key = chunk.lemma_.lower().strip()
            if len(key) > 2 and not key.isdigit():
                term_counts[key] = term_counts.get(key, 0) + 1
        
        # Add named entities (weighted higher)
        for ent in doc.ents:
            key = ent.text.lower().strip()
            if len(key) > 2:
                term_counts[key] = term_counts.get(key, 0) + 2
        
        # Sort by frequency and return top N
        sorted_terms = sorted(
            term_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [term for term, count in sorted_terms[:top_n]]
    
    def detect_manipulation_markers(
        self,
        text: str,
        lang: str
    ) -> List[CognitiveMarkerDTO]:
        """
        Detect manipulation markers in text.
        
        Uses configured keywords to identify propaganda
        techniques and manipulation patterns.
        
        Args:
            text: Text to analyze
            lang: Language code
            
        Returns:
            List[CognitiveMarkerDTO]: Detected markers
        """
        markers = []
        text_lower = text.lower()
        
        # Get manipulation markers from config
        manipulation_config = self.keywords_config.get("manipulation_markers", {})
        
        for marker_type, lang_keywords in manipulation_config.items():
            # Get keywords for language (fallback to English)
            keywords = lang_keywords.get(lang, lang_keywords.get("en", []))
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    # Find position in text
                    pos = text_lower.find(keyword_lower)
                    
                    markers.append(CognitiveMarkerDTO(
                        marker_type=marker_type,
                        marker_category="manipulation",
                        confidence=0.7,
                        severity=Severity.MEDIUM,
                        evidence_text=keyword,
                        evidence_start=pos,
                        evidence_end=pos + len(keyword)
                    ))
        
        return markers
    
    def detect_narratives(
        self,
        text: str,
        lang: str
    ) -> List[NarrativeMatch]:
        """
        Detect narrative themes in text.
        
        Matches text against configured narrative keywords
        to identify disinformation themes.
        
        Args:
            text: Text to analyze
            lang: Language code
            
        Returns:
            List[NarrativeMatch]: Detected narrative matches
        """
        detected = []
        text_lower = text.lower()
        
        narratives_config = self.keywords_config.get("narratives", {})
        min_matches = self.keywords_config.get("settings", {}).get(
            "min_matches_for_narrative", 2
        )
        
        for narrative_id, narrative_info in narratives_config.items():
            # Get keywords for language
            keywords = narrative_info.get("keywords", {}).get(lang, [])
            if not keywords:
                keywords = narrative_info.get("keywords", {}).get("en", [])
            
            if not keywords:
                continue
            
            # Count keyword matches
            matched_keywords = [
                kw for kw in keywords 
                if kw.lower() in text_lower
            ]
            
            if len(matched_keywords) >= min_matches:
                confidence = min(len(matched_keywords) / len(keywords), 1.0)
                
                detected.append(NarrativeMatch(
                    narrative_id=narrative_id,
                    narrative_name=narrative_info.get("name", narrative_id),
                    confidence=round(confidence, 4),
                    matched_keywords=matched_keywords
                ))
        
        # Sort by confidence
        detected.sort(key=lambda x: x.confidence, reverse=True)
        return detected
    
    def detect_cognitive_markers(
        self,
        text: str,
        lang: str
    ) -> List[CognitiveMarkerDTO]:
        """
        Detect cognitive warfare markers using DISARM framework.
        
        Args:
            text: Text to analyze
            lang: Language code
            
        Returns:
            List[CognitiveMarkerDTO]: Detected cognitive markers
        """
        markers = []
        text_lower = text.lower()
        
        # Check assessment phase indicators
        assess_config = self.cognitive_config.get("assess", {}).get("indicators", {})
        
        for indicator_id, indicator_info in assess_config.items():
            keywords = indicator_info.get("keywords", {}).get(lang, [])
            if not keywords:
                keywords = indicator_info.get("keywords", {}).get("en", [])
            
            matches = []
            for kw in keywords:
                if kw.lower() in text_lower:
                    pos = text_lower.find(kw.lower())
                    matches.append({"keyword": kw, "position": pos})
            
            if matches:
                # Map severity string to enum
                severity_str = indicator_info.get("severity", "medium")
                severity = Severity(severity_str) if severity_str in [s.value for s in Severity] else Severity.MEDIUM
                
                markers.append(CognitiveMarkerDTO(
                    marker_type=indicator_id,
                    marker_category="assess",
                    confidence=min(len(matches) * 0.3, 0.9),
                    severity=severity,
                    evidence_text=matches[0]["keyword"] if matches else None,
                    evidence_start=matches[0]["position"] if matches else None
                ))
        
        return markers
    
    def analyze_content(self, content: Content) -> Optional[NLPAnalysisResult]:
        """
        Perform full NLP analysis on content.
        
        Args:
            content: Content entity to analyze
            
        Returns:
            NLPAnalysisResult: Analysis results or None on failure
        """
        if not content.text_content:
            logger.debug(f"Skipping empty content: {content.id}")
            return None
        
        text = content.text_content
        
        try:
            # Detect language
            lang, lang_confidence = self.detect_language(text)
            
            # Analyze sentiment
            sentiment = self.analyze_sentiment(text, lang)
            
            # Extract entities
            entities = self.extract_entities(text, lang)
            
            # Extract keywords
            keywords = self.extract_keywords(text, lang)
            
            # Detect manipulation markers
            manipulation_markers = self.detect_manipulation_markers(text, lang)
            
            # Detect narratives
            narratives = self.detect_narratives(text, lang)
            
            # Detect cognitive markers
            cognitive_markers = self.detect_cognitive_markers(text, lang)
            
            # Determine if propaganda
            total_markers = len(manipulation_markers) + len(cognitive_markers)
            is_propaganda = total_markers >= 2
            propaganda_confidence = min(total_markers * 0.2, 0.95) if total_markers > 0 else 0.0
            
            # Create NLP analysis record
            nlp_analysis = NLPAnalysis(
                content_id=content.id,
                sentiment_score=sentiment.score,
                sentiment_label=sentiment.label.value,
                sentiment_confidence=sentiment.confidence,
                entities=[e.__dict__ for e in entities],
                keywords=keywords,
                is_propaganda=is_propaganda,
                propaganda_confidence=propaganda_confidence,
                propaganda_techniques=[m.marker_type for m in manipulation_markers],
                detected_language=lang,
                language_confidence=lang_confidence,
                model_version=self._model_version
            )
            self.session.add(nlp_analysis)
            
            # Store cognitive markers
            for marker in cognitive_markers:
                cm = CognitiveMarker(
                    content_id=content.id,
                    marker_type=marker.marker_type,
                    marker_category=marker.marker_category,
                    confidence=marker.confidence,
                    severity=marker.severity.value,
                    evidence_text=marker.evidence_text,
                    evidence_start=marker.evidence_start,
                    evidence_end=marker.evidence_end,
                    detector_version=self._model_version
                )
                self.session.add(cm)
            
            # Link narratives
            for narrative in narratives:
                db_narrative = self.session.query(Narrative).filter(
                    Narrative.name == narrative.narrative_name
                ).first()
                
                if db_narrative:
                    cn = ContentNarrative(
                        content_id=content.id,
                        narrative_id=db_narrative.id,
                        confidence=narrative.confidence
                    )
                    self.session.add(cn)
            
            # Mark content as analyzed
            content.is_analyzed = True
            content.analysis_version = 1
            
            self.session.commit()
            
            return NLPAnalysisResult(
                content_id=str(content.id),
                sentiment=sentiment,
                entities=entities,
                keywords=keywords,
                detected_language=lang,
                language_confidence=lang_confidence,
                is_propaganda=is_propaganda,
                propaganda_confidence=propaganda_confidence,
                propaganda_techniques=[m.marker_type for m in manipulation_markers]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing content {content.id}: {e}")
            self.session.rollback()
            return None
    
    def analyze_unprocessed(self, limit: int = 500) -> AnalysisResult:
        """
        Analyze unprocessed content items.
        
        Args:
            limit: Maximum items to process
            
        Returns:
            AnalysisResult: Summary of analysis run
        """
        start_time = datetime.utcnow()
        
        # Get unanalyzed content
        contents = self.session.query(Content).filter(
            Content.is_analyzed == False
        ).limit(limit).all()
        
        logger.info(f"Analyzing {len(contents)} content items...")
        
        analyzed = 0
        errors = 0
        
        for content in contents:
            result = self.analyze_content(content)
            if result:
                analyzed += 1
            else:
                errors += 1
        
        # Get remaining count
        remaining = self.session.query(Content).filter(
            Content.is_analyzed == False
        ).count()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            f"Analysis complete: {analyzed} analyzed, "
            f"{errors} errors, {remaining} remaining in {duration:.1f}s"
        )
        
        return AnalysisResult(
            timestamp=start_time,
            analyzed_count=analyzed,
            errors_count=errors,
            remaining_count=remaining,
            duration_seconds=duration
        )
    
    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Entry point for standalone execution."""
    logger.info("=== Doppelganger Tracker - NLP Analyzer ===")
    
    analyzer = NLPAnalyzer()
    
    try:
        result = analyzer.analyze_unprocessed(limit=500)
        logger.info(f"Analysis result: {result}")
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
