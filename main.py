#!/usr/bin/env python3

"""
Main entry point for movie and TV series conversion system.
Simplified to focus on queue-based daemon mode.

Usage:
  Queue worker (daemon mode): python -m main
  Add to queue manually: echo "/path/to/content" >> /share/conversion.txt
"""

import sys
import signal
import threading
import logging
from dotenv import load_dotenv

from logging_utils import setup_logging
from file_utils import validate_tool_paths
from core import queue_worker_loop
from config import AppConfig

# Global flag for graceful shutdown
shutdown_event = threading.Event()


def signal_handler(signum, frame) -> None:
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    global shutdown_event
    
    logger = logging.getLogger(__name__)
    try:
        sig_name = signal.Signals(signum).name
    except Exception:
        sig_name = str(signum)
        
    logger.info(f"SIGNAL_RECEIVED: {sig_name}")
    logger.info("SHUTTING_DOWN_GRACEFULLY (will finish current job)")

    shutdown_event.set()


def process_queue(config: AppConfig) -> None:
    """Run queue worker daemon."""
    # Console only logging for startup/idle - no file output for queue worker
    logger = setup_logging(config)
    if logger is None:
        return

    try:
        # Validate tools before starting
        if not validate_tool_paths(config):
            logger.error("REQUIRED_TOOLS_MISSING")
            return

        queue_worker_loop(config, shutdown_event, poll_interval=60)
    except KeyboardInterrupt:
        logger.info("QUEUE_WORKER_INTERRUPTED")
    except Exception as e:
        logger.exception("FATAL_ERROR_QUEUE_WORKER")
        raise


def main() -> None:
    """
    Main entry point.
    Runs queue daemon that processes conversion.txt entries.
    """
    load_dotenv()
    
    global shutdown_event
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Validate configuration before starting
    config = AppConfig()
    config.setup_directories()
    if not config.validate():
        print("CONFIGURATION_VALIDATION_FAILED - check logs")
        sys.exit(1)

    from db_utils import DatabaseManager
    db = DatabaseManager(config.db_path)

    # Always run in queue daemon mode
    process_queue(config)


if __name__ == "__main__":
    main()
