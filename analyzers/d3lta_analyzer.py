"""
Doppelganger Tracker - D3lta Integration Module
================================================
Détection de Coordinated Inauthentic Behavior (CIB) et Copycat
utilisant la bibliothèque D3lta développée par VIGINUM.

D3lta: https://github.com/VIGINUM-FR/D3lta
Paper: https://arxiv.org/abs/2312.17338

D3lta détecte 3 types de contenus dupliqués:
- Copypasta: duplicatas quasi-exacts
- Rewording: reformulations
- Translation: traductions

Requirements:
    pip install d3lta pandas numpy

Installation D3lta:
    pip install d3lta
    # ou depuis GitHub:
    pip install git+https://github.com/VIGINUM-FR/D3lta.git
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Protocol
from abc import ABC, abstractmethod
from enum import Enum, auto
import hashlib

import pandas as pd
import numpy as np
from loguru import logger

# =============================================================================
# IMPORTS CONDITIONNELS
# =============================================================================

try:
    from d3lta.faissd3lta import (
        semantic_faiss,
        compute_embeddings,
        create_index_cosine,
    )
    D3LTA_AVAILABLE = True
    logger.info("D3lta library loaded successfully")
except ImportError:
    D3LTA_AVAILABLE = False
    logger.warning(
        "D3lta not installed. Install with: pip install d3lta "
        "or pip install git+https://github.com/VIGINUM-FR/D3lta.git"
    )

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


# =============================================================================
# ENUMS & DATA STRUCTURES
# =============================================================================

class DuplicateType(Enum):
    """Types de duplicata détectés par D3lta."""
    COPYPASTA = "copy-pasta"      # Duplicata quasi-exact
    REWORDING = "rewording"        # Reformulation
    TRANSLATION = "translation"    # Traduction
    UNKNOWN = "unknown"


class CIBIndicator(Enum):
    """Indicateurs de comportement coordonné inauthentique."""
    TEMPORAL_BURST = auto()        # Publication en rafale
    IDENTICAL_CONTENT = auto()     # Contenu identique
    SYNCHRONIZED_POSTING = auto()  # Publication synchronisée
    NETWORK_AMPLIFICATION = auto() # Amplification réseau
    TEMPLATE_USAGE = auto()        # Utilisation de templates


@dataclass(frozen=True)
class D3ltaConfig:
    """
    Configuration pour l'analyse D3lta.
    
    Attributes:
        threshold_grapheme: Seuil pour la similarité graphémique (défaut: 0.693)
        threshold_language: Seuil pour la similarité intra-langue (défaut: 0.715)
        threshold_semantic: Seuil pour la similarité sémantique (défaut: 0.85)
        min_text_length: Longueur minimum de texte à analyser
        embedding_model: Modèle d'embedding (None = Universal Sentence Encoder)
        save_embeddings: Chemin pour sauvegarder les embeddings
    """
    threshold_grapheme: float = 0.693
    threshold_language: float = 0.715
    threshold_semantic: float = 0.85
    min_text_length: int = 10
    embedding_model: Optional[str] = None
    save_embeddings: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour D3lta."""
        return {
            "threshold_grapheme": self.threshold_grapheme,
            "threshold_language": self.threshold_language,
            "threshold_semantic": self.threshold_semantic,
            "min_size_txt": self.min_text_length,
        }


@dataclass
class DuplicateMatch:
    """
    Match de contenu dupliqué détecté par D3lta.
    
    Attributes:
        source_id: ID du contenu source
        target_id: ID du contenu cible
        similarity_score: Score de similarité (0-1)
        duplicate_type: Type de duplicata
        language_source: Langue du source
        language_target: Langue de la cible
        levenshtein_score: Score de distance Levenshtein (si disponible)
    """
    source_id: str
    target_id: str
    similarity_score: float
    duplicate_type: DuplicateType
    language_source: str = "unknown"
    language_target: str = "unknown"
    levenshtein_score: Optional[float] = None
    text_source_preview: str = ""
    text_target_preview: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_cross_language(self) -> bool:
        """Vérifie si c'est une traduction cross-lingue."""
        return self.language_source != self.language_target
    
    @property
    def is_high_similarity(self) -> bool:
        """Vérifie si la similarité est élevée."""
        return self.similarity_score >= 0.9
    
    @property
    def pair_id(self) -> str:
        """ID unique de la paire."""
        ids = sorted([self.source_id, self.target_id])
        return f"{ids[0]}-{ids[1]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "similarity_score": self.similarity_score,
            "duplicate_type": self.duplicate_type.value,
            "language_source": self.language_source,
            "language_target": self.language_target,
            "levenshtein_score": self.levenshtein_score,
            "is_cross_language": self.is_cross_language,
            "detected_at": self.detected_at.isoformat()
        }


