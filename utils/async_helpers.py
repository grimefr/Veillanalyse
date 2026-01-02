"""
Doppelganger Tracker - Async Utilities
=======================================
Helper utilities for async operations and CPU-bound task execution.

Provides utilities to run CPU-bound operations in thread pools
without blocking the async event loop.
"""

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar, Any
from loguru import logger

# Global thread pool executor for CPU-bound tasks
_executor: ThreadPoolExecutor = None
_executor_max_workers = 4

T = TypeVar('T')


def get_thread_pool() -> ThreadPoolExecutor:
    """
    Get or create the global thread pool executor.

    Returns:
        ThreadPoolExecutor: Shared executor for CPU-bound tasks
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=_executor_max_workers,
            thread_name_prefix="nlp_worker"
        )
        logger.info(f"Initialized thread pool with {_executor_max_workers} workers")
    return _executor


def set_thread_pool_size(max_workers: int):
    """
    Set the maximum number of worker threads.

    Must be called before the first use of get_thread_pool().

    Args:
        max_workers: Maximum number of worker threads
    """
    global _executor_max_workers, _executor
    if _executor is not None:
        logger.warning("Thread pool already initialized, size change will not take effect")
    else:
        _executor_max_workers = max_workers
        logger.info(f"Thread pool size set to {max_workers} workers")


async def run_in_executor(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Run a CPU-bound function in a thread pool executor.

    Prevents blocking the async event loop when performing
    CPU-intensive operations like NLP processing.

    Args:
        func: Synchronous function to execute
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Example:
        # Instead of blocking:
        # result = expensive_nlp_function(text)

        # Use async executor:
        result = await run_in_executor(expensive_nlp_function, text)
    """
    loop = asyncio.get_event_loop()
    executor = get_thread_pool()

    # Use functools.partial to handle kwargs
    if kwargs:
        func = functools.partial(func, **kwargs)

    return await loop.run_in_executor(executor, func, *args)


def run_in_thread(func: Callable[..., T]) -> Callable[..., asyncio.Future[T]]:
    """
    Decorator to automatically run a synchronous function in a thread pool.

    Use this decorator on CPU-bound synchronous functions that need to be
    called from async code without blocking the event loop.

    Args:
        func: Synchronous function to wrap

    Returns:
        Async wrapper function

    Example:
        @run_in_thread
        def expensive_nlp_operation(text: str) -> dict:
            nlp = get_spacy_model("en")
            doc = nlp(text)
            return {"entities": [ent.text for ent in doc.ents]}

        # Can now be called with await:
        async def process_text(text):
            result = await expensive_nlp_operation(text)
            return result
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        return await run_in_executor(func, *args, **kwargs)

    return async_wrapper


async def run_parallel(funcs: list[Callable], *args_list) -> list:
    """
    Run multiple CPU-bound functions in parallel using thread pool.

    Args:
        funcs: List of functions to execute
        *args_list: List of argument tuples, one per function

    Returns:
        List of results in the same order as funcs

    Example:
        results = await run_parallel(
            [analyze_sentiment, extract_entities, detect_keywords],
            (text1,), (text2,), (text3,)
        )
    """
    tasks = []
    for i, func in enumerate(funcs):
        args = args_list[i] if i < len(args_list) else ()
        tasks.append(run_in_executor(func, *args))

    return await asyncio.gather(*tasks)


def shutdown_thread_pool(wait: bool = True):
    """
    Shutdown the thread pool executor.

    Should be called when the application exits.

    Args:
        wait: If True, wait for all pending futures to complete
    """
    global _executor
    if _executor is not None:
        logger.info("Shutting down thread pool executor")
        _executor.shutdown(wait=wait)
        _executor = None


# Context manager for scoped thread pool
class ScopedThreadPool:
    """
    Context manager for a scoped thread pool executor.

    Example:
        async with ScopedThreadPool(max_workers=8) as pool:
            results = await pool.run(expensive_function, arg1, arg2)
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = None

    async def __aenter__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="scoped_worker"
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=True)

    async def run(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run function in this scoped thread pool."""
        loop = asyncio.get_event_loop()
        if kwargs:
            func = functools.partial(func, **kwargs)
        return await loop.run_in_executor(self.executor, func, *args)


__all__ = [
    'get_thread_pool',
    'set_thread_pool_size',
    'run_in_executor',
    'run_in_thread',
    'run_parallel',
    'shutdown_thread_pool',
    'ScopedThreadPool',
]
