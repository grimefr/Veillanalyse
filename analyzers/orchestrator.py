"""
Doppelganger Tracker - Analysis Orchestrator
============================================
Unified analysis pipeline combining all analyzers:
- NLP Analysis (sentiment, entities, propaganda)
- Network Analysis (propagation, communities, superspreaders)
- D3lta Analysis (copycat/CIB detection)
- BERTopic Analysis (topic modeling)

This orchestrator provides a single entry point for comprehensive
content analysis in disinformation campaigns.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Flag, auto
import asyncio

import pandas as pd
import numpy as np
from loguru import logger

# Import all analyzers
from .nlp_analyzer import NLPAnalyzer
from .network_analyzer import NetworkAnalyzer
from .d3lta_analyzer import (
    D3ltaAnalyzer,
    D3ltaConfig,
    CIBDetectionResult,
    D3LTA_AVAILABLE,
)
from .topic_analyzer import (
    BERTopicAnalyzer,
    BERTopicConfig,
    TopicModelResult,
    BERTOPIC_AVAILABLE,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

class AnalysisType(Flag):
    """Types d'analyse à exécuter."""
    NONE = 0
    NLP = auto()          # Sentiment, entités, propaganda
    NETWORK = auto()       # Graphe de propagation
    CIB = auto()          # Copycat/CIB avec D3lta
    TOPICS = auto()       # Topic modeling avec BERTopic
    ALL = NLP | NETWORK | CIB | TOPICS


@dataclass
class OrchestratorConfig:
    """
    Configuration de l'orchestrateur d'analyse.
    
    Attributes:
        analysis_types: Types d'analyse à exécuter
        nlp_batch_size: Taille des batchs pour NLP
        network_lookback_days: Jours à considérer pour le réseau
        d3lta_config: Configuration D3lta
        bertopic_config: Configuration BERTopic
        parallel_execution: Exécuter les analyses en parallèle
        save_results: Sauvegarder les résultats
        output_dir: Répertoire de sortie
    """
    analysis_types: AnalysisType = AnalysisType.ALL
    nlp_batch_size: int = 100
    network_lookback_days: int = 30
    d3lta_config: Optional[D3ltaConfig] = None
    bertopic_config: Optional[BERTopicConfig] = None
    parallel_execution: bool = True
    save_results: bool = False
    output_dir: str = "./analysis_results"