@dataclass
class ContentCluster:
    """
    Cluster de contenus similaires.
    
    Attributes:
        cluster_id: Identifiant du cluster
        content_ids: Liste des IDs de contenus
        centroid_id: ID du contenu central
        languages: Langues présentes dans le cluster
        duplicate_types: Types de duplicatas dans le cluster
    """
    cluster_id: int
    content_ids: List[str] = field(default_factory=list)
    centroid_id: Optional[str] = None
    languages: List[str] = field(default_factory=list)
    duplicate_types: List[DuplicateType] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def size(self) -> int:
        """Taille du cluster."""
        return len(self.content_ids)
    
    @property
    def is_multilingual(self) -> bool:
        """Vérifie si le cluster est multilingue."""
        return len(set(self.languages)) > 1
    
    def add_content(self, content_id: str, language: str = "unknown") -> None:
        """Ajoute un contenu au cluster."""
        if content_id not in self.content_ids:
            self.content_ids.append(content_id)
            self.languages.append(language)


@dataclass
class CIBDetectionResult:
    """
    Résultat complet de la détection CIB avec D3lta.
    
    Attributes:
        matches: Liste des matches de duplicatas
        clusters: Clusters de contenus similaires
        cib_indicators: Indicateurs CIB détectés
        statistics: Statistiques de l'analyse
        config_used: Configuration utilisée
    """
    matches: List[DuplicateMatch] = field(default_factory=list)
    clusters: List[ContentCluster] = field(default_factory=list)
    cib_indicators: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    config_used: Optional[D3ltaConfig] = None
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    processing_time_seconds: float = 0.0
    
    @property
    def total_matches(self) -> int:
        """Nombre total de matches."""
        return len(self.matches)
    
    @property
    def copypasta_count(self) -> int:
        """Nombre de copypasta détectés."""
        return sum(1 for m in self.matches if m.duplicate_type == DuplicateType.COPYPASTA)
    
    @property
    def rewording_count(self) -> int:
        """Nombre de rewordings détectés."""
        return sum(1 for m in self.matches if m.duplicate_type == DuplicateType.REWORDING)
    
    @property
    def translation_count(self) -> int:
        """Nombre de traductions détectées."""
        return sum(1 for m in self.matches if m.duplicate_type == DuplicateType.TRANSLATION)
    
    @property
    def cross_language_matches(self) -> List[DuplicateMatch]:
        """Matches cross-lingues."""
        return [m for m in self.matches if m.is_cross_language]
    
    def get_matches_by_type(self, dup_type: DuplicateType) -> List[DuplicateMatch]:
        """Récupère les matches par type."""
        return [m for m in self.matches if m.duplicate_type == dup_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "total_matches": self.total_matches,
            "copypasta_count": self.copypasta_count,
            "rewording_count": self.rewording_count,
            "translation_count": self.translation_count,
            "clusters_count": len(self.clusters),
            "cib_indicators": self.cib_indicators,
            "statistics": self.statistics,
            "timestamp": self.analysis_timestamp.isoformat(),
            "processing_time_seconds": self.processing_time_seconds
        }


# =============================================================================
# D3LTA ANALYZER - Main Interface
# =============================================================================

