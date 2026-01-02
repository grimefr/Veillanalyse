"""
Doppelganger Tracker - Utilities Package
=========================================
Common utilities and helper functions.
"""

from .logging_config import (
    setup_structured_logging,
    get_logger_with_context,
    LogContext,
    log_performance,
    log_database_query,
    log_api_request,
    log_collection_result,
    log_analysis_result,
    log_error,
    log_warning,
)

from .async_helpers import (
    get_thread_pool,
    set_thread_pool_size,
    run_in_executor,
    run_in_thread,
    run_parallel,
    shutdown_thread_pool,
    ScopedThreadPool,
)

__all__ = [
    # Logging
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
    # Async helpers
    'get_thread_pool',
    'set_thread_pool_size',
    'run_in_executor',
    'run_in_thread',
    'run_parallel',
    'shutdown_thread_pool',
    'ScopedThreadPool',
]
