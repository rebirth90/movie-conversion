#!/usr/bin/env python3
import logging
from pathlib import Path
from config import AppConfig

logger = logging.getLogger(__name__)







def validate_tool_paths(config: AppConfig) -> bool:
    """Verify all required tools are accessible."""
    
    tools = {
        "FFmpeg": config.ffmpeg_path,
        "FFprobe": config.ffprobe_path,
        "MKVExtract": config.mkvextract_path,
    }
    
    logger.info("VALIDATING_tools")
    missing_tools = []
    
    for tool_name, tool_path in tools.items():
        if not tool_path.exists():
            missing_tools.append(f"{tool_name}: {tool_path}")
            logger.error("MISSING: %s", tool_name)
        else:
            logger.info("FOUND: %s", tool_name)
    
    if missing_tools:
        logger.error("MISSING_REQUIRED_TOOLS")
        return False
    
    logger.info("All_tools_accessible")
    return True




def should_process_path(linux_path: Path, config: AppConfig) -> bool:
    """
    Validate path is within BASE_MOVIES_ROOT or BASE_TVSERIES_ROOT.
    Reject paths that start with /share/seeding.
    """
    path_str = str(linux_path).strip()
    
    # Reject seeding paths explicitly
    if path_str.startswith("/share/seeding"):
        logger.warning("PATH_REJECTED (seeding path): %s", linux_path)
        return False
    
    # Check if it's a TV series path
    if path_str.startswith(str(config.base_tvseries_root)):
        logger.info("PATH_ACCEPTED (TV_SERIES): %s", linux_path)
        return True
    
    # Check if it's a movie path
    if path_str.startswith(str(config.base_movies_root)):
        logger.info("PATH_ACCEPTED (MOVIE): %s", linux_path)
        return True
    
    logger.warning("PATH_REJECTED (not in movies or tv-series): %s", linux_path)
    return False
