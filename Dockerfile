# =============================================================================
# DOPPELGANGER TRACKER - Dockerfile
# =============================================================================
# Multi-stage build for optimized production image
# =============================================================================

# Pin exact base image version for reproducibility and security
# Note: Update digest when updating Python version
FROM python:3.11.7-slim AS base

# Metadata
LABEL maintainer="Doppelganger Tracker Project"
LABEL description="Disinformation analysis toolkit"
LABEL version="2.0"
LABEL org.opencontainers.image.source="https://github.com/your-org/doppelganger-tracker"

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# =============================================================================
# Builder Stage - Install dependencies
# =============================================================================
FROM base AS builder

# Install build dependencies (including git for d3lta installation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy models (small versions for faster builds)
RUN python -m spacy download en_core_web_sm && \
    python -m spacy download fr_core_news_sm && \
    python -m spacy download ru_core_news_sm

# =============================================================================
# Production Stage
# =============================================================================
FROM base AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directory
WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

# Create required directories
RUN mkdir -p /app/data /app/logs /app/exports/graphs /app/exports/reports /app/exports/data /app/.sessions \
    && chown -R appuser:appuser /app

# Copy entrypoint script first
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command
CMD ["python", "--version"]

# =============================================================================
# Development Stage
# =============================================================================
FROM production AS development

# Switch back to root for dev tools
USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    flake8 \
    ipython

# Switch back to appuser
USER appuser

# Default to shell for development
CMD ["/bin/bash"]
