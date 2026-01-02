"""
Doppelganger Tracker - Structured Logging Configuration
========================================================
Configures structured JSON logging with loguru for observability.

Features:
- JSON serialization for log aggregation
- Contextual binding for tracking operations
- Multiple output handlers (console, file, JSON file)
- Performance metrics integration
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
from contextvars import ContextVar

from loguru import logger

# Context variables for request/operation tracking
operation_context: ContextVar[Dict[str, Any]] = ContextVar('operation_context', default={})


def setup_structured_logging(
    level: str = "INFO",
    json_logs: bool = True,
    enable_console: bool = True,
    enable_file: bool = True
) -> None:
    """
    Configure structured logging with JSON serialization.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Enable JSON format for structured logging
        enable_console: Enable console output
        enable_file: Enable file output

    Example:
        setup_structured_logging(level="INFO", json_logs=True)

        # Use with context binding
        with logger.contextualize(operation="collection", source_type="telegram"):
            logger.info("Starting collection", items=100)
    """
    # Remove default handler
    logger.remove()

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Console handler (human-readable with colors)
    if enable_console:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{extra[operation]}</cyan> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:{line} - "
                "<level>{message}</level>"
            ),
            level=level,
            colorize=True,
            # Add default context if not present
            filter=lambda record: record["extra"].setdefault("operation", "general") or True
        )

    # File handler (detailed text logs)
    if enable_file:
        logger.add(
            log_dir / "doppelganger_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            compression="zip",
            level="DEBUG",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{extra[operation]} | {name}:{function}:{line} - {message}"
            ),
            filter=lambda record: record["extra"].setdefault("operation", "general") or True
        )

    # JSON handler (structured logs for aggregation)
    if json_logs:
        logger.add(
            log_dir / "doppelganger_{time:YYYY-MM-DD}.jsonl",
            rotation="1 day",
            retention="30 days",
            compression="zip",
            level="INFO",
            serialize=True,  # Enable JSON serialization
            format="{message}",  # Raw JSON
            # Enrich with default context
            filter=lambda record: record["extra"].setdefault("operation", "general") or True
        )

    logger.info(
        "Structured logging initialized",
        json_enabled=json_logs,
        console_enabled=enable_console,
        file_enabled=enable_file,
        log_level=level
    )


def get_logger_with_context(**context):
    """
    Get a logger with bound context.

    Args:
        **context: Key-value pairs to bind to the logger

    Returns:
        Logger with bound context

    Example:
        log = get_logger_with_context(operation="collection", source_id="123")
        log.info("Collected items", count=50)
        # Produces: {"message": "Collected items", "operation": "collection", "source_id": "123", "count": 50}
    """
    return logger.bind(**context)


class LogContext:
    """
    Context manager for structured logging with automatic context binding.

    Example:
        with LogContext(operation="nlp_analysis", content_id="abc123"):
            logger.info("Starting analysis")
            # ... do work ...
            logger.info("Analysis complete", sentiment_score=0.85)
    """

    def __init__(self, **context):
        """
        Initialize log context.

        Args:
            **context: Key-value pairs to bind to all log messages in this context
        """
        self.context = context
        self._token = None

    def __enter__(self):
        """Enter context, binding logger context."""
        # Store current context
        current = operation_context.get()
        # Merge with new context
        merged = {**current, **self.context}
        self._token = operation_context.set(merged)

        # Return bound logger
        return logger.bind(**merged)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context, restoring previous logger context."""
        if self._token:
            operation_context.reset(self._token)


def log_performance(operation: str, duration_ms: float, **extra):
    """
    Log performance metrics in structured format.

    Args:
        operation: Name of the operation
        duration_ms: Duration in milliseconds
        **extra: Additional context (items_count, error_count, etc.)

    Example:
        log_performance(
            "collection",
            duration_ms=1234.56,
            items_collected=150,
            errors=0
        )
    """
    logger.bind(
        metric_type="performance",
        operation=operation,
        duration_ms=round(duration_ms, 2),
        **extra
    ).info(
        f"{operation} completed",
        duration_ms=round(duration_ms, 2),
        **extra
    )


def log_database_query(query_type: str, duration_ms: float, rows_affected: int = 0, **extra):
    """
    Log database query metrics.

    Args:
        query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)
        duration_ms: Query duration in milliseconds
        rows_affected: Number of rows affected
        **extra: Additional context

    Example:
        log_database_query(
            "SELECT",
            duration_ms=45.2,
            rows_affected=100,
            table="content"
        )
    """
    logger.bind(
        metric_type="database",
        query_type=query_type,
        duration_ms=round(duration_ms, 2),
        rows=rows_affected,
        **extra
    ).debug(
        f"Database {query_type}",
        duration_ms=round(duration_ms, 2),
        rows=rows_affected,
        **extra
    )


