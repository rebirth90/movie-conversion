#!/usr/bin/env python3

"""
Standalone script to manually trigger the creation of the database file
and its tables for fresh deployments.
"""

from config import AppConfig
from db_utils import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Initializing database...")
    config = AppConfig()
    
    # The DatabaseManager __init__ will automatically create the file and setup tables
    db = DatabaseManager(config.db_path)
    
    logger.info(f"Database successfully initialized at: {config.db_path}")
