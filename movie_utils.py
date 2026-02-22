#!/usr/bin/env python3
import logging
import re
from typing import Optional
from pathlib import Path
from pathlib import Path
from config import AppConfig
from metadata_utils import search_movie_tmdb

logger = logging.getLogger(__name__)

def cleanup_movie_directory(directory: Path, config: AppConfig) -> None:
    """
    Clean up movie directory after conversion.
    
    Rule:
    - Keep only essential files defined in `config.VALID_EXTENSIONS` (.mp4, .srt, etc.)
    - Delete everything else (nfo, txt, jpg, samples, etc.)
    
    Args:
        directory (Path): The directory to clean.
    """
    logger.info("="*80)
    logger.info("CLEANUP: Removing non-essential files from movie directory")
    logger.info("="*80)

    deleted_count = 0
    kept_count = 0

    try:
        for item in directory.iterdir():
            if not item.is_file():
                continue
                
            if item.suffix.lower() in config.valid_extensions:
                logger.info(f"KEEPING: {item.name}")
                kept_count += 1
            else:
                logger.info(f"DELETING: {item.name}")
                try:
                    item.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {item.name}: {e}")

        logger.info(f"CLEANUP_COMPLETE: Kept {kept_count} files, deleted {deleted_count} files")

    except Exception as e:
        logger.error(f"ERROR during cleanup: {e}")



def sanitize_movie_name(filename: str, config: AppConfig) -> str:
    """
    Extract clean movie name from messy filename.
    Target Format: "Movie.Name.Year"
    
    Strategy:
    1. TMDB Lookup (Primary):
       - Cleans the filename of release tags.
       - Queries TMDB API for exact match.
       - Returns "Title.Year" or "Title" from verified metadata.
       
    2. Regex Extraction (Fallback):
       - Used if TMDB fails or token is missing.
       - Looks for Year (19xx/20xx) or common release tags (1080p, etc.) to truncate the string.
       - Cleans up dots and special characters.
    """
    
    # --- STRATEGY 1: TMDB Lookup ---
    
    # 0. Strip known file extensions to prevent "Movie.mkv" becoming "Movie mkv" query
    stem = filename
    # Broad list of video extensions to strip
    extensions_to_strip = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.divx', '.xvid', '.wmv'}
    for ext in extensions_to_strip:
        if filename.lower().endswith(ext):
            stem = filename[:-len(ext)]
            break
            
    # 1. Remove content in brackets [] and ()
    clean_stem = re.sub(r'\[.*?\]', '', stem)
    clean_stem = re.sub(r'\(.*?\)', '', clean_stem)
    
    # 2. Extract Year and Resolution to define the query
    query_year = None
    query_candidate = clean_stem

    # Try to find year
    year_match = re.search(r'(19|20)\d{2}', clean_stem)
    if year_match:
        query_year = year_match.group(0)
        # Use text BEFORE the year as the title query
        # But ensure we don't have empty string if year is at start
        possible_title = clean_stem[:year_match.start()]
        if possible_title.strip(r' ._-'):
             query_candidate = possible_title
        else:
             # If title is empty (e.g. "2001.Space.Odyssey"), maybe year is part of title? 
             # Or just use the whole thing.
             pass 
    else:
        # No year, look for resolution to truncate
        res_match = re.search(r'((?:1080|720|2160)p)', clean_stem, re.IGNORECASE)
        if res_match:
             query_candidate = clean_stem[:res_match.start()]

    # Final cleanup
    # Replace dots and underscores with spaces
    query_candidate = re.sub(r'[\._]', ' ', query_candidate).strip()
    
    if query_candidate:
        logger.info(f"Querying TMDB: '{query_candidate}' (Year: {query_year})")
        tmdb_result = search_movie_tmdb(config, filename, query_candidate, year=query_year)
        
        if tmdb_result:
            title, year_found = tmdb_result
            safe_title = re.sub(r'[^a-zA-Z0-9 ]+', '', title).replace(' ', '.')
            if year_found:
                logger.info(f"TMDB Success: {safe_title}.{year_found}")
                return f"{safe_title}.{year_found}"
            else:
                 logger.info(f"TMDB Success (no year): {safe_title}")
                 return safe_title
        else:
             logger.info("TMDB did not return a valid result. Falling back to regex.")

    # --- STRATEGY 2: Fallback Regex ---
    # 1. Try finding a year first
    year_match = re.search(r'(19|20)\d{2}', filename)
    if year_match:
        year = year_match.group(0)
        prefix = filename[:year_match.start()]
        prefix = re.sub(r'[._-]+$', '', prefix)
        prefix = re.sub(r'\.+', '.', prefix)
        prefix = re.sub(r'[^a-zA-Z0-9.]+', '.', prefix)
        prefix = prefix.rstrip('.')
        result = f"{prefix}.{year}"
    else:
        # 2. If no year, look for resolution/quality tags to stop at
        flags_pattern = r'((?:1080|720|2160|480|576)[pi]|4k|blu-?ray|web-?dl|web-?rip|hdtv|flac|aac|x264|x265|hevc|avc|divx|xvid)'
        
        split_match = re.search(flags_pattern, filename, re.IGNORECASE)
        
        if split_match:
             prefix = filename[:split_match.start()]
        else:
             prefix = filename

        result = re.sub(r'[^a-zA-Z0-9.]+', '.', prefix)
        result = re.sub(r'\.+', '.', result)
        result = result.rstrip('.')
    
    return result


def get_largest_movie_file(folder: Path) -> Optional[Path]:
    """
    Find largest movie file in folder.
    
    Args:
        folder (Path): Directory to search (or file path).
        
    Returns:
        Optional[Path]: Path to the largest video file (.mkv, .mp4, etc.), or None.
    """
    # If path is a file, it IS the movie file
    if folder.is_file():
        logger.info(f"File path detected, returning: {folder.name}")
        return folder
    
    movie_files = (list(folder.glob("*.mkv")) + list(folder.glob("*.mp4")) +
                   list(folder.glob("*.avi")) + list(folder.glob("*.mov")))
    
    if not movie_files:
        logger.warning(f"No movie files found in {folder}")
        return None
    
    # Sort by file size (largest first)
    largest_file = max(movie_files, key=lambda f: f.stat().st_size)
    logger.info(f"Found {len(movie_files)} movie file(s), selected largest: {largest_file.name}")
    
    return largest_file