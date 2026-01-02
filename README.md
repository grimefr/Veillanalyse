<<<<<<< HEAD
# 🎯 Doppelganger Tracker

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Academic Research Tool for Disinformation Analysis**

A comprehensive toolkit for tracking and analyzing the "Operation Doppelganger" disinformation campaign and similar influence operations. Built for academic research in the field of Social Engineering & Cognitive Warfare.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Development](#-development)
- [Testing](#-testing)
- [Ethical Guidelines](#-ethical-guidelines)
- [License](#-license)

---

## 🎯 Overview

Doppelganger Tracker is designed to:

1. **Collect** content from public sources (Telegram channels, RSS feeds, fact-checkers)
2. **Analyze** content using NLP (sentiment, entities, language detection)
3. **Detect** propaganda techniques and cognitive warfare markers
4. **Map** the propagation network and identify superspreaders
5. **Visualize** data through an interactive dashboard

### What is Operation Doppelganger?

Operation Doppelganger is a Russian disinformation campaign that uses typosquatted domains (e.g., `lemonde.ltd` instead of `lemonde.fr`) to impersonate legitimate news outlets and spread pro-Kremlin narratives. This tool helps researchers track and analyze such campaigns.

---

## ✨ Features

### Content Collection
- 📱 **Telegram Collector**: Monitor public Telegram channels using Telethon API
- 📰 **Media Collector**: Parse RSS/Atom feeds from news outlets and fact-checkers
- 🔄 **Deduplication**: Content hashing prevents duplicate entries
- ⏰ **Scheduling**: Automated periodic collection

### NLP Analysis
- 🌐 **Language Detection**: Automatic detection for 50+ languages
- 💬 **Sentiment Analysis**: Lexicon-based multilingual sentiment scoring
- 👤 **Entity Extraction**: Named entity recognition using spaCy
- 🔑 **Keyword Extraction**: Important term identification
- 🎭 **Propaganda Detection**: Manipulation technique identification

### Network Analysis
- 🕸️ **Graph Construction**: Build content and source relationship graphs
- 👥 **Community Detection**: Louvain algorithm for community identification
- ⭐ **Superspreader Detection**: Centrality-based influence analysis
- 🤝 **Coordinated Behavior**: Temporal pattern detection
- 📤 **GEXF Export**: Compatible with Gephi for visualization

### Cognitive Warfare Framework
- 🎯 **DISARM Integration**: Framework-based marker detection
- 📊 **Severity Scoring**: Risk level assessment
- 📈 **Narrative Tracking**: Theme and storyline monitoring

### Dashboard
- 📊 **Real-time Statistics**: Content, sources, analysis metrics
- 📈 **Timeline Visualization**: Content flow over time
- 🎨 **Interactive Charts**: Plotly-powered visualizations
- 🔍 **Content Search**: Full-text search capability
- 🚨 **Alert System**: Propaganda and marker notifications

---

## 🏗 Architecture

```
doppelganger-tracker/
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container image definition
├── docker-compose.yml     # Multi-service orchestration
│
├── config/                # Configuration files
│   ├── settings.py        # Pydantic settings management
│   ├── sources.yaml       # Source definitions
│   ├── keywords.yaml      # Narrative keywords
│   └── cognitive_warfare.yaml  # DISARM framework config
│
├── database/              # Data layer
│   ├── models.py          # SQLAlchemy ORM models
│   ├── dto.py             # Data transfer objects
│   └── schema.sql         # PostgreSQL schema
│
├── collectors/            # Data collection
│   ├── base.py            # Abstract base collector
│   ├── telegram_collector.py  # Telegram API integration
│   └── media_collector.py     # RSS feed parser
│
├── analyzers/             # Content analysis
│   ├── nlp_analyzer.py    # NLP processing pipeline
│   └── network_analyzer.py    # Graph analysis
│
├── dashboard/             # Web interface
│   └── app.py             # Streamlit application
│
└── tests/                 # Test suite
    ├── conftest.py        # Pytest fixtures
    ├── test_models.py     # Model tests
    ├── test_collectors.py # Collector tests
    └── test_analyzers.py  # Analyzer tests
```

### Database Schema

```mermaid
erDiagram
    SOURCES ||--o{ CONTENT : produces
    CONTENT ||--o| NLP_ANALYSIS : has
    CONTENT ||--o{ COGNITIVE_MARKERS : triggers
    CONTENT ||--o{ PROPAGATION : links
    CONTENT }o--o{ NARRATIVES : contains
    CONTENT ||--o{ FACTCHECKS : verified_by
```

---

## 🚀 Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (recommended)

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/your-repo/doppelganger-tracker.git
cd doppelganger-tracker

# Copy environment configuration
cp .env.example .env
# Edit .env with your settings (especially Telegram API keys)

# Start all services
docker-compose up -d

# Initialize database
docker-compose exec collector python main.py init-db

# Access dashboard
open http://localhost:8501
```

### Manual Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Download spaCy models
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm
python -m spacy download ru_core_news_sm

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
python main.py init-db

# Start services
python main.py collect &    # Background collection
python main.py dashboard    # Start dashboard
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://doppelganger:changeme@localhost:5432/doppelganger` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `TELEGRAM_API_ID` | Telegram API ID | *(required for Telegram)* |
| `TELEGRAM_API_HASH` | Telegram API Hash | *(required for Telegram)* |
| `LOG_LEVEL` | Logging level | `INFO` |
| `COLLECTION_INTERVAL` | Collection frequency (seconds) | `300` |
| `NLP_BATCH_SIZE` | NLP processing batch size | `500` |

### Source Configuration

Edit `config/sources.yaml` to add/modify monitored sources:

```yaml
telegram:
  pro_kremlin:
    - name: "Channel Name"
      channel: "@channel_username"
      language: "ru"
      type: "amplifier"
      priority: "high"

media:
  mainstream:
    en:
      - name: "News Outlet"
        url: "https://example.com/rss"
        type: "mainstream"
```

---

## 📖 Usage

### Command Line Interface

```bash
# Initialize database
python main.py init-db

# Run collection
python main.py collect                    # All sources
python main.py collect --telegram-only    # Telegram only
python main.py collect --media-only       # RSS feeds only
python main.py collect --lookback 14      # Look back 14 days

# Run analysis
python main.py analyze                    # Full analysis
python main.py analyze --nlp-only         # NLP only
python main.py analyze --network-only     # Network only
python main.py analyze --limit 1000       # Limit items

# Start dashboard
python main.py dashboard                  # Default port 8501
python main.py dashboard --port 8080      # Custom port

# Run tests
python main.py test                       # All tests
python main.py test --coverage            # With coverage
```

### Programmatic Usage

```python
# Collection
from collectors import TelegramCollector, MediaCollector

async def collect_telegram():
    collector = TelegramCollector()
    await collector.connect()
    result = await collector.collect_all(lookback_days=7)
    await collector.disconnect()
    return result

def collect_media():
    collector = MediaCollector()
    result = collector.collect_all_sync()
    collector.close()
    return result

# Analysis
from analyzers import NLPAnalyzer, NetworkAnalyzer

def analyze_content():
    # NLP Analysis
    nlp = NLPAnalyzer()
    nlp_result = nlp.analyze_unprocessed(limit=500)
    nlp.close()
    
    # Network Analysis
    net = NetworkAnalyzer()
    net_result = net.run_full_analysis(days_back=30)
    net.close()
    
    return nlp_result, net_result
```

---

## 📚 API Reference

### Database Models

#### Source
```python
class Source:
    id: UUID
    name: str
    source_type: str  # telegram, domain, media, factcheck
    platform: str
    language: str
    is_doppelganger: bool
    is_amplifier: bool
    is_active: bool
```

#### Content
```python
class Content:
    id: UUID
    source_id: UUID
    text_content: str
    text_hash: str  # SHA256 for deduplication
    content_type: str  # article, post, message, forward
    language: str
    published_at: datetime
    is_analyzed: bool
```

#### NLPAnalysis
```python
class NLPAnalysis:
    content_id: UUID
    sentiment_score: float  # -1.0 to 1.0
    sentiment_label: str  # positive, negative, neutral
    entities: dict  # {type: [entities]}
    is_propaganda: bool
    propaganda_techniques: list[str]
```

### Analyzers

#### NLPAnalyzer
```python
class NLPAnalyzer:
    def detect_language(text: str) -> tuple[str, float]
    def analyze_sentiment(text: str, lang: str) -> SentimentResult
    def extract_entities(text: str, lang: str) -> list[EntityDTO]
    def extract_keywords(text: str, lang: str, top_n: int) -> list[str]
    def detect_manipulation_markers(text: str, lang: str) -> list[CognitiveMarkerDTO]
    def analyze_content(content: Content) -> NLPAnalysisResult
    def analyze_unprocessed(limit: int) -> AnalysisResult
```

#### NetworkAnalyzer
```python
class NetworkAnalyzer:
    def build_content_graph(days_back: int) -> nx.DiGraph
    def build_source_graph(days_back: int) -> nx.DiGraph
    def detect_communities() -> dict[str, int]
    def find_superspreaders(top_n: int) -> list[SuperspreaderInfo]
    def detect_coordinated_behavior() -> list[CoordinatedBehaviorEvent]
    def export_to_gexf(filepath: str) -> str
    def run_full_analysis(days_back: int) -> dict
```

---

## 🛠 Development

### Setting Up Development Environment

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy

# Run linting
black .
flake8 .
mypy .

# Run tests
pytest -v
pytest --cov=. --cov-report=html
```

### Code Style

- **Formatter**: Black (line length 88)
- **Linter**: Flake8
- **Type Checking**: MyPy
- **Docstrings**: Google style

### Adding New Collectors

1. Create a new file in `collectors/`
2. Inherit from `BaseCollector` or `SyncCollector`
3. Implement required methods:
   - `collector_type` property
   - `collect_all()` method
4. Add to `collectors/__init__.py`

```python
from collectors.base import BaseCollector

class MyCollector(BaseCollector):
    @property
    def collector_type(self) -> str:
        return "my_source"
    
    async def collect_all(self) -> CollectionResult:
        self.start_run()
        # Collection logic here
        return self.end_run("completed")
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_models.py

# Run tests matching pattern
pytest -k "sentiment"

# Run with verbose output
pytest -v

# Skip slow tests
pytest -m "not slow"
```

### Test Categories

- **Unit Tests**: Individual function/method testing
- **Integration Tests**: Multi-component testing (marked with `@pytest.mark.integration`)
- **Database Tests**: Require PostgreSQL (marked with `@pytest.mark.requires_db`)

---

## ⚖️ Ethical Guidelines

### Purpose

This tool is designed for **academic research** to:
- Understand disinformation campaigns
- Develop counter-measures
- Support fact-checking efforts

### Data Collection Principles

1. **Public Sources Only**: Only collect publicly available content
2. **No Personal Data**: Do not collect or store personal information
3. **Research Purpose**: Use only for legitimate research
4. **GDPR Compliance**: Follow data protection regulations
5. **Attribution**: Always cite sources in research

### Responsible Use

- Do **NOT** use for surveillance
- Do **NOT** target individuals
- Do **NOT** spread disinformation
- Do **NOT** use for political manipulation

### Academic Citation

If you use this tool in your research, please cite:

```bibtex
@software{doppelganger_tracker,
  title = {Doppelganger Tracker: Disinformation Analysis Toolkit},
  year = {2025},
  url = {https://github.com/your-repo/doppelganger-tracker}
}
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [EU DisinfoLab](https://www.disinfo.eu/) - For Doppelganger research
- [DISARM Framework](https://disarmframework.org/) - Cognitive warfare framework
- [spaCy](https://spacy.io/) - NLP library
- [NetworkX](https://networkx.org/) - Network analysis
- [Streamlit](https://streamlit.io/) - Dashboard framework

---

## 📞 Support

For questions or issues:
- Open a GitHub Issue
- Contact: [your-email@institution.edu]

---

**⚠️ Disclaimer**: This tool is for educational and research purposes only. The authors are not responsible for misuse.
=======
# Veillanalyse
>>>>>>> abeb8b6190ec56bd1d555466c7a7c47450b91111