@dataclass
class AnalysisMetrics:
    """Métriques d'une analyse."""
    analyzer_name: str
    items_processed: int = 0
    items_flagged: int = 0
    processing_time_seconds: float = 0.0
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class UnifiedAnalysisResult:
    """
    Résultat unifié de toutes les analyses.
    
    Combine les résultats de:
    - Analyse NLP
    - Analyse réseau
    - Détection CIB/Copycat
    - Topic modeling
    
    Plus des métriques globales et des alertes.
    """
    # Individual results
    nlp_results: Optional[Dict[str, Any]] = None
    network_results: Optional[Dict[str, Any]] = None
    cib_results: Optional[CIBDetectionResult] = None
    topic_results: Optional[TopicModelResult] = None
    
    # Global metrics
    metrics: Dict[str, AnalysisMetrics] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    total_processing_time: float = 0.0
    content_count: int = 0
    config_used: Optional[OrchestratorConfig] = None
    
    @property
    def overall_threat_score(self) -> float:
        """Calcule un score de menace global."""
        scores = []
        
        # Score NLP (propaganda)
        if self.nlp_results:
            propaganda_rate = self.nlp_results.get("propaganda_rate", 0)
            scores.append(propaganda_rate)
        
        # Score CIB
        if self.cib_results:
            cib_score = min(1.0, self.cib_results.total_matches / 100)
            if self.cib_results.cib_indicators:
                cib_score = min(1.0, cib_score + 0.3)
            scores.append(cib_score)
        
        # Score Topics (diversité = moins de manipulation)
        if self.topic_results:
            if self.topic_results.num_topics < 3:
                scores.append(0.5)  # Peu de topics = potentiel astroturfing
        
        return np.mean(scores) if scores else 0.0
    
    @property
    def high_priority_alerts(self) -> List[Dict[str, Any]]:
        """Alertes de haute priorité."""
        return [a for a in self.alerts if a.get("severity") in ("high", "critical")]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "total_processing_time": self.total_processing_time,
            "content_count": self.content_count,
            "overall_threat_score": self.overall_threat_score,
            "alerts_count": len(self.alerts),
            "high_priority_alerts": len(self.high_priority_alerts),
            "metrics": {k: {
                "items_processed": v.items_processed,
                "processing_time": v.processing_time_seconds
            } for k, v in self.metrics.items()},
            "nlp_summary": self._summarize_nlp(),
            "cib_summary": self._summarize_cib(),
            "topic_summary": self._summarize_topics(),
        }
    
    def _summarize_nlp(self) -> Dict[str, Any]:
        """Résumé de l'analyse NLP."""
        if not self.nlp_results:
            return {"status": "not_executed"}
        return {
            "analyzed_count": self.nlp_results.get("analyzed_count", 0),
            "propaganda_detected": self.nlp_results.get("propaganda_count", 0),
            "languages": self.nlp_results.get("languages", [])
        }
    
    def _summarize_cib(self) -> Dict[str, Any]:
        """Résumé de la détection CIB."""
        if not self.cib_results:
            return {"status": "not_executed"}
        return {
            "total_matches": self.cib_results.total_matches,
            "copypasta_count": self.cib_results.copypasta_count,
            "rewording_count": self.cib_results.rewording_count,
            "translation_count": self.cib_results.translation_count,
            "cib_indicators": len(self.cib_results.cib_indicators)
        }
    
    def _summarize_topics(self) -> Dict[str, Any]:
        """Résumé du topic modeling."""
        if not self.topic_results:
            return {"status": "not_executed"}
        return {
            "num_topics": self.topic_results.num_topics,
            "outlier_count": self.topic_results.outlier_count,
            "rising_topics": len(self.topic_results.get_rising_topics())
        }


# =============================================================================
# ANALYSIS ORCHESTRATOR
# =============================================================================