def log_api_request(
    service: str,
    endpoint: str,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None,
    **extra
):
    """
    Log external API request metrics.

    Args:
        service: Service name (telegram, media, etc.)
        endpoint: API endpoint or method
        status_code: HTTP status code (if applicable)
        duration_ms: Request duration in milliseconds
        error: Error message if request failed
        **extra: Additional context

    Example:
        log_api_request(
            "telegram",
            "messages.getHistory",
            status_code=200,
            duration_ms=234.5,
            items_fetched=50
        )
    """
    log_data = {
        "metric_type": "api_request",
        "service": service,
        "endpoint": endpoint,
        **extra
    }

    if status_code:
        log_data["status_code"] = status_code
    if duration_ms:
        log_data["duration_ms"] = round(duration_ms, 2)
    if error:
        log_data["error"] = error

    level = "error" if error or (status_code and status_code >= 400) else "info"

    logger.bind(**log_data).log(
        level.upper(),
        f"{service} API request",
        **log_data
    )


def log_collection_result(
    source_type: str,
    source_name: str,
    items_collected: int,
    items_new: int,
    items_updated: int,
    errors: int = 0,
    duration_ms: Optional[float] = None,
    **extra
):
    """
    Log collection operation results.

    Args:
        source_type: Type of source (telegram, media, web)
        source_name: Name of specific source
        items_collected: Total items collected
        items_new: Number of new items
        items_updated: Number of updated items
        errors: Number of errors encountered
        duration_ms: Operation duration in milliseconds
        **extra: Additional context

    Example:
        log_collection_result(
            "telegram",
            "@channel_name",
            items_collected=150,
            items_new=100,
            items_updated=50,
            errors=0,
            duration_ms=5432.1
        )
    """
    logger.bind(
        metric_type="collection_result",
        source_type=source_type,
        source_name=source_name,
        items_collected=items_collected,
        items_new=items_new,
        items_updated=items_updated,
        errors=errors,
        duration_ms=round(duration_ms, 2) if duration_ms else None,
        **extra
    ).info(
        f"Collection completed: {source_name}",
        items_collected=items_collected,
        items_new=items_new,
        items_updated=items_updated,
        errors=errors
    )


def log_analysis_result(
    analysis_type: str,
    items_analyzed: int,
    duration_ms: float,
    results: Optional[Dict[str, Any]] = None,
    errors: int = 0,
    **extra
):
    """
    Log analysis operation results.

    Args:
        analysis_type: Type of analysis (nlp, network, topic, d3lta)
        items_analyzed: Number of items analyzed
        duration_ms: Operation duration in milliseconds
        results: Analysis results summary
        errors: Number of errors encountered
        **extra: Additional context

    Example:
        log_analysis_result(
            "nlp",
            items_analyzed=500,
            duration_ms=12345.6,
            results={"propaganda_detected": 45, "avg_sentiment": -0.3},
            errors=2
        )
    """
    log_data = {
        "metric_type": "analysis_result",
        "analysis_type": analysis_type,
        "items_analyzed": items_analyzed,
        "duration_ms": round(duration_ms, 2),
        "errors": errors,
        **extra
    }

    if results:
        log_data["results"] = results

    logger.bind(**log_data).info(
        f"{analysis_type.upper()} analysis completed",
        items=items_analyzed,
        errors=errors
    )


# Convenience aliases
def log_error(message: str, error: Exception, **context):
    """
    Log an error with exception details.

    Args:
        message: Error message
        error: Exception object
        **context: Additional context
    """
    logger.bind(
        error_type=type(error).__name__,
        error_message=str(error),
        **context
    ).error(
        message,
        error=str(error),
        error_type=type(error).__name__
    )


def log_warning(message: str, **context):
    """
    Log a warning with context.

    Args:
        message: Warning message
        **context: Additional context
    """
    logger.bind(**context).warning(message, **context)


# Export main functions
__all__ = [
    'setup_structured_logging',
    'get_logger_with_context',
    'LogContext',
    'log_performance',
    'log_database_query',
    'log_api_request',
    'log_collection_result',
    'log_analysis_result',
    'log_error',
    'log_warning',
]
