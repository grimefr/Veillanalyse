"""
Doppelganger Tracker - BERTopic Integration Module
===================================================
Identification et suivi des topics/thématiques dans les contenus
utilisant BERTopic pour le topic modeling neuronal.

BERTopic: https://github.com/MaartenGr/BERTopic
Paper: https://arxiv.org/abs/2203.05794

BERTopic combine:
- Embeddings (Sentence-BERT)
- Réduction dimensionnelle (UMAP)
- Clustering (HDBSCAN)
- Représentation des topics (c-TF-IDF)

Requirements:
    pip install bertopic[all]
    # ou minimal:
    pip install bertopic umap-learn hdbscan
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
from collections import Counter
from pathlib import Path
import json

import pandas as pd
import numpy as np
from loguru import logger

# =============================================================================
# IMPORTS CONDITIONNELS
# =============================================================================

try:
    from bertopic import BERTopic
    from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance
    BERTOPIC_AVAILABLE = True
    logger.info("BERTopic library loaded successfully")
except ImportError:
    BERTOPIC_AVAILABLE = False
    logger.warning(
        "BERTopic not installed. Install with: pip install bertopic[all]"
    )

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from umap import UMAP
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False

try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import CountVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class BERTopicConfig:
    """
    Configuration pour BERTopic.
    
    Attributes:
        embedding_model: Modèle d'embedding (sentence-transformers)
        language: Langue principale pour le vectorizer
        min_topic_size: Taille minimum d'un topic
        nr_topics: Nombre de topics (None = auto, "auto" = réduction auto)
        top_n_words: Nombre de mots par topic
        n_gram_range: Range des n-grams pour c-TF-IDF
        calculate_probabilities: Calculer les probabilités de topic
        diversity: Diversité des mots du topic (0-1)
        seed_topic_list: Liste de topics seeds pour guided topic modeling
    """
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    language: str = "multilingual"
    min_topic_size: int = 10
    nr_topics: Optional[Union[int, str]] = None
    top_n_words: int = 10
    n_gram_range: Tuple[int, int] = (1, 2)
    calculate_probabilities: bool = False
    diversity: float = 0.3
    seed_topic_list: Optional[List[List[str]]] = None
    
    # UMAP parameters
    umap_n_neighbors: int = 15
    umap_n_components: int = 5
    umap_min_dist: float = 0.0
    umap_metric: str = "cosine"
    
    # HDBSCAN parameters
    hdbscan_min_cluster_size: int = 10
    hdbscan_min_samples: int = 5
    hdbscan_metric: str = "euclidean"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "embedding_model": self.embedding_model,
            "language": self.language,
            "min_topic_size": self.min_topic_size,
            "nr_topics": self.nr_topics,
            "top_n_words": self.top_n_words,
            "n_gram_range": self.n_gram_range,
            "diversity": self.diversity
        }


@dataclass
class Topic:
    """
    Représentation d'un topic détecté.
    
    Attributes:
        topic_id: Identifiant du topic (-1 = outliers)
        name: Nom généré du topic
        keywords: Mots-clés représentatifs avec scores
        size: Nombre de documents dans le topic
        representative_docs: Documents représentatifs
        coherence_score: Score de cohérence (si calculé)
    """
    topic_id: int
    name: str
    keywords: List[Tuple[str, float]]  # [(word, score), ...]
    size: int = 0
    representative_docs: List[str] = field(default_factory=list)
    coherence_score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_outlier(self) -> bool:
        """Vérifie si c'est le topic des outliers."""
        return self.topic_id == -1
    
    @property
    def top_keywords(self) -> List[str]:
        """Retourne les top mots-clés."""
        return [kw for kw, _ in self.keywords[:5]]
    
    @property
    def label(self) -> str:
        """Label court du topic."""
        if self.is_outlier:
            return "Outliers"
        return f"Topic {self.topic_id}: {', '.join(self.top_keywords[:3])}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "keywords": self.keywords,
            "size": self.size,
            "representative_docs": self.representative_docs[:3],
            "is_outlier": self.is_outlier,
            "label": self.label
        }


@dataclass
class DocumentTopicAssignment:
    """
    Assignation d'un document à un topic.
    
    Attributes:
        doc_id: ID du document
        topic_id: ID du topic assigné
        probability: Probabilité d'appartenance
        text_preview: Aperçu du texte
    """
    doc_id: str
    topic_id: int
    probability: float = 1.0
    text_preview: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "topic_id": self.topic_id,
            "probability": self.probability
        }


