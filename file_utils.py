#!/usr/bin/env python3
import logging
from pathlib import Path
from config import AppConfig

logger = logging.getLogger(__name__)







import shutil
import time

def linux_mv(source: Path, dest: Path) -> None:
    """Robust cross-device file move."""
    try:
        shutil.move(str(source), str(dest))
    except (PermissionError, OSError) as e:
        logger.warning(f"shutil.move failed with {e}, falling back to copy+delete for {source}")
        time.sleep(1)
        shutil.copy2(str(source), str(dest))
        source.unlink(missing_ok=True)

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




def should_process_path(linux_path: Path) -> bool:
    """
    Reject paths that start with /share/seeding.
    """
    path_str = str(linux_path).strip()
    if path_str.startswith("/share/seeding"):
        logger.warning(f"PATH_REJECTED (seeding path): {linux_path}")
        return False
    return True
