#!/usr/bin/env python3

"""
TV Series utilities for detecting, parsing, and processing TV series paths.
Handles season folder renaming and episode queueing.
"""

import logging
import re
import shutil
from db_utils import DatabaseManager
from pathlib import Path

logger = logging.getLogger(__name__)

def clean_season_folder_name(season_path: Path):
    """
    Standardize season folder names.
    e.g. "Season.01" -> "Season01"
    
    Returns:
        Path: The path to the (potentially renamed) season directory.
        None: If renaming failed or folder is invalid.
    """
    season_directory_lower = season_path.name.lower()
    season_directory_name = None
    
    match = re.search(r's(\d{2})', season_directory_lower)
    if match:
        season_directory_name = f"Season{match.group(1)}"
    
    # Pattern 2: Season 1, Season 01, Season01
    match = re.search(r'season[\s._-]*(\d+)', season_directory_lower)
    if match:
        season_directory_name = f"Season{match.group(1).zfill(2)}"

    if season_directory_name:
        new_season_path = season_path.parent / season_directory_name
        shutil.move(str(season_path), str(new_season_path))
        return new_season_path
    
    return None

def queue_episodes(episode_files: list, db: DatabaseManager) -> int:
    """
    Queue all episode files to the SQLite conversion database.
    Returns the number of successfully queued episodes.
    """
    if not episode_files:
        return 0
    
    queued_count = 0
    try:
        for episode_file in episode_files:
            if not db.add_job(str(episode_file)):
                logger.info(f"EPISODE_ALREADY_QUEUED: {episode_file}")
                continue
                
            queued_count += 1
            logger.info(f"QUEUED_EPISODE: {episode_file}")
    
    except Exception as e:
        logger.exception(f"ERROR_queueing_episodes: {e}")
        return queued_count
    
    logger.info(f"QUEUED_{queued_count}_EPISODES")
    return queued_count


def sanitize_tvseries_name(filename: str) -> str:
    """
    Extract clean episode name from filename.
    Format: "Series.Name.SxxExx"
    
    Strategy:
    1. Look for SxxExx pattern and truncate everything after it.
    2. Fallback: Strip common resolution/codec tags if SxxExx is missing/irregular.
    """
    name_no_ext = Path(filename).stem
    
    # Find SxxExx pattern
    match = re.search(r'(.*?s\d{2}e\d{2})', name_no_ext.lower())
    if match:
        clean_name = name_no_ext[:match.end(1)]
        return clean_name
    
    # Fallback: remove common patterns
    clean_name = re.sub(r'\.(2160p|1080p|720p|480p).*', '', name_no_ext, flags=re.IGNORECASE)
    clean_name = re.sub(r'\.(HDTV|WEB-DL|BluRay|BRRip|x264|x265|HEVC|AAC).*', '', clean_name, flags=re.IGNORECASE)
    
    return clean_name