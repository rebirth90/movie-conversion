#!/usr/bin/env python3

"""
TV Series utilities for detecting, parsing, and processing TV series paths.
Handles season folder renaming and episode queueing.
"""

import logging
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db_utils import DatabaseManager

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
        if season_path.resolve() == new_season_path.resolve():
            return new_season_path
            
        try:
            shutil.move(str(season_path), str(new_season_path))
        except (shutil.Error, OSError) as e:
            logger.warning(f"Cross-device move failed: {e}. Falling back to copytree/rmtree.")
            try:
                shutil.copytree(str(season_path), str(new_season_path))
                shutil.rmtree(str(season_path))
            except Exception as inner_e:
                logger.error(f"Fallback copytree failed: {inner_e}")
                return None
                
        return new_season_path
    
    return None

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