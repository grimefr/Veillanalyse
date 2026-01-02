"""
Doppelganger Tracker - Dashboard
================================
Streamlit-based web dashboard for monitoring and analysis.

Usage:
    streamlit run dashboard/app.py --server.port=8501

Features:
    - Real-time statistics overview
    - Content timeline visualization
    - Sentiment analysis charts
    - Network analysis display
    - Propaganda alerts
    - Content search
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import (
    get_session,
    Content,
    Source,
    NLPAnalysis,
    CognitiveMarker,
    Factcheck,
    CollectionRun,
    Narrative,
    DashboardStats,
)


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Doppelganger Tracker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

@st.cache_resource
def get_db_session():
    """
    Get cached database session with connection test.
    
    Returns:
        Session: Database session or None if connection fails
    """
    try:
        session = get_session()
        # Test connection
        session.execute(text("SELECT 1"))
        return session
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def get_stats() -> DashboardStats:
    """
    Fetch overall dashboard statistics.
    
    Returns:
        DashboardStats: Current statistics
    """
    session = get_db_session()
    
    if session is None:
        return DashboardStats()
    
    try:
        return DashboardStats(
            total_content=session.query(Content).count(),
            total_sources=session.query(Source).count(),
            analyzed_content=session.query(Content).filter(
                Content.is_analyzed == True
            ).count(),
            doppelganger_sources=session.query(Source).filter(
                Source.is_doppelganger == True
            ).count(),
            propaganda_detected=session.query(NLPAnalysis).filter(
                NLPAnalysis.is_propaganda == True
            ).count(),
            cognitive_markers=session.query(CognitiveMarker).count(),
            factchecks=session.query(Factcheck).count()
        )
    except Exception as e:
        st.warning(f"Error fetching stats: {e}")
        return DashboardStats()


def get_timeline_data(days: int = 30) -> pd.DataFrame:
    """
    Get content timeline data for visualization.
    
    Args:
        days: Number of days to include
        
    Returns:
        pd.DataFrame: Timeline data
    """
    session = get_db_session()
    
    if session is None:
        return pd.DataFrame()
    
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        contents = session.query(Content).filter(
            Content.published_at >= since,
            Content.published_at.isnot(None)
        ).all()
        
        if not contents:
            return pd.DataFrame()
        
        data = [{
            "date": c.published_at.date(),
            "source_id": c.source_id,
            "language": c.language or "unknown",
            "content_type": c.content_type
        } for c in contents]
        
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def get_sentiment_distribution() -> pd.DataFrame:
    """
    Get sentiment analysis distribution.
    
    Returns:
        pd.DataFrame: Sentiment data
    """
    session = get_db_session()
    
    if session is None:
        return pd.DataFrame()
    
    try:
        analyses = session.query(NLPAnalysis).filter(
            NLPAnalysis.sentiment_label.isnot(None)
        ).all()
        
        if not analyses:
            return pd.DataFrame()
        
        data = [{
            "sentiment": a.sentiment_label,
            "score": a.sentiment_score,
            "is_propaganda": a.is_propaganda or False
        } for a in analyses]
        
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def get_cognitive_markers_data() -> pd.DataFrame:
    """
    Get cognitive markers distribution.
    
    Returns:
        pd.DataFrame: Markers data
    """
    session = get_db_session()
    
    if session is None:
        return pd.DataFrame()
    
    try:
        markers = session.query(CognitiveMarker).all()
        
        if not markers:
            return pd.DataFrame()
        
        data = [{
            "type": m.marker_type,
            "category": m.marker_category,
            "severity": m.severity or "medium",
            "confidence": m.confidence
        } for m in markers]
        
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def get_sources_data() -> pd.DataFrame:
    """
    Get sources summary data.
    
    Returns:
        pd.DataFrame: Sources data
    """
    session = get_db_session()
    
    if session is None:
        return pd.DataFrame()
    
    try:
        sources = session.query(Source).all()
        
        if not sources:
            return pd.DataFrame()
        
        data = []
        for s in sources:
            content_count = session.query(Content).filter(
                Content.source_id == s.id
            ).count()
            
            data.append({
                "name": s.name,
                "type": s.source_type,
                "language": s.language or "unknown",
                "is_doppelganger": "🔴" if s.is_doppelganger else "",
                "is_amplifier": "🟠" if s.is_amplifier else "",
                "content_count": content_count,
                "last_collected": s.last_collected_at
            })
        
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def get_recent_content(limit: int = 20) -> pd.DataFrame:
    """
    Get most recent content items.
    
    Args:
        limit: Maximum items to return
        
    Returns:
        pd.DataFrame: Recent content
    """
    session = get_db_session()
    
    if session is None:
        return pd.DataFrame()
    
    try:
        contents = session.query(Content).order_by(
            Content.collected_at.desc()
        ).limit(limit).all()
        
        if not contents:
            return pd.DataFrame()
        
        data = []
        for c in contents:
            source = session.query(Source).filter(
                Source.id == c.source_id
            ).first()
            
            analysis = session.query(NLPAnalysis).filter(
                NLPAnalysis.content_id == c.id
            ).first()
            
            title = c.title or c.text_content[:80]
            if len(title) > 80:
                title = title[:77] + "..."
            
            data.append({
                "id": str(c.id)[:8],
                "title": title,
                "source": source.name if source else "Unknown",
                "type": c.content_type,
                "language": c.language or "?",
                "sentiment": analysis.sentiment_label if analysis else "N/A",
                "propaganda": "⚠️" if (analysis and analysis.is_propaganda) else "",
                "published": c.published_at.strftime("%Y-%m-%d %H:%M") if c.published_at else "N/A"
            })
        
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def get_language_distribution() -> pd.DataFrame:
    """
    Get content language distribution.
    
    Returns:
        pd.DataFrame: Language distribution
    """
    session = get_db_session()
    
    if session is None:
        return pd.DataFrame()
    
    try:
        contents = session.query(Content).filter(
            Content.language.isnot(None)
        ).all()
        
        if not contents:
            return pd.DataFrame()
        
        lang_counts: Dict[str, int] = {}
        for c in contents:
            lang = c.language or "unknown"
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        
        data = [
            {"language": lang, "count": count}
            for lang, count in lang_counts.items()
        ]
        
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def create_timeline_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create timeline visualization.
    
    Args:
        df: Timeline data
        
    Returns:
        go.Figure: Plotly figure
    """
    if df.empty:
        return go.Figure()
    
    # Group by date
    daily_counts = df.groupby("date").size().reset_index(name="count")
    
    fig = px.area(
        daily_counts,
        x="date",
        y="count",
        title="Content Collection Timeline",
        labels={"date": "Date", "count": "Items Collected"}
    )
    
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Content Count",
        hovermode="x unified"
    )
    
    return fig