@dataclass
class TopicEvolution:
    """
    Évolution d'un topic dans le temps.
    
    Attributes:
        topic_id: ID du topic
        timestamps: Liste des timestamps
        frequencies: Fréquences correspondantes
        trend: Tendance (rising, falling, stable)
    """
    topic_id: int
    timestamps: List[datetime] = field(default_factory=list)
    frequencies: List[int] = field(default_factory=list)
    trend: str = "stable"  # rising, falling, stable
    
    @property
    def total_count(self) -> int:
        """Total des occurrences."""
        return sum(self.frequencies)
    
    def compute_trend(self, window: int = 3) -> str:
        """Calcule la tendance sur les dernières périodes."""
        if len(self.frequencies) < window * 2:
            return "stable"
        
        recent = np.mean(self.frequencies[-window:])
        previous = np.mean(self.frequencies[-window*2:-window])
        
        if recent > previous * 1.2:
            return "rising"
        elif recent < previous * 0.8:
            return "falling"
        return "stable"


@dataclass
class TopicModelResult:
    """
    Résultat complet du topic modeling.
    
    Attributes:
        topics: Liste des topics détectés
        assignments: Assignations document-topic
        topic_evolution: Évolution temporelle (si timestamps fournis)
        embeddings: Embeddings des documents (optionnel)
        config: Configuration utilisée
        statistics: Statistiques du modèle
    """
    topics: List[Topic] = field(default_factory=list)
    assignments: List[DocumentTopicAssignment] = field(default_factory=list)
    topic_evolution: Dict[int, TopicEvolution] = field(default_factory=dict)
    embeddings: Optional[np.ndarray] = None
    config: Optional[BERTopicConfig] = None
    statistics: Dict[str, Any] = field(default_factory=dict)
    model_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_seconds: float = 0.0
    
    @property
    def num_topics(self) -> int:
        """Nombre de topics (hors outliers)."""
        return len([t for t in self.topics if not t.is_outlier])
    
    @property
    def outlier_count(self) -> int:
        """Nombre de documents outliers."""
        outlier_topic = next((t for t in self.topics if t.is_outlier), None)
        return outlier_topic.size if outlier_topic else 0
    
    def get_topic(self, topic_id: int) -> Optional[Topic]:
        """Récupère un topic par ID."""
        return next((t for t in self.topics if t.topic_id == topic_id), None)
    
    def get_documents_for_topic(self, topic_id: int) -> List[DocumentTopicAssignment]:
        """Récupère les documents d'un topic."""
        return [a for a in self.assignments if a.topic_id == topic_id]
    
    def get_rising_topics(self) -> List[Topic]:
        """Récupère les topics en hausse."""
        rising_ids = [
            tid for tid, evo in self.topic_evolution.items() 
            if evo.trend == "rising"
        ]
        return [t for t in self.topics if t.topic_id in rising_ids]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "num_topics": self.num_topics,
            "outlier_count": self.outlier_count,
            "topics": [t.to_dict() for t in self.topics],
            "statistics": self.statistics,
            "created_at": self.created_at.isoformat(),
            "processing_time_seconds": self.processing_time_seconds
        }


# =============================================================================
# BERTOPIC ANALYZER - Main Interface
# =============================================================================

