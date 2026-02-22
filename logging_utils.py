#!/usr/bin/env python3

"""
Logging utilities for conversion system.
Process-safe logging with file and console output using concurrent-log-handler.
"""

import logging

import sys
import threading
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from config import AppConfig
try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
except ImportError:
    from logging.handlers import RotatingFileHandler as ConcurrentRotatingFileHandler
    print("WARNING: concurrent-log-handler not installed, falling back to standard RotatingFileHandler.")

log_lock = threading.Lock()
logger: Optional[logging.Logger] = None
current_job_handler: Optional[logging.Handler] = None


def setup_logging(config: AppConfig) -> Optional[logging.Logger]:
    """
    Initialize logging with console output only.
    File logging is strictly per-job (in /general) or per-process (in /ffmpeg).
    """
    global logger
    
    try:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        config.log_general_dir.mkdir(exist_ok=True)
        config.log_ffmpeg_dir.mkdir(exist_ok=True)
        
        # Console handler for stdout (always active)
        console_handler = logging.StreamHandler(sys.stdout)
        
        log_format = logging.Formatter(
            fmt='%(asctime)s - [PID:%(process)d] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d_%H:%M:%S'
        )
        console_handler.setFormatter(log_format)
        
        # Clear any existing handlers to avoid duplicates
        root_logger = logging.getLogger()
        if root_logger.handlers:
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
        
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[console_handler]
        )
        
        logger_instance = logging.getLogger(__name__)
        logger_instance.info("LOGGING_INITIALIZED (Console Only)")
        
        return logger_instance
    
    except Exception as e:
        print(f"CRITICAL_LOGGING_FAILURE: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_process_log_file(config: AppConfig, movie_name: str) -> Path:
    """
    Generate timestamped process log file path for FFmpeg output.
    Format: LOG_FFMPEG_DIR / CleanedName_Date.log
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Cleaned name is usually passed in, but sanitize just in case
    safe_movie_name = re.sub(r'[\\//*?:"<>| ]', "_", movie_name)
    
    return config.log_ffmpeg_dir / f"{safe_movie_name}_{timestamp}.log"

def start_job_logging(config: AppConfig, job_name: str) -> Path:
    """
    Switch logging to a job-specific file in LOG_GENERAL_DIR.
    Format: LOG_GENERAL_DIR / CleanedName_Date.log
    Returns the path to the log file.
    """
    global current_job_handler
    
    root_logger = logging.getLogger()
    
    # Create new job handler
    safe_name = re.sub(r'[\\//*?:"<>| ]', "_", job_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # LOG_GENERAL_DIR should strictly be used for application logic logs
    log_file = config.log_general_dir / f"{safe_name}_{timestamp}.log"
    
    # Ensure directory exists (redundant if setup_logging verified it, but safe)
    config.log_general_dir.mkdir(exist_ok=True)
    
    current_job_handler = ConcurrentRotatingFileHandler(
        str(log_file),
        mode='a',
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    
    log_format = logging.Formatter(
        fmt='%(asctime)s - [PID:%(process)d] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d_%H:%M:%S'
    )
    current_job_handler.setFormatter(log_format)
    
    root_logger.addHandler(current_job_handler)
    
    # Log the switch
    logging.info(f"STARTED_JOB_LOGGING: {job_name} -> {log_file}")
    
    return log_file


def restore_main_logging() -> None:
    """
    Switch logging back to console only.
    Removes the job-specific handler.
    """
    global current_job_handler
    
    root_logger = logging.getLogger()
    
    # Remove job handler
    if current_job_handler:
        current_job_handler.close()
        if current_job_handler in root_logger.handlers:
            root_logger.removeHandler(current_job_handler)
        current_job_handler = None
        
    logging.info("RESTORED_MAIN_LOGGING (Console Only)")
