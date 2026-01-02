"""
Doppelganger Tracker - Network Analyzer
=======================================
Analyzes the propagation network to identify:
- Superspreader nodes
- Community structures
- Coordinated behavior patterns
- Propagation cascades

Usage:
    from analyzers.network_analyzer import NetworkAnalyzer
    
    analyzer = NetworkAnalyzer()
    results = analyzer.run_full_analysis(days_back=30)
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set
from pathlib import Path
from collections import defaultdict

import networkx as nx
from community import community_louvain
from loguru import logger
from sqlalchemy.orm import joinedload

from database import (
    get_session,
    Content,
    Source,
    Propagation,
    NLPAnalysis,
    NetworkNode,
    NetworkEdge,
    SuperspreaderInfo,
    NetworkStats,
    CoordinatedBehaviorEvent,
)
from config.settings import settings


class NetworkAnalyzer:
    """
    Network analysis for content propagation.
    
    Builds and analyzes graphs representing content flow
    between sources to identify influence patterns.
    
    Attributes:
        session: Database session
        content_graph: Graph of content relationships
        source_graph: Graph of source relationships
    """
    
    def __init__(self):
        """Initialize network analyzer."""
        self.session = get_session()
        self.content_graph = nx.DiGraph()
        self.source_graph = nx.DiGraph()
    
    def build_content_graph(
        self,
        days_back: int = 30,
        min_similarity: float = 0.5
    ) -> nx.DiGraph:
        """
        Build graph of content propagation.
        
        Args:
            days_back: Number of days to look back
            min_similarity: Minimum similarity threshold
            
        Returns:
            nx.DiGraph: Content propagation graph
        """
        logger.info(f"Building content graph (last {days_back} days)...")
        
        self.content_graph.clear()
        
        # Get propagation links with eager loading to prevent N+1 queries
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        propagations = (
            self.session.query(Propagation)
            .options(
                joinedload(Propagation.source_content),
                joinedload(Propagation.target_content)
            )
            .filter(Propagation.created_at >= cutoff_date)
            .all()
        )
        
        # Build graph
        for prop in propagations:
            if prop.similarity_score and prop.similarity_score < min_similarity:
                continue
            
            self.content_graph.add_edge(
                str(prop.source_content_id),
                str(prop.target_content_id),
                propagation_type=prop.propagation_type,
                similarity=prop.similarity_score or 0,
                mutation=prop.mutation_detected,
                time_delta=prop.time_delta_seconds or 0
            )
        
        logger.info(
            f"Content graph: {self.content_graph.number_of_nodes()} nodes, "
            f"{self.content_graph.number_of_edges()} edges"
        )
        
        return self.content_graph
    
    def build_source_graph(self, days_back: int = 30) -> nx.DiGraph:
        """
        Build graph of source relationships.
        
        Creates edges between sources based on content propagation,
        with edge weights representing propagation frequency.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            nx.DiGraph: Source relationship graph
        """
        logger.info("Building source graph...")
        
        self.source_graph.clear()
        
        # Get all active sources
        sources = self.session.query(Source).filter(
            Source.is_active == True
        ).all()
        
        # Add nodes with attributes
        for source in sources:
            self.source_graph.add_node(
                str(source.id),
                name=source.name,
                source_type=source.source_type,
                language=source.language or "unknown",
                is_doppelganger=source.is_doppelganger,
                is_amplifier=source.is_amplifier
            )
        
        # Build edges from propagation with eager loading to prevent N+1 queries
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        propagations = (
            self.session.query(Propagation)
            .options(
                joinedload(Propagation.source_content),
                joinedload(Propagation.target_content)
            )
            .filter(Propagation.created_at >= cutoff_date)
            .all()
        )

        # Count propagations between sources
        edge_weights: Dict[tuple, int] = defaultdict(int)

        for prop in propagations:
            # Access pre-loaded relationships (no additional queries)
            source_content = prop.source_content
            target_content = prop.target_content

            if source_content and target_content:
                src_id = source_content.source_id
                tgt_id = target_content.source_id

                if src_id and tgt_id and src_id != tgt_id:
                    edge_weights[(str(src_id), str(tgt_id))] += 1
        
        # Add weighted edges
        for (src, tgt), weight in edge_weights.items():
            self.source_graph.add_edge(src, tgt, weight=weight)
        
        logger.info(
            f"Source graph: {self.source_graph.number_of_nodes()} nodes, "
            f"{self.source_graph.number_of_edges()} edges"
        )
        
        return self.source_graph
    
    def detect_communities(
        self,
        graph: Optional[nx.Graph] = None
    ) -> Dict[str, int]:
        """
        Detect communities using Louvain algorithm.
        
        Args:
            graph: Graph to analyze (defaults to source_graph)
            
        Returns:
            Dict[str, int]: Node ID to community ID mapping
        """
        if graph is None:
            graph = self.source_graph.to_undirected()
        
        if graph.number_of_nodes() < 2:
            return {}
        
        try:
            partition = community_louvain.best_partition(graph)
            num_communities = len(set(partition.values()))
            logger.info(f"Detected {num_communities} communities")
            return partition
        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return {}
    
    def find_superspreaders(
        self,
        graph: Optional[nx.DiGraph] = None,
        top_n: int = 10
    ) -> List[SuperspreaderInfo]:
        """
        Identify superspreader nodes.
        
        Uses multiple centrality metrics to identify
        the most influential nodes in the network.
        
        Args:
            graph: Graph to analyze (defaults to source_graph)
            top_n: Number of top nodes to return
            
        Returns:
            List[SuperspreaderInfo]: Top superspreaders
        """
        if graph is None:
            graph = self.source_graph
        
        if graph.number_of_nodes() == 0:
            return []
        
        # Calculate centrality metrics
        out_degrees = dict(graph.out_degree())
        
        try:
            pagerank = nx.pagerank(graph, max_iter=100)
        except Exception:
            pagerank = {n: 0 for n in graph.nodes()}
        
        try:
            betweenness = nx.betweenness_centrality(graph)
        except Exception:
            betweenness = {n: 0 for n in graph.nodes()}
        
        # Calculate combined scores
        superspreaders = []
        
        for node in graph.nodes():
            attrs = graph.nodes[node]
            
            # Weighted score combining metrics
            score = (
                out_degrees.get(node, 0) * 0.4 +
                pagerank.get(node, 0) * 100 * 0.4 +
                betweenness.get(node, 0) * 10 * 0.2
            )
            
            superspreaders.append(SuperspreaderInfo(
                id=node,
                name=attrs.get("name", node),
                source_type=attrs.get("source_type", "unknown"),
                out_degree=out_degrees.get(node, 0),
                pagerank=pagerank.get(node, 0),
                betweenness=betweenness.get(node, 0),
                score=score,
                is_doppelganger=attrs.get("is_doppelganger", False)
            ))
        
        # Sort by score and return top N
        superspreaders.sort(key=lambda x: x.score, reverse=True)
        return superspreaders[:top_n]
    
    def analyze_propagation_patterns(
        self,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze propagation patterns.
        
        Args:
            days_back: Days to analyze
            
        Returns:
            Dict: Propagation pattern statistics
        """
        logger.info("Analyzing propagation patterns...")

        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        # Use eager loading to prevent N+1 queries
        propagations = (
            self.session.query(Propagation)
            .options(
                joinedload(Propagation.source_content),
                joinedload(Propagation.target_content)
            )
            .filter(Propagation.created_at >= cutoff_date)
            .all()
        )
        
        if not propagations:
            return {"total": 0, "patterns": {}}
        
        # Analyze patterns
        patterns = {
            "total": len(propagations),
            "by_type": defaultdict(int),
            "mutations": 0,
            "avg_time_delta": 0,
            "fast_propagation": 0,  # < 1 hour
            "same_day": 0,          # < 24 hours
        }
        
        total_delta = 0
        counted = 0
        
        for prop in propagations:
            patterns["by_type"][prop.propagation_type] += 1
            
            if prop.mutation_detected:
                patterns["mutations"] += 1
            
            if prop.time_delta_seconds:
                total_delta += prop.time_delta_seconds
                counted += 1
                
                if prop.time_delta_seconds < 3600:
                    patterns["fast_propagation"] += 1
                if prop.time_delta_seconds < 86400:
                    patterns["same_day"] += 1
        
        if counted > 0:
            patterns["avg_time_delta"] = total_delta / counted
        
        patterns["by_type"] = dict(patterns["by_type"])
        
        return patterns
    
    def detect_coordinated_behavior(
        self,
        time_window_seconds: int = 300,
        min_actors: int = 3
    ) -> List[CoordinatedBehaviorEvent]:
        """
        Detect potential coordinated behavior.
        
        Identifies clusters of content posted within tight
        time windows by multiple sources.
        
        Args:
            time_window_seconds: Time window for coordination (default: 5 min)
            min_actors: Minimum number of sources for coordination
            
        Returns:
            List[CoordinatedBehaviorEvent]: Detected events
        """
        logger.info("Detecting coordinated behavior...")

        coordinated = []

        # Get content ordered by time with eager loading to prevent N+1 queries
        contents = (
            self.session.query(Content)
            .options(joinedload(Content.source))
            .filter(Content.published_at.isnot(None))
            .order_by(Content.published_at)
            .all()
        )
        
        if not contents:
            return []
        
        # Sliding window detection
        seen_hours: Set[str] = set()
        
        for i, content in enumerate(contents):
            if not content.published_at:
                continue
            
            window_contents = []
            
            # Find content within time window
            for j in range(i, len(contents)):
                other = contents[j]
                if not other.published_at:
                    continue
                
                delta = (other.published_at - content.published_at).total_seconds()
                
                if delta <= time_window_seconds:
                    window_contents.append(other)
                elif delta > time_window_seconds:
                    break
            
            # Check for coordination
            if len(window_contents) >= min_actors:
                sources = {c.source_id for c in window_contents if c.source_id}
                
                if len(sources) >= min_actors:
                    # Deduplicate by hour
                    hour_key = content.published_at.strftime("%Y-%m-%dT%H")
                    
                    if hour_key not in seen_hours:
                        seen_hours.add(hour_key)
                        
                        coordinated.append(CoordinatedBehaviorEvent(
                            timestamp=content.published_at,
                            content_count=len(window_contents),
                            unique_sources=len(sources),
                            window_seconds=time_window_seconds,
                            content_ids=[str(c.id) for c in window_contents[:10]]
                        ))
        
        logger.info(f"Detected {len(coordinated)} potential coordinated events")
        return coordinated
    
    def get_network_stats(self) -> NetworkStats:
        """
        Calculate network statistics.
        
        Returns:
            NetworkStats: Network statistics summary
        """
        stats = NetworkStats(
            node_count=self.source_graph.number_of_nodes(),
            edge_count=self.source_graph.number_of_edges(),
            density=nx.density(self.source_graph) if self.source_graph.number_of_nodes() > 0 else 0,
            community_count=0,
            avg_degree=0,
            is_connected=False
        )
        
        if self.source_graph.number_of_nodes() > 0:
            # Average degree
            degrees = dict(self.source_graph.degree())
            stats.avg_degree = sum(degrees.values()) / len(degrees)
            
            # Connectivity (for undirected version)
            try:
                undirected = self.source_graph.to_undirected()
                stats.is_connected = nx.is_connected(undirected)
            except Exception:
                pass
        
        return stats
    
    def export_to_gexf(
        self,
        filepath: str,
        graph: Optional[nx.Graph] = None
    ) -> str:
        """
        Export graph to GEXF format for Gephi.
        
        Args:
            filepath: Output file path
            graph: Graph to export (defaults to source_graph)
            
        Returns:
            str: Path to exported file
        """
        if graph is None:
            graph = self.source_graph
        
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        nx.write_gexf(graph, str(output_path))
        logger.info(f"Exported graph to {output_path}")
        
        return str(output_path)
    
    def run_full_analysis(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Run complete network analysis.
        
        Args:
            days_back: Days to analyze
            
        Returns:
            Dict: Complete analysis results
        """
        logger.info("=" * 50)
        logger.info("NETWORK ANALYSIS")
        logger.info("=" * 50)
        
        # Build graphs
        self.build_content_graph(days_back)
        self.build_source_graph(days_back)
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "period_days": days_back,
            "stats": self.get_network_stats().__dict__,
            "superspreaders": [s.__dict__ for s in self.find_superspreaders(top_n=20)],
            "propagation_patterns": self.analyze_propagation_patterns(days_back),
            "coordinated_behavior": [e.__dict__ for e in self.detect_coordinated_behavior()]
        }
        
        # Community detection
        if self.source_graph.number_of_nodes() > 2:
            partition = self.detect_communities()
            results["communities"] = {
                "count": len(set(partition.values())),
                "partition": partition
            }
        
        # Export graph
        if self.source_graph.number_of_nodes() > 0:
            exports_dir = Path(settings.exports_dir) / "graphs"
            exports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            gexf_path = self.export_to_gexf(
                exports_dir / f"source_network_{timestamp}.gexf"
            )
            results["exports"] = {"source_network": gexf_path}
        
        return results
    
    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Entry point for standalone execution."""
    logger.info("=== Doppelganger Tracker - Network Analyzer ===")
    
    analyzer = NetworkAnalyzer()
    
    try:
        results = analyzer.run_full_analysis(days_back=30)
        
        stats = results.get("stats", {})
        logger.info(f"Network stats: {stats}")
        
        superspreaders = results.get("superspreaders", [])
        if superspreaders:
            logger.info(f"Top spreaders: {[s['name'] for s in superspreaders[:5]]}")
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