def create_sentiment_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create sentiment distribution chart.
    
    Args:
        df: Sentiment data
        
    Returns:
        go.Figure: Plotly figure
    """
    if df.empty:
        return go.Figure()
    
    sentiment_counts = df["sentiment"].value_counts().reset_index()
    sentiment_counts.columns = ["sentiment", "count"]
    
    colors = {
        "positive": "#2ecc71",
        "neutral": "#95a5a6",
        "negative": "#e74c3c"
    }
    
    fig = px.pie(
        sentiment_counts,
        values="count",
        names="sentiment",
        title="Sentiment Distribution",
        color="sentiment",
        color_discrete_map=colors
    )
    
    return fig


def create_markers_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create cognitive markers chart.
    
    Args:
        df: Markers data
        
    Returns:
        go.Figure: Plotly figure
    """
    if df.empty:
        return go.Figure()
    
    marker_counts = df["type"].value_counts().head(10).reset_index()
    marker_counts.columns = ["marker_type", "count"]
    
    fig = px.bar(
        marker_counts,
        x="count",
        y="marker_type",
        orientation="h",
        title="Top Cognitive Markers Detected",
        labels={"marker_type": "Marker Type", "count": "Occurrences"}
    )
    
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    
    return fig


def create_language_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create language distribution chart.
    
    Args:
        df: Language data
        
    Returns:
        go.Figure: Plotly figure
    """
    if df.empty:
        return go.Figure()
    
    fig = px.pie(
        df,
        values="count",
        names="language",
        title="Content by Language"
    )
    
    return fig


# =============================================================================
# PAGE RENDERERS
# =============================================================================

def render_overview():
    """Render the overview/home page."""
    st.header("📊 Dashboard Overview")
    
    # Fetch stats
    stats = get_stats()
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📝 Total Content",
            value=f"{stats.total_content:,}",
            delta=None
        )
    
    with col2:
        st.metric(
            label="📡 Active Sources",
            value=f"{stats.total_sources:,}",
            delta=None
        )
    
    with col3:
        st.metric(
            label="🔍 Analyzed",
            value=f"{stats.analyzed_content:,}",
            delta=None
        )
    
    with col4:
        st.metric(
            label="⚠️ Propaganda",
            value=f"{stats.propaganda_detected:,}",
            delta=None
        )
    
    st.markdown("---")
    
    # Secondary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🔴 Doppelganger Sources",
            value=stats.doppelganger_sources
        )
    
    with col2:
        st.metric(
            label="🎯 Cognitive Markers",
            value=f"{stats.cognitive_markers:,}"
        )
    
    with col3:
        st.metric(
            label="✅ Fact-checks",
            value=stats.factchecks
        )
    
    with col4:
        analysis_rate = (
            (stats.analyzed_content / stats.total_content * 100)
            if stats.total_content > 0 else 0
        )
        st.metric(
            label="📈 Analysis Rate",
            value=f"{analysis_rate:.1f}%"
        )
    
    st.markdown("---")
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        timeline_df = get_timeline_data(30)
        if not timeline_df.empty:
            st.plotly_chart(
                create_timeline_chart(timeline_df),
                use_container_width=True
            )
        else:
            st.info("No timeline data available yet")
    
    with col2:
        sentiment_df = get_sentiment_distribution()
        if not sentiment_df.empty:
            st.plotly_chart(
                create_sentiment_chart(sentiment_df),
                use_container_width=True
            )
        else:
            st.info("No sentiment data available yet")
    
    # Language and markers row
    col1, col2 = st.columns(2)
    
    with col1:
        lang_df = get_language_distribution()
        if not lang_df.empty:
            st.plotly_chart(
                create_language_chart(lang_df),
                use_container_width=True
            )
        else:
            st.info("No language data available")
    
    with col2:
        markers_df = get_cognitive_markers_data()
        if not markers_df.empty:
            st.plotly_chart(
                create_markers_chart(markers_df),
                use_container_width=True
            )
        else:
            st.info("No cognitive markers detected yet")


def render_sources():
    """Render the sources page."""
    st.header("📡 Sources")
    
    sources_df = get_sources_data()
    
    if not sources_df.empty:
        # Summary stats
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Sources", len(sources_df))
        with col2:
            doppelganger_count = len(sources_df[sources_df["is_doppelganger"] == "🔴"])
            st.metric("Doppelganger", doppelganger_count)
        with col3:
            amplifier_count = len(sources_df[sources_df["is_amplifier"] == "🟠"])
            st.metric("Amplifiers", amplifier_count)
        
        st.markdown("---")
        
        # Sources table
        st.subheader("Source Registry")
        st.dataframe(
            sources_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Type distribution
        type_counts = sources_df["type"].value_counts().reset_index()
        type_counts.columns = ["type", "count"]
        
        fig = px.bar(
            type_counts,
            x="type",
            y="count",
            title="Sources by Type"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No sources registered yet")


def render_content():
    """Render the content analysis page."""
    st.header("📄 Content Analysis")
    
    # Recent content
    st.subheader("Recent Content")
    
    recent_df = get_recent_content(30)
    
    if not recent_df.empty:
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        st.info("No content collected yet")
    
    st.markdown("---")
    
    # Search
    st.subheader("🔍 Search Content")
    search_query = st.text_input("Enter search terms")
    
    if search_query:
        session = get_db_session()
        
        if session:
            try:
                results = session.query(Content).filter(
                    Content.text_content.ilike(f"%{search_query}%")
                ).limit(20).all()
                
                if results:
                    st.success(f"Found {len(results)} results")
                    
                    for r in results:
                        with st.expander(
                            f"📄 {r.title or r.text_content[:50]}..."
                        ):
                            st.write(r.text_content[:500])
                            st.caption(
                                f"Type: {r.content_type} | "
                                f"Language: {r.language} | "
                                f"Published: {r.published_at}"
                            )
                else:
                    st.warning("No results found")
            except Exception as e:
                st.error(f"Search error: {e}")


def render_network():
    """Render the network analysis page."""
    st.header("🕸️ Network Analysis")
    
    st.info("""
    **Propagation Network Analysis**
    
    This section displays:
    - Source relationship graphs
    - Detected communities
    - Superspreader identification
    - Coordinated behavior patterns
    
    Export GEXF files from `/exports/graphs/` for Gephi visualization.
    """)
    
    # Check for exported graphs
    exports_dir = Path("exports/graphs")
    
    if exports_dir.exists():
        gexf_files = list(exports_dir.glob("*.gexf"))
        
        if gexf_files:
            st.success(f"📁 {len(gexf_files)} graph file(s) available for download")
            
            for f in gexf_files[-5:]:  # Show last 5
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f.name)
                with col2:
                    with open(f, "rb") as file:
                        st.download_button(
                            "📥 Download",
                            file.read(),
                            f.name,
                            "application/gexf+xml",
                            key=f.name
                        )
        else:
            st.info("No graph exports available. Run network analysis first.")
    else:
        st.info("Export directory not found. Run network analysis to generate graphs.")


def render_alerts():
    """Render the alerts page."""
    st.header("🚨 Alerts & Detections")
    
    session = get_db_session()
    
    if session is None:
        st.error("Database not available")
        return
    
    try:
        # Propaganda alerts
        st.subheader("⚠️ Propaganda Content Detected")
        
        propaganda = session.query(NLPAnalysis).filter(
            NLPAnalysis.is_propaganda == True,
            NLPAnalysis.propaganda_confidence >= 0.7
        ).order_by(NLPAnalysis.analyzed_at.desc()).limit(10).all()
        
        if propaganda:
            for p in propaganda:
                content = session.query(Content).filter(
                    Content.id == p.content_id
                ).first()
                
                if content:
                    with st.expander(
                        f"🚨 Confidence: {p.propaganda_confidence:.0%} | "
                        f"{content.title or 'Untitled'}"
                    ):
                        st.write(content.text_content[:500])
                        st.write(f"**Techniques:** {', '.join(p.propaganda_techniques or [])}")
                        st.write(f"**Sentiment:** {p.sentiment_label} ({p.sentiment_score:.2f})")
        else:
            st.success("✅ No high-confidence propaganda detected recently")
        
        st.markdown("---")
        
        # High-severity markers
        st.subheader("🎯 High-Severity Cognitive Markers")
        
        high_markers = session.query(CognitiveMarker).filter(
            CognitiveMarker.severity == "high",
            CognitiveMarker.confidence >= 0.8
        ).limit(10).all()
        
        if high_markers:
            for m in high_markers:
                st.warning(
                    f"**{m.marker_type}** ({m.marker_category}) - "
                    f"Confidence: {m.confidence:.0%}"
                )
        else:
            st.success("✅ No high-severity markers detected")
        
    except Exception as e:
        st.error(f"Error loading alerts: {e}")


def render_about():
    """Render the about page."""
    st.header("ℹ️ About Doppelganger Tracker")
    
    st.markdown("""
    ## 🎯 Purpose
    
    Doppelganger Tracker is an **academic research tool** designed to study
    and analyze the propagation of disinformation, specifically focusing on
    the "Operation Doppelganger" influence campaign.
    
    ## 📚 Features
    
    - **Content Collection**: Automated collection from Telegram channels and RSS feeds
    - **NLP Analysis**: Sentiment analysis, entity extraction, language detection
    - **Propaganda Detection**: Identification of manipulation techniques
    - **Network Analysis**: Mapping of content propagation patterns
    - **Cognitive Warfare Framework**: DISARM-based marker detection
    
    ## ⚠️ Ethical Notice
    
    This tool is intended for **academic research purposes only**.
    All data collection follows ethical guidelines:
    
    - Public sources only
    - No personal data collection
    - GDPR compliance
    - Research purpose only
    
    ## 🔗 Resources
    
    - [DISARM Framework](https://disarmframework.org)
    - [EU DisinfoLab](https://www.disinfo.eu/)
    - [EU vs Disinfo](https://euvsdisinfo.eu/)
    
    ---
    
    **Version:** 1.0.0  
    **Last Updated:** 2025
    """)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """Main dashboard application."""
    
    # Sidebar navigation
    st.sidebar.title("🎯 Doppelganger Tracker")
    st.sidebar.markdown("---")
    
    # Navigation menu
    page = st.sidebar.radio(
        "Navigation",
        [
            "📊 Overview",
            "📡 Sources",
            "📄 Content",
            "🕸️ Network",
            "🚨 Alerts",
            "ℹ️ About"
        ]
    )
    
    st.sidebar.markdown("---")
    
    # Last update info
    st.sidebar.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Render selected page
    if page == "📊 Overview":
        render_overview()
    elif page == "📡 Sources":
        render_sources()
    elif page == "📄 Content":
        render_content()
    elif page == "🕸️ Network":
        render_network()
    elif page == "🚨 Alerts":
        render_alerts()
    elif page == "ℹ️ About":
        render_about()


if __name__ == "__main__":
    main()