class D3ltaAnalyzer:
    """
    Analyseur principal utilisant D3lta pour la détection de CIB.
    
    Cette classe encapsule la bibliothèque D3lta de VIGINUM pour:
    - Détecter les contenus dupliqués (copypasta, rewording, translation)
    - Identifier les clusters de contenus similaires
    - Détecter les comportements coordonnés inauthentiques
    
    Example:
        ```python
        analyzer = D3ltaAnalyzer(config=D3ltaConfig(
            threshold_semantic=0.85,
            min_text_length=20
        ))
        
        contents = [
            {"id": "1", "text": "Les chats sont gris", "source_id": "src1"},
            {"id": "2", "text": "Cats are grey", "source_id": "src2"},
            {"id": "3", "text": "Les chats ne sont pas gris", "source_id": "src3"},
        ]
        
        result = analyzer.analyze(contents)
        print(f"Found {result.total_matches} matches")
        ```
    
    Attributes:
        config: Configuration D3lta
        embedding_model: Modèle d'embedding optionnel
        _embeddings_cache: Cache des embeddings calculés
    """
    
    def __init__(
        self,
        config: Optional[D3ltaConfig] = None,
        embedding_model_name: Optional[str] = None
    ):
        """
        Initialise l'analyseur D3lta.
        
        Args:
            config: Configuration D3lta (défaut si None)
            embedding_model_name: Nom du modèle sentence-transformers
                                  (None = Universal Sentence Encoder de D3lta)
        """
        self.config = config or D3ltaConfig()
        self._embeddings_cache: Dict[str, np.ndarray] = {}
        self._sentence_transformer = None
        
        # Vérifier disponibilité D3lta
        if not D3LTA_AVAILABLE:
            logger.error(
                "D3lta is not available. Install with: pip install d3lta"
            )
        
        # Charger modèle d'embedding personnalisé si spécifié
        if embedding_model_name and SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.info(f"Loading embedding model: {embedding_model_name}")
            self._sentence_transformer = SentenceTransformer(embedding_model_name)
        elif embedding_model_name:
            logger.warning(
                "sentence-transformers not available, using D3lta default embeddings"
            )
    
    @property
    def is_available(self) -> bool:
        """Vérifie si D3lta est disponible."""
        return D3LTA_AVAILABLE
    
    def analyze(
        self,
        contents: List[Dict[str, Any]],
        detect_cib: bool = True,
        compute_clusters: bool = True
    ) -> CIBDetectionResult:
        """
        Analyse une liste de contenus pour détecter les duplicatas et CIB.
        
        Args:
            contents: Liste de contenus avec 'id', 'text', optionnel: 'source_id', 'published_at'
            detect_cib: Activer la détection CIB
            compute_clusters: Calculer les clusters
            
        Returns:
            CIBDetectionResult avec matches, clusters et indicateurs
        """
        import time
        start_time = time.time()
        
        if not self.is_available:
            logger.error("D3lta not available, returning empty result")
            return CIBDetectionResult(config_used=self.config)
        
        # Préparer les données pour D3lta
        df = self._prepare_dataframe(contents)
        
        if len(df) < 2:
            logger.warning("Not enough content for analysis (minimum 2)")
            return CIBDetectionResult(
                config_used=self.config,
                statistics={"input_count": len(contents), "valid_count": len(df)}
            )
        
        logger.info(f"Analyzing {len(df)} contents with D3lta")
        
        # Calculer embeddings personnalisés si modèle spécifié
        df_embeddings = None
        if self._sentence_transformer is not None:
            df_embeddings = self._compute_custom_embeddings(df)
        
        # Exécuter D3lta semantic_faiss
        try:
            matches_df, clusters_df = self._run_d3lta_analysis(df, df_embeddings)
        except Exception as e:
            logger.error(f"D3lta analysis error: {e}")
            return CIBDetectionResult(
                config_used=self.config,
                statistics={"error": str(e)}
            )
        
        # Convertir les résultats
        matches = self._convert_matches(matches_df, contents)
        clusters = self._convert_clusters(clusters_df) if compute_clusters else []
        
        # Détecter les indicateurs CIB
        cib_indicators = []
        if detect_cib:
            cib_indicators = self._detect_cib_indicators(matches, contents)
        
        # Calculer les statistiques
        statistics = self._compute_statistics(matches, clusters, contents)
        
        processing_time = time.time() - start_time
        
        result = CIBDetectionResult(
            matches=matches,
            clusters=clusters,
            cib_indicators=cib_indicators,
            statistics=statistics,
            config_used=self.config,
            processing_time_seconds=processing_time
        )
        
        logger.info(
            f"D3lta analysis completed in {processing_time:.2f}s: "
            f"{result.total_matches} matches, {len(clusters)} clusters"
        )
        
        return result
    
    def find_similar(
        self,
        query_text: str,
        corpus: List[Dict[str, Any]],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Trouve les contenus similaires à un texte requête.
        
        Args:
            query_text: Texte de requête
            corpus: Corpus de contenus
            top_k: Nombre max de résultats
            threshold: Seuil de similarité
            
        Returns:
            Liste de (content_id, similarity_score)
        """
        if not self.is_available:
            return []
        
        # Préparer le corpus
        df_corpus = self._prepare_dataframe(corpus)
        
        if len(df_corpus) == 0:
            return []
        
        # Calculer embeddings
        if self._sentence_transformer:
            corpus_embeddings = self._sentence_transformer.encode(
                df_corpus["text_to_embed"].tolist()
            )
            query_embedding = self._sentence_transformer.encode([query_text])
        else:
            # Utiliser D3lta embeddings
            df_corpus_emb = compute_embeddings(
                df_corpus.rename(columns={"original": "text_to_embed"})
            )
            corpus_embeddings = df_corpus_emb.to_numpy()
            
            query_df = pd.DataFrame([{"text_to_embed": query_text}])
            query_emb = compute_embeddings(query_df)
            query_embedding = query_emb.to_numpy()
        
        # Créer index FAISS et rechercher
        index = create_index_cosine(pd.DataFrame(corpus_embeddings))
        
        limits, distances, indices = index.range_search(
            x=query_embedding.reshape(1, -1).astype('float32'),
            thresh=threshold
        )
        
        # Formatter les résultats
        results = []
        for idx, dist in zip(indices, distances):
            if idx < len(corpus):
                content_id = corpus[idx].get("id", str(idx))
                results.append((content_id, float(dist)))
        
        # Trier par similarité décroissante et limiter
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def _prepare_dataframe(self, contents: List[Dict[str, Any]]) -> pd.DataFrame:
        """Prépare le DataFrame pour D3lta."""
        data = []
        for i, content in enumerate(contents):
            text = content.get("text", "")
            
            # Filtrer les textes trop courts
            if len(text) < self.config.min_text_length:
                continue
            
            data.append({
                "id": content.get("id", str(i)),
                "original": text,
                "source_id": content.get("source_id", "unknown"),
                "published_at": content.get("published_at"),
            })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            df.index = df["id"].astype(str)
        
        return df
    
    def _compute_custom_embeddings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule les embeddings avec le modèle personnalisé."""
        texts = df["original"].tolist()
        embeddings = self._sentence_transformer.encode(texts)
        return pd.DataFrame(embeddings, index=df.index)
    
    def _run_d3lta_analysis(
        self,
        df: pd.DataFrame,
        df_embeddings: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Exécute l'analyse D3lta."""
        kwargs = {
            "df": df.rename(columns={"original": "original"}),
            "min_size_txt": self.config.min_text_length,
            "threshold_grapheme": self.config.threshold_grapheme,
            "threshold_language": self.config.threshold_language,
            "threshold_semantic": self.config.threshold_semantic,
        }
        
        if df_embeddings is not None:
            kwargs["df_embeddings_use"] = df_embeddings
        
        if self.config.save_embeddings:
            kwargs["embeddings_to_save"] = self.config.save_embeddings
        
        matches_df, clusters_df = semantic_faiss(**kwargs)
        
        return matches_df, clusters_df
    
    def _convert_matches(
        self,
        matches_df: pd.DataFrame,
        original_contents: List[Dict[str, Any]]
    ) -> List[DuplicateMatch]:
        """Convertit les matches D3lta en DuplicateMatch."""
        matches = []
        
        if matches_df.empty:
            return matches
        
        # Créer un mapping id -> content
        content_map = {str(c.get("id", i)): c for i, c in enumerate(original_contents)}
        
        for _, row in matches_df.iterrows():
            # Déterminer le type de duplicata
            dup_type_str = row.get("dup_type", "unknown")
            if dup_type_str == "copy-pasta":
                dup_type = DuplicateType.COPYPASTA
            elif dup_type_str == "rewording":
                dup_type = DuplicateType.REWORDING
            elif dup_type_str == "translation":
                dup_type = DuplicateType.TRANSLATION
            else:
                dup_type = DuplicateType.UNKNOWN
            
            source_id = str(row.get("source", ""))
            target_id = str(row.get("target", ""))
            
            # Récupérer les previews
            source_content = content_map.get(source_id, {})
            target_content = content_map.get(target_id, {})
            
            match = DuplicateMatch(
                source_id=source_id,
                target_id=target_id,
                similarity_score=float(row.get("score", 0)),
                duplicate_type=dup_type,
                language_source=str(row.get("language_source", "unknown")),
                language_target=str(row.get("language_target", "unknown")),
                levenshtein_score=row.get("score_lev") if pd.notna(row.get("score_lev")) else None,
                text_source_preview=source_content.get("text", "")[:100],
                text_target_preview=target_content.get("text", "")[:100],
            )
            matches.append(match)
        
        return matches
    
    def _convert_clusters(self, clusters_df: pd.DataFrame) -> List[ContentCluster]:
        """Convertit les clusters D3lta en ContentCluster."""
        clusters = []
        
        if clusters_df.empty or "cluster" not in clusters_df.columns:
            return clusters
        
        # Filtrer les entrées sans cluster
        valid_clusters = clusters_df[clusters_df["cluster"].notna()]
        
        # Grouper par cluster
        for cluster_id, group in valid_clusters.groupby("cluster"):
            cluster = ContentCluster(
                cluster_id=int(cluster_id),
                content_ids=group.index.tolist(),
                languages=group["language"].tolist() if "language" in group.columns else [],
            )
            
            # Définir le centroïde (premier élément)
            if len(cluster.content_ids) > 0:
                cluster.centroid_id = cluster.content_ids[0]
            
            clusters.append(cluster)
        
        return clusters
    
    def _detect_cib_indicators(
        self,
        matches: List[DuplicateMatch],
        contents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Détecte les indicateurs de comportement coordonné."""
        indicators = []
        
        if not matches:
            return indicators
        
        # Créer mapping pour analyse temporelle
        content_map = {str(c.get("id", i)): c for i, c in enumerate(contents)}
        
        # 1. Détecter les bursts temporels
        temporal_bursts = self._detect_temporal_bursts(matches, content_map)
        if temporal_bursts:
            indicators.append({
                "type": CIBIndicator.TEMPORAL_BURST.name,
                "description": "Multiple similar contents posted in short time window",
                "evidence": temporal_bursts,
                "severity": "high" if len(temporal_bursts) > 5 else "medium"
            })
        
        # 2. Détecter les contenus identiques (copypasta massif)
        copypasta_matches = [m for m in matches if m.duplicate_type == DuplicateType.COPYPASTA]
        if len(copypasta_matches) >= 3:
            indicators.append({
                "type": CIBIndicator.IDENTICAL_CONTENT.name,
                "description": f"Found {len(copypasta_matches)} nearly identical contents",
                "count": len(copypasta_matches),
                "severity": "critical" if len(copypasta_matches) > 10 else "high"
            })
        
        # 3. Détecter l'amplification réseau (même source vers multiple cibles)
        amplification = self._detect_network_amplification(matches)
        if amplification:
            indicators.append({
                "type": CIBIndicator.NETWORK_AMPLIFICATION.name,
                "description": "Coordinated content amplification detected",
                "sources": amplification,
                "severity": "high"
            })
        
        # 4. Détecter l'utilisation de templates (traductions coordonnées)
        translations = [m for m in matches if m.duplicate_type == DuplicateType.TRANSLATION]
        if len(translations) >= 3:
            indicators.append({
                "type": CIBIndicator.TEMPLATE_USAGE.name,
                "description": f"Found {len(translations)} coordinated translations",
                "languages": list(set(
                    [m.language_source for m in translations] + 
                    [m.language_target for m in translations]
                )),
                "severity": "high"
            })
        
        return indicators
    
    def _detect_temporal_bursts(
        self,
        matches: List[DuplicateMatch],
        content_map: Dict[str, Dict],
        window_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """Détecte les rafales temporelles de contenus similaires."""
        bursts = []
        
        # Collecter les timestamps des contenus matchés
        timestamps = []
        for match in matches:
            for content_id in [match.source_id, match.target_id]:
                content = content_map.get(content_id, {})
                pub_at = content.get("published_at")
                if pub_at:
                    if isinstance(pub_at, str):
                        try:
                            pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                    timestamps.append((content_id, pub_at))
        
        if len(timestamps) < 3:
            return bursts
        
        # Trier par timestamp
        timestamps.sort(key=lambda x: x[1])
        
        # Détecter les fenêtres avec beaucoup de contenus
        window = timedelta(minutes=window_minutes)
        i = 0
        while i < len(timestamps):
            window_contents = [timestamps[i]]
            j = i + 1
            while j < len(timestamps) and timestamps[j][1] - timestamps[i][1] <= window:
                window_contents.append(timestamps[j])
                j += 1
            
            if len(window_contents) >= 3:
                bursts.append({
                    "start": timestamps[i][1].isoformat(),
                    "end": timestamps[j-1][1].isoformat(),
                    "content_ids": [c[0] for c in window_contents],
                    "count": len(window_contents)
                })
                i = j  # Skip past this burst
            else:
                i += 1
        
        return bursts
    
    def _detect_network_amplification(
        self,
        matches: List[DuplicateMatch],
        min_targets: int = 3
    ) -> List[Dict[str, Any]]:
        """Détecte l'amplification réseau (1 source → N cibles)."""
        from collections import defaultdict
        
        source_targets = defaultdict(set)
        
        for match in matches:
            source_targets[match.source_id].add(match.target_id)
            source_targets[match.target_id].add(match.source_id)
        
        amplifiers = []
        for source_id, targets in source_targets.items():
            if len(targets) >= min_targets:
                amplifiers.append({
                    "source_id": source_id,
                    "target_count": len(targets),
                    "target_ids": list(targets)
                })
        
        return amplifiers
    
    def _compute_statistics(
        self,
        matches: List[DuplicateMatch],
        clusters: List[ContentCluster],
        contents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calcule les statistiques de l'analyse."""
        stats = {
            "input_count": len(contents),
            "matches_count": len(matches),
            "clusters_count": len(clusters),
            "copypasta_count": sum(1 for m in matches if m.duplicate_type == DuplicateType.COPYPASTA),
            "rewording_count": sum(1 for m in matches if m.duplicate_type == DuplicateType.REWORDING),
            "translation_count": sum(1 for m in matches if m.duplicate_type == DuplicateType.TRANSLATION),
            "cross_language_count": sum(1 for m in matches if m.is_cross_language),
            "avg_similarity": np.mean([m.similarity_score for m in matches]) if matches else 0,
            "max_cluster_size": max((c.size for c in clusters), default=0),
            "multilingual_clusters": sum(1 for c in clusters if c.is_multilingual),
        }
        
        # Distribution des langues
        languages = []
        for m in matches:
            languages.extend([m.language_source, m.language_target])
        if languages:
            from collections import Counter
            stats["language_distribution"] = dict(Counter(languages))
        
        return stats


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def detect_copycats(
    contents: List[Dict[str, Any]],
    threshold: float = 0.85,
    min_text_length: int = 20
) -> CIBDetectionResult:
    """
    Fonction de convenance pour détecter les copycats.
    
    Args:
        contents: Liste de contenus avec 'id' et 'text'
        threshold: Seuil de similarité sémantique
        min_text_length: Longueur minimum de texte
        
    Returns:
        CIBDetectionResult
    """
    config = D3ltaConfig(
        threshold_semantic=threshold,
        min_text_length=min_text_length
    )
    analyzer = D3ltaAnalyzer(config=config)
    return analyzer.analyze(contents)


def find_duplicates_in_corpus(
    query: str,
    corpus: List[Dict[str, Any]],
    top_k: int = 10
) -> List[Tuple[str, float]]:
    """
    Trouve les duplicatas d'un texte dans un corpus.
    
    Args:
        query: Texte de requête
        corpus: Corpus de contenus
        top_k: Nombre de résultats
        
    Returns:
        Liste de (content_id, similarity)
    """
    analyzer = D3ltaAnalyzer()
    return analyzer.find_similar(query, corpus, top_k=top_k)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    "D3ltaConfig",
    
    # Enums
    "DuplicateType",
    "CIBIndicator",
    
    # Data structures
    "DuplicateMatch",
    "ContentCluster",
    "CIBDetectionResult",
    
    # Main analyzer
    "D3ltaAnalyzer",
    
    # Convenience functions
    "detect_copycats",
    "find_duplicates_in_corpus",
    
    # Availability flag
    "D3LTA_AVAILABLE",
]
