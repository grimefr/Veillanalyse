# 📘 Best Practices Guide - Doppelganger Tracker v2

**Audience**: Developers, DevOps Engineers, Security Engineers
**Last Updated**: 2026-01-02

---

## 🎯 Core Principles

1. **Security First**: Never compromise security for convenience
2. **Performance Matters**: Design for scale from day one
3. **Fail Explicitly**: No silent failures; fail fast and loud
4. **Test Everything**: Code without tests is legacy code
5. **Document Decisions**: Architecture Decision Records (ADRs)

---

## 🔒 Security Best Practices

### 1. Credential Management

**✅ DO**:
```python
# Load from environment variables
from config.settings import settings

db_password = settings.postgres_password  # Required field
```

**❌ DON'T**:
```python
# NEVER hardcode credentials
DB_PASSWORD = "changeme"
DATABASE_URL = "postgresql://user:password@localhost/db"
```

**Docker Secrets** (Production):
```yaml
secrets:
  postgres_password:
    external: true

services:
  app:
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
```

---

### 2. Dependency Management

**✅ DO**: Pin all versions
```txt
# requirements.txt
requests==2.31.0           # Exact version
torch==2.1.2              # No wildcards
```

**❌ DON'T**: Use unpinned or wildcard versions
```txt
requests>=2.0              # Too broad
torch                      # No version at all
```

**Weekly Audit**:
```bash
# Check for vulnerabilities
pip-audit

# Update dependencies safely
pip list --outdated
pip install --upgrade package==x.y.z  # Test one at a time
```

---

### 3. Input Validation

**✅ DO**: Validate all external inputs
```python
from pydantic import BaseModel, Field, validator

class ContentInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., regex=r'https?://.*')

    @validator('url')
    def validate_url(cls, v):
        if not v.startswith('https'):
            raise ValueError('URL must use HTTPS')
        return v
```

**❌ DON'T**: Trust user input
```python
# Unsafe - no validation
def save_content(title, url):
    content = Content(title=title, url=url)  # SQL injection risk
    session.add(content)
```

---

### 4. Error Handling

**✅ DO**: Catch specific exceptions
```python
from sqlalchemy.exc import IntegrityError, OperationalError

try:
    session.commit()
except IntegrityError as e:
    logger.error(f"Duplicate record: {e}")
    session.rollback()
    raise DuplicateRecordError(str(e))
except OperationalError as e:
    logger.error(f"Database connection lost: {e}")
    session.rollback()
    raise DatabaseUnavailableError(str(e))
```

**❌ DON'T**: Catch generic exceptions
```python
try:
    session.commit()
except Exception as e:  # Too broad - masks bugs
    logger.error(f"Error: {e}")
    pass  # Silent failure - NEVER do this
```

---

## 🚀 Performance Best Practices

### 1. Database Query Optimization

**✅ DO**: Use eager loading to prevent N+1 queries
```python
from sqlalchemy.orm import joinedload, selectinload

# Efficient - single query with JOIN
contents = (
    session.query(Content)
    .options(
        joinedload(Content.source),           # One-to-one/many-to-one
        selectinload(Content.nlp_analysis),   # One-to-many
        joinedload(Content.narratives)
    )
    .filter(Content.published_at >= cutoff)
    .all()
)

# Access related data without additional queries
for content in contents:
    print(content.source.name)  # No DB hit
    print(content.nlp_analysis.sentiment)  # No DB hit
```

**❌ DON'T**: Lazy load in loops
```python
# Inefficient - N+1 query problem
contents = session.query(Content).all()  # 1 query

for content in contents:
    print(content.source.name)  # +N queries
    print(content.nlp_analysis.sentiment)  # +N queries
```

---

### 2. Indexing Strategy

**✅ DO**: Index frequently queried columns
```python
from sqlalchemy import Index

class Content(Base):
    __tablename__ = 'content'

    __table_args__ = (
        # Single column indexes
        Index('ix_content_source_id', 'source_id'),
        Index('ix_content_collected_at', 'collected_at'),

        # Composite indexes for complex queries
        Index('ix_content_source_collected', 'source_id', 'collected_at'),

        # Partial indexes (PostgreSQL)
        Index('ix_content_unanalyzed', 'id', postgresql_where=(analyzed==False)),
    )
```

**Check index usage**:
```sql
-- Find missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public' AND tablename = 'content'
ORDER BY abs(correlation) DESC;

-- Check index usage stats
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC;
```

---

### 3. Connection Pooling

**✅ DO**: Configure appropriate pool sizes
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=20,              # Base connections
    max_overflow=30,           # Additional connections under load
    pool_timeout=30,           # Wait time for connection
    pool_recycle=3600,         # Recycle connections hourly
    pool_pre_ping=True,        # Check connection validity
    echo_pool=True,            # Log pool events (dev only)
)
```

**Monitor pool**:
```python
# Check pool status
print(f"Pool size: {engine.pool.size()}")
print(f"Checked out: {engine.pool.checkedout()}")
print(f"Overflow: {engine.pool.overflow()}")
```

---

### 4. Async Best Practices

**✅ DO**: Use thread pool for CPU-bound tasks
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)

async def process_nlp(text: str):
    # Run CPU-bound spaCy processing in thread pool
    doc = await asyncio.get_event_loop().run_in_executor(
        _executor,
        nlp_model,
        text
    )
    return doc
```

