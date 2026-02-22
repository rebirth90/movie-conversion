#!/usr/bin/env python3
import logging
import urllib.request
import urllib.parse
import json
import re
from typing import Optional, Tuple
from difflib import SequenceMatcher
from config import AppConfig

logger = logging.getLogger(__name__)

def search_movie_tmdb(config: AppConfig, raw_filename: str, query: str, year: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Search for a movie on TMDB using the Read Access Token.
    Returns the best matching title from the top 5 results based on difflib scoring.
    """
    if not config.tmdb_read_access_token:
        logger.warning("tmdb_read_access_token not set in config.")
        return None

    try:
        # --- Query Cleaning ---
        # Raw filenames often contain noise like [Group], (1080p), etc. that confuse the API.
        
        # 1. Remove content in brackets [] and ()
        clean_query = re.sub(r'\[.*?\]', '', query)
        clean_query = re.sub(r'\(.*?\)', '', clean_query)
        
        # 2. Replace separators with spaces
        clean_query = re.sub(r'[\._]', ' ', clean_query)
        
        # 3. Strip resolution and other common tags from the end
        clean_query = re.sub(r'(1080|720|2160)p?.*', '', clean_query, flags=re.IGNORECASE)
        
        clean_query = clean_query.strip()
        
        encoded_query = urllib.parse.quote(clean_query)
        url = f"https://api.themoviedb.org/3/search/movie?query={encoded_query}&include_adult=false&language=en-US&page=1"
        
        if year:
            url += f"&year={year}"
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {config.tmdb_read_access_token}"
        }

        # Execute Request
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                logger.error(f"TMDB API returned status {response.status}")
                return None
            
            data = json.loads(response.read().decode('utf-8'))
            results = data.get('results', [])
            
            if not results:
                logger.info(f"No TMDB results found for: {clean_query}")
                return None
            
            top_results = results[:5]
            best_match = None
            highest_score = 0.0
            
            for movie in top_results:
                title = movie.get('title')
                release_date = movie.get('release_date', '')
                year_found = release_date[:4] if len(release_date) >= 4 else ""
                
                compare_str = f"{title} {year_found}".strip()
                score = SequenceMatcher(None, compare_str.lower(), raw_filename.lower()).ratio()
                
                if score > highest_score:
                    highest_score = score
                    best_match = (title, year_found)
                    
            if best_match:
                logger.info(f"TMDB Best Match: {best_match[0]} ({best_match[1]}) - Score: {highest_score:.2f}")
                return best_match
            
            return None

    except Exception as e:
        logger.error(f"Error querying TMDB: {e}")
        return None
