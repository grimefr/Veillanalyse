#!/usr/bin/env python3
"""
Doppelganger Tracker - Main Entry Point
========================================
Command-line interface for the Doppelganger disinformation analysis toolkit.

Usage:
    python main.py collect          # Run collection
    python main.py analyze          # Run analysis
    python main.py dashboard        # Start dashboard
    python main.py init-db          # Initialize database
    python main.py --help           # Show help

Author: Academic Research Project
License: Educational Use Only
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

from loguru import logger
from utils.logging_config import setup_structured_logging, LogContext

# Configure logging (now using structured logging)
def setup_logging(level: str = "INFO"):
    """Configure structured logging with JSON serialization."""
    setup_structured_logging(
        level=level,
        json_logs=True,
        enable_console=True,
        enable_file=True
    )


def cmd_init_db(args):
    """Initialize database tables."""
    logger.info("Initializing database...")
    
    from database import init_db
    init_db()
    
    logger.info("Database initialized successfully!")


def cmd_collect(args):
    """Run content collection with structured logging."""
    from utils.logging_config import log_collection_result, log_error

    with LogContext(operation="collection", lookback_days=args.lookback):
        logger.info("Starting collection", telegram=not args.media_only, media=not args.telegram_only)

        async def run_collection():
            results = []

            # Telegram collection
            if not args.media_only:
                with LogContext(source_type="telegram"):
                    try:
                        from collectors.telegram_collector import TelegramCollector
                        collector = TelegramCollector()

                        if await collector.connect():
                            result = await collector.collect_all(
                                lookback_days=args.lookback,
                                limit_per_channel=args.limit
                            )
                            results.append(("Telegram", result))
                            await collector.disconnect()
                        else:
                            logger.warning("Telegram not configured, skipping")

                        collector.close()
                    except Exception as e:
                        log_error("Telegram collection failed", e, source_type="telegram")

            # Media collection
            if not args.telegram_only:
                with LogContext(source_type="media"):
                    try:
                        from collectors.media_collector import MediaCollector
                        collector = MediaCollector()
                        result = collector.collect_all_sync()
                        results.append(("Media", result))
                        collector.close()
                    except Exception as e:
                        log_error("Media collection failed", e, source_type="media")

            # Summary with structured logging
            logger.info("Collection completed", total_sources=len(results))
            for name, result in results:
                log_collection_result(
                    source_type=name.lower(),
                    source_name=name,
                    items_collected=result.items_new + result.items_updated,
                    items_new=result.items_new,
                    items_updated=result.items_updated,
                    errors=result.errors_count
                )
    
    asyncio.run(run_collection())


def cmd_analyze(args):
    """Run content analysis with structured logging."""
    from utils.logging_config import log_analysis_result, log_error
    import time

    with LogContext(operation="analysis"):
        logger.info("Starting analysis", nlp=not args.network_only, network=not args.nlp_only)

        results = {}

        # NLP Analysis
        if not args.network_only:
            with LogContext(analysis_type="nlp"):
                try:
                    start_time = time.time()
                    from analyzers.nlp_analyzer import NLPAnalyzer
                    analyzer = NLPAnalyzer()
                    result = analyzer.analyze_unprocessed(limit=args.limit)
                    duration_ms = (time.time() - start_time) * 1000
                    results["NLP"] = result
                    analyzer.close()

                    log_analysis_result(
                        "nlp",
                        items_analyzed=result.get("processed", 0),
                        duration_ms=duration_ms,
                        errors=result.get("errors", 0)
                    )
                except Exception as e:
                    log_error("NLP analysis failed", e, analysis_type="nlp")
    
        # Network Analysis
        if not args.nlp_only:
            with LogContext(analysis_type="network"):
                try:
                    start_time = time.time()
                    from analyzers.network_analyzer import NetworkAnalyzer
                    analyzer = NetworkAnalyzer()
                    result = analyzer.run_full_analysis(days_back=args.days)
                    duration_ms = (time.time() - start_time) * 1000
                    results["Network"] = result

                    log_analysis_result(
                        "network",
                        items_analyzed=result.get("stats", {}).get("node_count", 0),
                        duration_ms=duration_ms,
                        results={
                            "nodes": result.get("stats", {}).get("node_count", 0),
                            "edges": result.get("stats", {}).get("edge_count", 0)
                        }
                    )
                except Exception as e:
                    log_error("Network analysis failed", e, analysis_type="network")

        # Summary
        logger.info("Analysis completed", total_analyses=len(results))


def cmd_dashboard(args):
    """Start the Streamlit dashboard."""
    import subprocess
    
    logger.info(f"Starting dashboard on port {args.port}...")
    
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(dashboard_path),
        "--server.port", str(args.port),
        "--server.address", args.host
    ])


def cmd_test(args):
    """Run test suite."""
    import subprocess
    
    logger.info("Running tests...")
    
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    if args.coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])
    
    subprocess.run(cmd)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Doppelganger Tracker - Disinformation Analysis Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py init-db              Initialize database
    python main.py collect              Run all collectors
    python main.py collect --telegram-only  Run Telegram only
    python main.py analyze --limit 100  Analyze 100 items
    python main.py dashboard            Start web dashboard
    python main.py test                 Run tests
        """
    )
    
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init-db command
    init_parser = subparsers.add_parser("init-db", help="Initialize database")
    init_parser.set_defaults(func=cmd_init_db)
    
    # collect command
    collect_parser = subparsers.add_parser("collect", help="Run collection")
    collect_parser.add_argument(
        "--telegram-only", action="store_true",
        help="Only collect from Telegram"
    )
    collect_parser.add_argument(
        "--media-only", action="store_true",
        help="Only collect from media feeds"
    )
    collect_parser.add_argument(
        "--lookback", type=int, default=7,
        help="Days to look back (default: 7)"
    )
    collect_parser.add_argument(
        "--limit", type=int, default=100,
        help="Max items per source (default: 100)"
    )
    collect_parser.set_defaults(func=cmd_collect)
    
    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run analysis")
    analyze_parser.add_argument(
        "--nlp-only", action="store_true",
        help="Only run NLP analysis"
    )
    analyze_parser.add_argument(
        "--network-only", action="store_true",
        help="Only run network analysis"
    )
    analyze_parser.add_argument(
        "--limit", type=int, default=500,
        help="Max items to analyze (default: 500)"
    )
    analyze_parser.add_argument(
        "--days", type=int, default=30,
        help="Days for network analysis (default: 30)"
    )
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Start dashboard")
    dashboard_parser.add_argument(
        "--port", type=int, default=8501,
        help="Port number (default: 8501)"
    )
    dashboard_parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host address (default: 0.0.0.0)"
    )
    dashboard_parser.set_defaults(func=cmd_dashboard)
    
    # test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument(
        "--coverage", action="store_true",
        help="Include coverage report"
    )
    test_parser.set_defaults(func=cmd_test)
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(log_level)
    
    # Show banner
    logger.info("=" * 60)
    logger.info("🎯 DOPPELGANGER TRACKER")
    logger.info("   Disinformation Analysis Toolkit")
    logger.info("=" * 60)
    
    # Execute command
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