class BERTopicAnalyzer:
    """
    Analyseur de topics utilisant BERTopic.
    
    Cette classe encapsule BERTopic pour:
    - Extraire automatiquement les topics d'un corpus
    - Suivre l'évolution des topics dans le temps
    - Identifier les thématiques émergentes
    - Supporter le topic modeling guidé (avec seeds)
    
    Example:
        ```python
        analyzer = BERTopicAnalyzer(config=BERTopicConfig(
            min_topic_size=5,
            language="french"
        ))
        
        contents = [
            {"id": "1", "text": "L'Ukraine résiste face à l'invasion"},
            {"id": "2", "text": "Les sanctions économiques contre la Russie"},
            {"id": "3", "text": "La crise énergétique en Europe"},
        ]
        
        result = analyzer.fit_transform(contents)
        print(f"Found {result.num_topics} topics")
        
        for topic in result.topics:
            print(f"{topic.label}: {topic.size} documents")
        ```
    
    Attributes:
        config: Configuration BERTopic
        model: Instance BERTopic
        embedding_model: Modèle d'embedding
    """
    
    def __init__(
        self,
        config: Optional[BERTopicConfig] = None,
        load_from: Optional[str] = None
    ):
        """
        Initialise l'analyseur BERTopic.
        
        Args:
            config: Configuration BERTopic
            load_from: Chemin pour charger un modèle existant
        """
        self.config = config or BERTopicConfig()
        self.model: Optional[BERTopic] = None
        self._embedding_model = None
        self._embeddings_cache: Dict[str, np.ndarray] = {}
        
        if not BERTOPIC_AVAILABLE:
            logger.error("BERTopic not available. Install with: pip install bertopic[all]")
            return
        
        if load_from:
            self.load(load_from)
        else:
            self._initialize_model()
    
    @property
    def is_available(self) -> bool:
        """Vérifie si BERTopic est disponible."""
        return BERTOPIC_AVAILABLE
    
    @property
    def is_fitted(self) -> bool:
        """Vérifie si le modèle est entraîné."""
        return self.model is not None and hasattr(self.model, 'topics_')
    
    def _initialize_model(self) -> None:
        """Initialise le modèle BERTopic."""
        if not self.is_available:
            return
        
        logger.info("Initializing BERTopic model...")
        
        # Embedding model
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self._embedding_model = SentenceTransformer(self.config.embedding_model)
        else:
            self._embedding_model = self.config.embedding_model
        
        # UMAP
        umap_model = None
        if UMAP_AVAILABLE:
            umap_model = UMAP(
                n_neighbors=self.config.umap_n_neighbors,
                n_components=self.config.umap_n_components,
                min_dist=self.config.umap_min_dist,
                metric=self.config.umap_metric,
                random_state=42
            )
        
        # HDBSCAN
        hdbscan_model = None
        if HDBSCAN_AVAILABLE:
            hdbscan_model = HDBSCAN(
                min_cluster_size=self.config.hdbscan_min_cluster_size,
                min_samples=self.config.hdbscan_min_samples,
                metric=self.config.hdbscan_metric,
                prediction_data=True
            )
        
        # Vectorizer pour c-TF-IDF
        vectorizer_model = None
        if SKLEARN_AVAILABLE:
            # Stopwords multilingues
            stop_words = self._get_stopwords(self.config.language)
            vectorizer_model = CountVectorizer(
                ngram_range=self.config.n_gram_range,
                stop_words=stop_words,
                min_df=2
            )
        
        # Representation models
        representation_model = None
        try:
            representation_model = [
                KeyBERTInspired(),
                MaximalMarginalRelevance(diversity=self.config.diversity)
            ]
        except Exception:
            pass
        
        # Créer le modèle BERTopic
        self.model = BERTopic(
            embedding_model=self._embedding_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            representation_model=representation_model,
            min_topic_size=self.config.min_topic_size,
            nr_topics=self.config.nr_topics,
            top_n_words=self.config.top_n_words,
            calculate_probabilities=self.config.calculate_probabilities,
            verbose=False
        )
        
        logger.info("BERTopic model initialized")
    
    def _get_stopwords(self, language: str) -> Optional[List[str]]:
        """Récupère les stopwords pour une langue."""
        # Stopwords de base multilingues
        stopwords = {
            "french": ["le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "à", "au", "aux", 
                      "ce", "cette", "ces", "qui", "que", "quoi", "dont", "où", "pour", "par", "sur",
                      "avec", "sans", "sous", "dans", "est", "sont", "a", "ont", "être", "avoir",
                      "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "se", "ne", "pas"],
            "english": ["the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                       "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
                       "may", "might", "must", "shall", "can", "need", "to", "of", "in", "for",
                       "on", "with", "at", "by", "from", "as", "into", "through", "during",
                       "before", "after", "above", "below", "between", "under", "again", "further",
                       "then", "once", "here", "there", "when", "where", "why", "how", "all", "each",
                       "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
                       "own", "same", "so", "than", "too", "very", "just", "and", "but", "if", "or"],
            "russian": ["и", "в", "не", "на", "с", "что", "а", "как", "это", "по", "но", "к",
                       "из", "у", "о", "за", "от", "же", "для", "до", "или", "так", "все",
                       "он", "она", "они", "мы", "вы", "его", "её", "их", "был", "была", "были",
                       "быть", "есть", "будет", "этот", "эта", "эти", "тот", "та", "те"]
        }
        
        if language == "multilingual":
            all_stopwords = []
            for sw in stopwords.values():
                all_stopwords.extend(sw)
            return list(set(all_stopwords))
        
        return stopwords.get(language)
    
    def fit_transform(
        self,
        contents: List[Dict[str, Any]],
        timestamps: Optional[List[datetime]] = None,
        compute_evolution: bool = True
    ) -> TopicModelResult:
        """
        Entraîne le modèle et assigne les topics.
        
        Args:
            contents: Liste de contenus avec 'id' et 'text'
            timestamps: Timestamps pour l'évolution temporelle
            compute_evolution: Calculer l'évolution des topics
            
        Returns:
            TopicModelResult avec topics et assignations
        """
        import time
        start_time = time.time()
        
        if not self.is_available or self.model is None:
            logger.error("BERTopic not available")
            return TopicModelResult(config=self.config)
        
        # Extraire les textes
        texts = [c.get("text", "") for c in contents]
        doc_ids = [str(c.get("id", i)) for i, c in enumerate(contents)]
        
        # Filtrer les textes vides
        valid_indices = [i for i, t in enumerate(texts) if len(t.strip()) > 10]
        texts = [texts[i] for i in valid_indices]
        doc_ids = [doc_ids[i] for i in valid_indices]
        
        if len(texts) < self.config.min_topic_size:
            logger.warning(f"Not enough documents ({len(texts)}) for topic modeling")
            return TopicModelResult(
                config=self.config,
                statistics={"error": "Not enough documents"}
            )
        
        logger.info(f"Fitting BERTopic on {len(texts)} documents...")
        
        # Calcul des embeddings (pour réutilisation)
        embeddings = None
        if isinstance(self._embedding_model, SentenceTransformer):
            embeddings = self._embedding_model.encode(texts, show_progress_bar=False)
        
        # Fit transform
        try:
            if self.config.seed_topic_list:
                topics, probs = self.model.fit_transform(
                    texts,
                    embeddings=embeddings,
                    y=self._create_seed_labels(texts, self.config.seed_topic_list)
                )
            else:
                topics, probs = self.model.fit_transform(texts, embeddings=embeddings)
        except Exception as e:
            logger.error(f"BERTopic fit_transform error: {e}")
            return TopicModelResult(config=self.config, statistics={"error": str(e)})
        
        # Convertir les résultats
        result_topics = self._extract_topics()
        assignments = self._create_assignments(doc_ids, texts, topics, probs)
        
        # Évolution temporelle
        topic_evolution = {}
        if compute_evolution and timestamps:
            valid_timestamps = [timestamps[i] for i in valid_indices]
            topic_evolution = self._compute_topic_evolution(topics, valid_timestamps)
        
        # Statistiques
        statistics = self._compute_statistics(topics, result_topics)
        
        processing_time = time.time() - start_time
        
        result = TopicModelResult(
            topics=result_topics,
            assignments=assignments,
            topic_evolution=topic_evolution,
            embeddings=embeddings,
            config=self.config,
            statistics=statistics,
            processing_time_seconds=processing_time
        )
        
        logger.info(
            f"BERTopic completed in {processing_time:.2f}s: "
            f"{result.num_topics} topics, {result.outlier_count} outliers"
        )
        
        return result
    
    def transform(
        self,
        contents: List[Dict[str, Any]]
    ) -> List[DocumentTopicAssignment]:
        """
        Assigne des topics à de nouveaux documents (modèle déjà entraîné).
        
        Args:
            contents: Nouveaux contenus à classifier
            
        Returns:
            Liste d'assignations
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit_transform first.")
        
        texts = [c.get("text", "") for c in contents]
        doc_ids = [str(c.get("id", i)) for i, c in enumerate(contents)]
        
        topics, probs = self.model.transform(texts)
        
        return self._create_assignments(doc_ids, texts, topics, probs)
    
    def get_topic_info(self) -> pd.DataFrame:
        """Récupère les informations sur tous les topics."""
        if not self.is_fitted:
            return pd.DataFrame()
        return self.model.get_topic_info()
    
    def get_topic(self, topic_id: int) -> List[Tuple[str, float]]:
        """Récupère les mots-clés d'un topic."""
        if not self.is_fitted:
            return []
        return self.model.get_topic(topic_id)
    
    def find_topics(
        self,
        query: str,
        top_n: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Trouve les topics les plus similaires à une requête.
        
        Args:
            query: Texte de requête
            top_n: Nombre de topics à retourner
            
        Returns:
            Liste de (topic_id, similarity)
        """
        if not self.is_fitted:
            return []
        
        similar_topics, similarity = self.model.find_topics(query, top_n=top_n)
        return list(zip(similar_topics, similarity))
    
    def reduce_topics(self, nr_topics: int) -> None:
        """
        Réduit le nombre de topics par fusion.
        
        Args:
            nr_topics: Nombre de topics cible
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted.")
        
        self.model.reduce_topics(self.model.original_documents_, nr_topics=nr_topics)
        logger.info(f"Topics reduced to {nr_topics}")
    
    def merge_topics(self, topics_to_merge: List[List[int]]) -> None:
        """
        Fusionne des topics spécifiques.
        
        Args:
            topics_to_merge: Liste de listes de topic IDs à fusionner
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted.")
        
        for topic_group in topics_to_merge:
            if len(topic_group) >= 2:
                self.model.merge_topics(self.model.original_documents_, topic_group)
    
    def visualize_topics(self) -> Any:
        """Génère une visualisation des topics."""
        if not self.is_fitted:
            return None
        return self.model.visualize_topics()
    
    def visualize_hierarchy(self) -> Any:
        """Génère une visualisation hiérarchique."""
        if not self.is_fitted:
            return None
        return self.model.visualize_hierarchy()
    
    def visualize_barchart(self, top_n_topics: int = 10) -> Any:
        """Génère un barchart des topics."""
        if not self.is_fitted:
            return None
        return self.model.visualize_barchart(top_n_topics=top_n_topics)
    
    def visualize_over_time(
        self,
        timestamps: List[datetime],
        nr_bins: int = 20
    ) -> Any:
        """Visualise l'évolution des topics dans le temps."""
        if not self.is_fitted:
            return None
        
        topics_over_time = self.model.topics_over_time(
            self.model.original_documents_,
            timestamps,
            nr_bins=nr_bins
        )
        return self.model.visualize_topics_over_time(topics_over_time)
    
    def save(self, path: str) -> str:
        """
        Sauvegarde le modèle.
        
        Args:
            path: Chemin de sauvegarde
            
        Returns:
            Chemin du modèle sauvegardé
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted.")
        
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.model.save(str(save_path))
        logger.info(f"BERTopic model saved to {save_path}")
        
        return str(save_path)
    
    def load(self, path: str) -> None:
        """
        Charge un modèle sauvegardé.
        
        Args:
            path: Chemin du modèle
        """
        if not self.is_available:
            raise ValueError("BERTopic not available")
        
        self.model = BERTopic.load(path)
        logger.info(f"BERTopic model loaded from {path}")
    
    def _extract_topics(self) -> List[Topic]:
        """Extrait les topics du modèle."""
        topics = []
        
        topic_info = self.model.get_topic_info()
        
        for _, row in topic_info.iterrows():
            topic_id = row["Topic"]
            
            # Récupérer les mots-clés
            keywords = self.model.get_topic(topic_id)
            if keywords is None:
                keywords = []
            
            # Récupérer les documents représentatifs
            rep_docs = []
            try:
                rep_docs = self.model.get_representative_docs(topic_id)
                if rep_docs:
                    rep_docs = [doc[:200] for doc in rep_docs[:3]]
            except Exception:
                pass
            
            topic = Topic(
                topic_id=topic_id,
                name=row.get("Name", f"Topic_{topic_id}"),
                keywords=keywords,
                size=int(row.get("Count", 0)),
                representative_docs=rep_docs
            )
            topics.append(topic)
        
        return topics
    
    def _create_assignments(
        self,
        doc_ids: List[str],
        texts: List[str],
        topics: List[int],
        probs: Optional[np.ndarray]
    ) -> List[DocumentTopicAssignment]:
        """Crée les assignations document-topic."""
        assignments = []
        
        for i, (doc_id, text, topic_id) in enumerate(zip(doc_ids, texts, topics)):
            prob = 1.0
            if probs is not None and len(probs) > i:
                if isinstance(probs[i], np.ndarray):
                    prob = float(np.max(probs[i]))
                else:
                    prob = float(probs[i]) if probs[i] is not None else 1.0
            
            assignment = DocumentTopicAssignment(
                doc_id=doc_id,
                topic_id=int(topic_id),
                probability=prob,
                text_preview=text[:100]
            )
            assignments.append(assignment)
        
        return assignments
    
    def _compute_topic_evolution(
        self,
        topics: List[int],
        timestamps: List[datetime]
    ) -> Dict[int, TopicEvolution]:
        """Calcule l'évolution des topics dans le temps."""
        evolution = {}
        
        # Grouper par période (jour)
        topic_time_counts: Dict[int, Dict[str, int]] = {}
        
        for topic_id, ts in zip(topics, timestamps):
            if topic_id == -1:
                continue
            
            day_key = ts.strftime("%Y-%m-%d")
            
            if topic_id not in topic_time_counts:
                topic_time_counts[topic_id] = {}
            
            if day_key not in topic_time_counts[topic_id]:
                topic_time_counts[topic_id][day_key] = 0
            
            topic_time_counts[topic_id][day_key] += 1
        
        # Convertir en TopicEvolution
        for topic_id, day_counts in topic_time_counts.items():
            sorted_days = sorted(day_counts.keys())
            
            evo = TopicEvolution(
                topic_id=topic_id,
                timestamps=[datetime.strptime(d, "%Y-%m-%d") for d in sorted_days],
                frequencies=[day_counts[d] for d in sorted_days]
            )
            evo.trend = evo.compute_trend()
            
            evolution[topic_id] = evo
        
        return evolution
    
    def _create_seed_labels(
        self,
        texts: List[str],
        seed_topics: List[List[str]]
    ) -> List[int]:
        """Crée des labels pour le guided topic modeling."""
        labels = [-1] * len(texts)
        
        for i, text in enumerate(texts):
            text_lower = text.lower()
            for topic_idx, keywords in enumerate(seed_topics):
                if any(kw.lower() in text_lower for kw in keywords):
                    labels[i] = topic_idx
                    break
        
        return labels
    
    def _compute_statistics(
        self,
        topics: List[int],
        result_topics: List[Topic]
    ) -> Dict[str, Any]:
        """Calcule les statistiques du modèle."""
        topic_counts = Counter(topics)
        
        stats = {
            "total_documents": len(topics),
            "num_topics": len([t for t in result_topics if not t.is_outlier]),
            "outlier_count": topic_counts.get(-1, 0),
            "outlier_percentage": topic_counts.get(-1, 0) / len(topics) * 100 if topics else 0,
            "avg_topic_size": np.mean([t.size for t in result_topics if not t.is_outlier]) if result_topics else 0,
            "max_topic_size": max((t.size for t in result_topics if not t.is_outlier), default=0),
            "min_topic_size": min((t.size for t in result_topics if not t.is_outlier), default=0),
            "topic_distribution": dict(topic_counts)
        }
        
        return stats


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def extract_topics(
    contents: List[Dict[str, Any]],
    min_topic_size: int = 10,
    language: str = "multilingual"
) -> TopicModelResult:
    """
    Fonction de convenance pour extraire les topics.
    
    Args:
        contents: Liste de contenus avec 'id' et 'text'
        min_topic_size: Taille minimum d'un topic
        language: Langue des contenus
        
    Returns:
        TopicModelResult
    """
    config = BERTopicConfig(
        min_topic_size=min_topic_size,
        language=language
    )
    analyzer = BERTopicAnalyzer(config=config)
    return analyzer.fit_transform(contents)


def find_similar_topics(
    query: str,
    model_path: str,
    top_n: int = 5
) -> List[Tuple[int, float]]:
    """
    Trouve les topics similaires à une requête.
    
    Args:
        query: Texte de requête
        model_path: Chemin du modèle BERTopic
        top_n: Nombre de résultats
        
    Returns:
        Liste de (topic_id, similarity)
    """
    analyzer = BERTopicAnalyzer(load_from=model_path)
    return analyzer.find_topics(query, top_n=top_n)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    "BERTopicConfig",
    
    # Data structures
    "Topic",
    "DocumentTopicAssignment",
    "TopicEvolution",
    "TopicModelResult",
    
    # Main analyzer
    "BERTopicAnalyzer",
    
    # Convenience functions
    "extract_topics",
    "find_similar_topics",
    
    # Availability flag
    "BERTOPIC_AVAILABLE",
]