**❌ DON'T**: Block the event loop
```python
async def process_nlp(text: str):
    doc = nlp_model(text)  # BLOCKS event loop for seconds
    return doc
```

---

### 5. Caching Strategy

**✅ DO**: Cache expensive operations
```python
from functools import lru_cache
from cachetools import TTLCache
import threading

# In-memory cache with TTL
_model_cache = TTLCache(maxsize=10, ttl=3600)
_cache_lock = threading.Lock()

def get_cached_model(lang: str):
    with _cache_lock:
        if lang not in _model_cache:
            _model_cache[lang] = load_expensive_model(lang)
        return _model_cache[lang]

# Redis cache for distributed systems
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)

def get_or_cache(key: str, compute_fn, ttl=3600):
    value = cache.get(key)
    if value is None:
        value = compute_fn()
        cache.setex(key, ttl, value)
    return value
```

---

## 📊 Logging Best Practices

### 1. Structured Logging

**✅ DO**: Use structured JSON logs
```python
from loguru import logger

# Configure JSON output
logger.add(
    "logs/app.jsonl",
    serialize=True,
    format="{message}",
    rotation="100 MB",
    retention="30 days"
)

# Log with context
logger.bind(
    operation="collection",
    source_id=123,
    items_collected=45,
    duration_ms=1234
).info("Collection completed")

# Output: {"operation": "collection", "source_id": 123, ...}
```

**❌ DON'T**: Use unstructured string logs
```python
logger.info(f"Collected 45 items from source 123 in 1234ms")
# Cannot parse programmatically
```

---

### 2. Log Levels

**Usage**:
- `DEBUG`: Detailed diagnostic info (dev only)
- `INFO`: General informational messages
- `WARNING`: Warning messages (recoverable issues)
- `ERROR`: Error messages (handled exceptions)
- `CRITICAL`: Critical errors (unrecoverable)

**Example**:
```python
logger.debug(f"Processing content: {content.id}")  # Dev only
logger.info("Collection started")                   # Normal flow
logger.warning("Rate limit hit, retrying in 60s")   # Recoverable
logger.error(f"Failed to parse RSS: {e}")           # Handled error
logger.critical("Database connection lost!")        # System failure
```

---

### 3. Performance Logging

**✅ DO**: Log operation latency
```python
import time
from contextlib import contextmanager

@contextmanager
def log_duration(operation: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.bind(operation=operation, duration_ms=duration_ms).info("Operation completed")

# Usage
with log_duration("nlp_processing"):
    result = analyze_text(text)
```

---

## 🧪 Testing Best Practices

### 1. Test Organization

**Structure**:
```
tests/
├── unit/               # Fast, isolated tests
│   ├── test_models.py
│   ├── test_dto.py
│   └── test_utils.py
├── integration/        # Tests with DB, Redis
│   ├── test_collectors.py
│   ├── test_analyzers.py
│   └── test_pipeline.py
├── e2e/                # End-to-end tests
│   └── test_workflows.py
└── fixtures/           # Test data
    └── sample_content.json
```

---

### 2. Test Fixtures

**✅ DO**: Use pytest fixtures
```python
import pytest
from factory import Factory, Faker

# conftest.py
@pytest.fixture
def db_session():
    """Provide a clean database session for each test."""
    from database import get_engine, Base
    engine = get_engine("postgresql://test:test@localhost/test_db")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)

# Factory pattern for test data
class ContentFactory(Factory):
    class Meta:
        model = Content

    title = Faker('sentence')
    text_content = Faker('paragraph')
    url = Faker('url')

# test_collectors.py
def test_collect_content(db_session):
    content = ContentFactory.create()
    db_session.add(content)
    db_session.commit()

    assert content.id is not None
```

---

### 3. Test Coverage

**Target**: > 80% coverage
```bash
# Run tests with coverage
pytest --cov=. --cov-report=html --cov-report=term-missing

# Check coverage
coverage report

# Enforce minimum coverage
pytest --cov=. --cov-fail-under=80
```

---

## 🐳 Docker Best Practices

### 1. Multi-Stage Builds

**✅ DO**: Separate build and runtime
```dockerfile
# Builder stage
FROM python:3.11.7-slim AS builder
RUN apt-get update && apt-get install -y build-essential
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Production stage
FROM python:3.11.7-slim AS production
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*
COPY . /app
USER appuser
CMD ["python", "main.py"]
```

---

### 2. Security Hardening

**✅ DO**: Run as non-root
```dockerfile
# Create non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root
USER appuser
```

