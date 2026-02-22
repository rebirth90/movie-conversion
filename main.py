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

from logging_utils import setup_logging
from file_utils import validate_tool_paths
from core import queue_worker_loop
from config import validate_config

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    global shutdown_requested
    
    # 1. Try to get the logger (console only) - no file output for signal handler
    logger = setup_logging()

    # 2. Check if logger is valid before using it
    if logger:
        logger.info(f"SIGNAL_RECEIVED: {signal.Signals(signum).name}")
        logger.info("SHUTTING_DOWN_GRACEFULLY (will finish current job)")
    else:
        # Fallback: If logging fails, print to console so you still see the message
        print(f"SIGNAL_RECEIVED: {signal.Signals(signum).name}")
        print("SHUTTING_DOWN_GRACEFULLY (logging failed)")

    shutdown_requested = True
    sys.exit(0)


def process_queue() -> None:
    """Run queue worker daemon."""
    # Console only logging for startup/idle - no file output for queue worker
    logger = setup_logging()
    if logger is None:
        return

    try:
        # Validate tools before starting
        if not validate_tool_paths():
            logger.error("REQUIRED_TOOLS_MISSING")
            return

        queue_worker_loop(poll_interval=60)
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
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Validate configuration before starting
    if not validate_config():
        print("CONFIGURATION_VALIDATION_FAILED - check logs")
        sys.exit(1)

    # Always run in queue daemon mode
    process_queue()


if __name__ == "__main__":
    main()