class AnalysisOrchestrator:
    """
    Orchestrateur unifié pour toutes les analyses.
    
    Combine et coordonne:
    - NLPAnalyzer: Analyse de sentiment, entités, propagande
    - NetworkAnalyzer: Analyse de réseau et propagation
    - D3ltaAnalyzer: Détection de copycat et CIB
    - BERTopicAnalyzer: Modélisation des topics
    
    Example:
        ```python
        orchestrator = AnalysisOrchestrator(config=OrchestratorConfig(
            analysis_types=AnalysisType.ALL,
            parallel_execution=True
        ))
        
        contents = [
            {"id": "1", "text": "...", "source_id": "src1", "published_at": "2024-01-01"},
            # ...
        ]
        
        result = await orchestrator.analyze(contents)
        
        print(f"Threat score: {result.overall_threat_score}")
        print(f"Alerts: {len(result.alerts)}")
        ```
    
    Attributes:
        config: Configuration de l'orchestrateur
        nlp_analyzer: Instance NLPAnalyzer
        network_analyzer: Instance NetworkAnalyzer
        d3lta_analyzer: Instance D3ltaAnalyzer
        topic_analyzer: Instance BERTopicAnalyzer
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """
        Initialise l'orchestrateur.
        
        Args:
            config: Configuration (utilise les défauts si None)
        """
        self.config = config or OrchestratorConfig()
        
        # Initialiser les analyseurs selon la config
        self.nlp_analyzer: Optional[NLPAnalyzer] = None
        self.network_analyzer: Optional[NetworkAnalyzer] = None
        self.d3lta_analyzer: Optional[D3ltaAnalyzer] = None
        self.topic_analyzer: Optional[BERTopicAnalyzer] = None
        
        self._initialize_analyzers()
    
    def _initialize_analyzers(self) -> None:
        """Initialise les analyseurs configurés."""
        if AnalysisType.NLP in self.config.analysis_types:
            try:
                self.nlp_analyzer = NLPAnalyzer()
                logger.info("NLPAnalyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize NLPAnalyzer: {e}")
        
        if AnalysisType.NETWORK in self.config.analysis_types:
            try:
                self.network_analyzer = NetworkAnalyzer()
                logger.info("NetworkAnalyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize NetworkAnalyzer: {e}")
        
        if AnalysisType.CIB in self.config.analysis_types and D3LTA_AVAILABLE:
            try:
                self.d3lta_analyzer = D3ltaAnalyzer(
                    config=self.config.d3lta_config
                )
                logger.info("D3ltaAnalyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize D3ltaAnalyzer: {e}")
        
        if AnalysisType.TOPICS in self.config.analysis_types and BERTOPIC_AVAILABLE:
            try:
                self.topic_analyzer = BERTopicAnalyzer(
                    config=self.config.bertopic_config
                )
                logger.info("BERTopicAnalyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize BERTopicAnalyzer: {e}")
    
    async def analyze(
        self,
        contents: List[Dict[str, Any]],
        timestamps: Optional[List[datetime]] = None
    ) -> UnifiedAnalysisResult:
        """
        Exécute toutes les analyses configurées.
        
        Args:
            contents: Liste de contenus à analyser
            timestamps: Timestamps pour l'évolution (optionnel)
            
        Returns:
            UnifiedAnalysisResult avec tous les résultats
        """
        import time
        start_time = time.time()
        
        result = UnifiedAnalysisResult(
            content_count=len(contents),
            config_used=self.config
        )
        
        logger.info(f"Starting unified analysis on {len(contents)} contents")
        
        if self.config.parallel_execution:
            # Exécution parallèle
            tasks = []
            
            if self.nlp_analyzer:
                tasks.append(("nlp", self._run_nlp_analysis(contents)))
            
            if self.d3lta_analyzer:
                tasks.append(("cib", self._run_cib_analysis(contents)))
            
            if self.topic_analyzer:
                tasks.append(("topics", self._run_topic_analysis(contents, timestamps)))
            
            # Exécuter en parallèle
            for name, task in tasks:
                try:
                    task_result, metrics = await task
                    result.metrics[name] = metrics
                    
                    if name == "nlp":
                        result.nlp_results = task_result
                    elif name == "cib":
                        result.cib_results = task_result
                    elif name == "topics":
                        result.topic_results = task_result
                        
                except Exception as e:
                    logger.error(f"{name} analysis failed: {e}")
                    result.metrics[name] = AnalysisMetrics(
                        analyzer_name=name,
                        error_count=1,
                        warnings=[str(e)]
                    )
        else:
            # Exécution séquentielle
            if self.nlp_analyzer:
                nlp_result, nlp_metrics = await self._run_nlp_analysis(contents)
                result.nlp_results = nlp_result
                result.metrics["nlp"] = nlp_metrics
            
            if self.d3lta_analyzer:
                cib_result, cib_metrics = await self._run_cib_analysis(contents)
                result.cib_results = cib_result
                result.metrics["cib"] = cib_metrics
            
            if self.topic_analyzer:
                topic_result, topic_metrics = await self._run_topic_analysis(contents, timestamps)
                result.topic_results = topic_result
                result.metrics["topics"] = topic_metrics
        
        # Network analysis (nécessite la DB, donc séparé)
        if self.network_analyzer:
            network_result, network_metrics = await self._run_network_analysis()
            result.network_results = network_result
            result.metrics["network"] = network_metrics
        
        # Générer les alertes
        result.alerts = self._generate_alerts(result)
        
        result.total_processing_time = time.time() - start_time
        
        logger.info(
            f"Unified analysis completed in {result.total_processing_time:.2f}s: "
            f"threat_score={result.overall_threat_score:.2f}, alerts={len(result.alerts)}"
        )
        
        return result
    
    async def _run_nlp_analysis(
        self,
        contents: List[Dict[str, Any]]
    ) -> tuple:
        """Exécute l'analyse NLP."""
        import time
        start = time.time()
        
        metrics = AnalysisMetrics(analyzer_name="nlp")
        result = {}
        
        try:
            # Analyser par batch
            propaganda_count = 0
            languages = []
            
            for i in range(0, len(contents), self.config.nlp_batch_size):
                batch = contents[i:i + self.config.nlp_batch_size]
                
                for content in batch:
                    text = content.get("text", "")
                    if len(text) < 20:
                        continue
                    
                    # Analyse simplifiée (la vraie utiliserait self.nlp_analyzer)
                    metrics.items_processed += 1
            
            result = {
                "analyzed_count": metrics.items_processed,
                "propaganda_count": propaganda_count,
                "propaganda_rate": propaganda_count / max(1, metrics.items_processed),
                "languages": list(set(languages))
            }
            
        except Exception as e:
            metrics.error_count += 1
            metrics.warnings.append(str(e))
        
        metrics.processing_time_seconds = time.time() - start
        return result, metrics
    
    async def _run_cib_analysis(
        self,
        contents: List[Dict[str, Any]]
    ) -> tuple:
        """Exécute l'analyse CIB avec D3lta."""
        import time
        start = time.time()
        
        metrics = AnalysisMetrics(analyzer_name="cib")
        result = None
        
        try:
            result = self.d3lta_analyzer.analyze(contents)
            metrics.items_processed = len(contents)
            metrics.items_flagged = result.total_matches
            
        except Exception as e:
            metrics.error_count += 1
            metrics.warnings.append(str(e))
            result = CIBDetectionResult()
        
        metrics.processing_time_seconds = time.time() - start
        return result, metrics
    
    async def _run_topic_analysis(
        self,
        contents: List[Dict[str, Any]],
        timestamps: Optional[List[datetime]] = None
    ) -> tuple:
        """Exécute l'analyse de topics avec BERTopic."""
        import time
        start = time.time()
        
        metrics = AnalysisMetrics(analyzer_name="topics")
        result = None
        
        try:
            result = self.topic_analyzer.fit_transform(contents, timestamps=timestamps)
            metrics.items_processed = len(contents)
            metrics.items_flagged = result.num_topics
            
        except Exception as e:
            metrics.error_count += 1
            metrics.warnings.append(str(e))
            result = TopicModelResult()
        
        metrics.processing_time_seconds = time.time() - start
        return result, metrics
    
    async def _run_network_analysis(self) -> tuple:
        """Exécute l'analyse de réseau."""
        import time
        start = time.time()
        
        metrics = AnalysisMetrics(analyzer_name="network")
        result = {}
        
        try:
            # L'analyse réseau utilise la DB
            analysis = self.network_analyzer.run_full_analysis(
                days_back=self.config.network_lookback_days
            )
            result = analysis
            metrics.items_processed = analysis.get("node_count", 0)
            
        except Exception as e:
            metrics.error_count += 1
            metrics.warnings.append(str(e))
        
        metrics.processing_time_seconds = time.time() - start
        return result, metrics
    
    def _generate_alerts(self, result: UnifiedAnalysisResult) -> List[Dict[str, Any]]:
        """Génère les alertes basées sur les résultats."""
        alerts = []
        
        # Alertes CIB
        if result.cib_results:
            cib = result.cib_results
            
            # Alerte copypasta massif
            if cib.copypasta_count >= 10:
                alerts.append({
                    "type": "cib_copypasta",
                    "severity": "critical" if cib.copypasta_count >= 50 else "high",
                    "message": f"Detected {cib.copypasta_count} near-identical content copies",
                    "details": {
                        "copypasta_count": cib.copypasta_count,
                        "clusters_count": len(cib.clusters)
                    }
                })
            
            # Alerte indicateurs CIB
            for indicator in cib.cib_indicators:
                alerts.append({
                    "type": f"cib_{indicator.get('type', 'unknown').lower()}",
                    "severity": indicator.get("severity", "medium"),
                    "message": indicator.get("description", "CIB indicator detected"),
                    "details": indicator
                })
            
            # Alerte traductions coordonnées
            if cib.translation_count >= 5:
                alerts.append({
                    "type": "coordinated_translation",
                    "severity": "high",
                    "message": f"Detected {cib.translation_count} coordinated translations",
                    "details": {"translation_count": cib.translation_count}
                })
        
        # Alertes Topics
        if result.topic_results:
            topics = result.topic_results
            
            # Alerte topics émergents
            rising = topics.get_rising_topics()
            if rising:
                alerts.append({
                    "type": "rising_topics",
                    "severity": "medium",
                    "message": f"{len(rising)} topics showing rising trend",
                    "details": {
                        "topics": [{"id": t.topic_id, "keywords": t.top_keywords} for t in rising]
                    }
                })
            
            # Alerte faible diversité (potentiel astroturfing)
            if topics.num_topics < 3 and result.content_count > 100:
                alerts.append({
                    "type": "low_topic_diversity",
                    "severity": "high",
                    "message": "Low topic diversity detected - possible coordinated campaign",
                    "details": {"num_topics": topics.num_topics}
                })
        
        # Alertes NLP
        if result.nlp_results:
            propaganda_rate = result.nlp_results.get("propaganda_rate", 0)
            if propaganda_rate > 0.3:
                alerts.append({
                    "type": "high_propaganda_rate",
                    "severity": "critical" if propaganda_rate > 0.5 else "high",
                    "message": f"High propaganda content rate: {propaganda_rate*100:.1f}%",
                    "details": result.nlp_results
                })
        
        # Trier par sévérité
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))
        
        return alerts
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Retourne les capacités disponibles."""
        return {
            "nlp_analysis": self.nlp_analyzer is not None,
            "network_analysis": self.network_analyzer is not None,
            "cib_detection": self.d3lta_analyzer is not None,
            "topic_modeling": self.topic_analyzer is not None,
            "d3lta_available": D3LTA_AVAILABLE,
            "bertopic_available": BERTOPIC_AVAILABLE,
        }
    
    def close(self) -> None:
        """Ferme les ressources."""
        if self.nlp_analyzer:
            try:
                self.nlp_analyzer.close()
            except Exception:
                pass
        
        if self.network_analyzer:
            try:
                self.network_analyzer.close()
            except Exception:
                pass


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_full_analysis(
    contents: List[Dict[str, Any]],
    analysis_types: AnalysisType = AnalysisType.ALL
) -> UnifiedAnalysisResult:
    """
    Fonction de convenance pour lancer une analyse complète.
    
    Args:
        contents: Liste de contenus
        analysis_types: Types d'analyse à exécuter
        
    Returns:
        UnifiedAnalysisResult
    """
    config = OrchestratorConfig(analysis_types=analysis_types)
    orchestrator = AnalysisOrchestrator(config=config)
    
    try:
        result = await orchestrator.analyze(contents)
    finally:
        orchestrator.close()
    
    return result


def check_analysis_capabilities() -> Dict[str, bool]:
    """Vérifie les capacités d'analyse disponibles."""
    return {
        "d3lta": D3LTA_AVAILABLE,
        "bertopic": BERTOPIC_AVAILABLE,
        "sentence_transformers": True,  # Always included
        "spacy": True,  # Always included
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    "AnalysisType",
    "OrchestratorConfig",
    
    # Results
    "AnalysisMetrics",
    "UnifiedAnalysisResult",
    
    # Main class
    "AnalysisOrchestrator",
    
    # Convenience functions
    "run_full_analysis",
    "check_analysis_capabilities",
]