**Scan for vulnerabilities**:
```bash
# Trivy scan
trivy image doppelganger-tracker:latest

# Grype scan
grype doppelganger-tracker:latest

# Docker Scout
docker scout cves doppelganger-tracker:latest
```

---

### 3. Resource Limits

**✅ DO**: Set memory and CPU limits
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## 📈 Monitoring & Observability

### 1. Metrics

**✅ DO**: Expose Prometheus metrics
```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
collection_counter = Counter(
    'collection_total',
    'Total number of collections',
    ['source_type', 'status']
)

nlp_processing_duration = Histogram(
    'nlp_processing_seconds',
    'Time spent in NLP processing',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

active_connections = Gauge(
    'database_connections_active',
    'Number of active database connections'
)

# Usage
collection_counter.labels(source_type='telegram', status='success').inc()

with nlp_processing_duration.time():
    process_nlp(text)

active_connections.set(engine.pool.checkedout())

# Start metrics server
start_http_server(9090)  # Metrics on :9090/metrics
```

---

### 2. Health Checks

**✅ DO**: Implement comprehensive health checks
```python
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

app = FastAPI()

@app.get("/health")
async def health_check():
    """Basic liveness probe."""
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness_check():
    """Readiness probe with dependency checks."""
    health = {
        "status": "ok",
        "checks": {}
    }

    # Check database
    try:
        session.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {e}"
        health["status"] = "degraded"

    # Check Redis
    try:
        redis_client.ping()
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"error: {e}"
        health["status"] = "degraded"

    if health["status"] != "ok":
        raise HTTPException(status_code=503, detail=health)

    return health
```

---

## 🔄 CI/CD Best Practices

### 1. Automated Testing

**GitHub Actions Example**:
```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: pip install -r requirements.txt -r requirements-dev.txt

    - name: Run tests
      run: pytest --cov=. --cov-report=xml

    - name: Security scan
      run: |
        pip-audit
        bandit -r . -f json -o bandit-report.json

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

### 2. Container Scanning

```yaml
    - name: Build image
      run: docker build -t app:${{ github.sha }} .

    - name: Scan image
      run: trivy image --severity HIGH,CRITICAL app:${{ github.sha }}
```

---

## 📚 Documentation Standards

### 1. Code Documentation

**✅ DO**: Write comprehensive docstrings
```python
def analyze_content(
    content: Content,
    *,
    force: bool = False,
    batch_size: int = 100
) -> AnalysisResult:
    """
    Analyze content using NLP and network analysis.

    This function performs sentiment analysis, entity extraction,
    and propaganda detection on the provided content.

    Args:
        content: Content object to analyze
        force: Force re-analysis even if already analyzed
        batch_size: Number of items to process in each batch

    Returns:
        AnalysisResult: Object containing analysis results with
            sentiment scores, entities, and manipulation markers

    Raises:
        ValueError: If content.text_content is None or empty
        DatabaseError: If database commit fails

    Example:
        >>> content = session.query(Content).first()
        >>> result = analyze_content(content, force=True)
        >>> print(result.sentiment_score)
        0.75

    Note:
        This is a CPU-intensive operation. Consider running
        in a thread pool for async contexts.

    See Also:
        - NLPAnalyzer.analyze_full(): Lower-level analysis
        - batch_analyze(): Analyze multiple contents efficiently
    """
    if not content.text_content:
        raise ValueError("Content text cannot be empty")

    # Implementation...
```

---

### 2. Architecture Decision Records (ADRs)

**Template**:
```markdown
# ADR-001: Use PostgreSQL for Primary Database

## Status
Accepted

## Context
We need a database to store collected content, analysis results,
and network graphs.

## Decision
Use PostgreSQL 16 as the primary database.

## Consequences
### Positive
- JSONB support for flexible schema
- Full-text search capabilities
- Mature ecosystem and tooling
- Strong ACID guarantees

### Negative
- Higher resource usage than SQLite
- Requires external service (not embedded)

## Alternatives Considered
- MongoDB: No ACID, eventual consistency issues
- SQLite: Not suitable for concurrent writes
- MySQL: Inferior JSON support

## Date
2026-01-02
```

---

## ✅ Pre-Deployment Checklist

Before deploying to production:

- [ ] All tests passing (unit, integration, e2e)
- [ ] Test coverage > 80%
- [ ] Security audit completed
- [ ] Dependency vulnerabilities scanned
- [ ] Container image scanned
- [ ] Secrets externalized (no hardcoded credentials)
- [ ] Environment-specific configs separated
- [ ] Database migrations tested
- [ ] Backup/restore procedure documented
- [ ] Monitoring and alerting configured
- [ ] Logging aggregation set up
- [ ] Health checks implemented
- [ ] Resource limits configured
- [ ] Disaster recovery plan documented
- [ ] Incident response plan created

---

**Document Version**: 1.0
**Last Updated**: 2026-01-02
**Next Review**: 2026-04-02
