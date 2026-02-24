"""
Domain models for the video conversion system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from enum import Enum, auto
import logging
import subprocess
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db_utils import DatabaseManager
    from encoding_utils import EncoderStrategy
    import threading

from exceptions import MediaValidationError
from config import AppConfig
from tvseries_utils import sanitize_tvseries_name, clean_season_folder_name
from movie_utils import sanitize_movie_name, get_largest_movie_file, cleanup_movie_directory
from file_utils import linux_mv

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class VideoStreamInfo:
    width: int
    height: int
    codec_name: str
    profile: str
    pix_fmt: str
    master_display: str = ""
    max_cll: str = ""
    
    @classmethod
    def from_file(cls, filepath: Path, config: 'AppConfig') -> 'VideoStreamInfo':
        """Extract stream info using native ffprobe json."""
        try:
            result = subprocess.run(
                [
                    str(config.ffprobe_path),
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name,profile,width,height,pix_fmt:stream_side_data=red_x,red_y,green_x,green_y,blue_x,blue_y,white_point_x,white_point_y,min_luminance,max_luminance,max_content,max_average",
                    "-of",
                    "json",
                    str(filepath),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            
            probe_data = json.loads(result.stdout)
            streams = probe_data.get("streams", [])
            
            if not streams:
                raise MediaValidationError(f"No video tracks found in {filepath}")
                
            track = streams[0]
            
            width = track.get("width")
            height = track.get("height")
            codec_name = track.get("codec_name", "unknown")
            profile = track.get("profile", "unknown")
            pix_fmt = track.get("pix_fmt", "unknown")

            if width is None or height is None:
                raise MediaValidationError(f"Missing width/height in {filepath}")
                
            master_display = ""
            max_cll = ""
            for side in track.get("side_data_list", []):
                if 'red_x' in side and 'green_x' in side and 'blue_x' in side and 'white_point_x' in side:
                    try:
                        rx = side['red_x'].split('/')[0]
                        ry = side['red_y'].split('/')[0]
                        gx = side['green_x'].split('/')[0]
                        gy = side['green_y'].split('/')[0]
                        bx = side['blue_x'].split('/')[0]
                        by = side['blue_y'].split('/')[0]
                        wpx = side['white_point_x'].split('/')[0]
                        wpy = side['white_point_y'].split('/')[0]
                        minL = side['min_luminance'].split('/')[0]
                        maxL = side['max_luminance'].split('/')[0]
                        master_display = f"G({gx},{gy})B({bx},{by})R({rx},{ry})WP({wpx},{wpy})L({maxL},{minL})"
                    except Exception as e:
                        logger.warning(f"Failed to parse master_display side data: {e}", exc_info=True)
                        pass
                if 'max_content' in side and 'max_average' in side:
                    max_cll = f"{side['max_content']},{side['max_average']}"

            return cls(
                width=int(width),
                height=int(height),
                codec_name=str(codec_name).lower(),
                profile=str(profile).lower(),
                pix_fmt=str(pix_fmt).lower(),
                master_display=master_display,
                max_cll=max_cll
            )
        except Exception as e:
            if isinstance(e, MediaValidationError):
                raise
            raise MediaValidationError(f"Failed to parse media info: {e}")

class MediaType(Enum):
    """Enumeration of processable media entity types."""
    MOVIE = auto()
    TVSERIES = auto()
    UNKNOWN = auto()

class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"

@dataclass(frozen=True)
class EncodingTier:
    bf: int
    lad: int
    async_depth: int
    desc: str

@dataclass
class JobContext:
    config: AppConfig
    db: 'DatabaseManager'
    media_item: 'MediaItem'
    strategy: 'EncoderStrategy'
    job_id: int
    shutdown_event: Optional['threading.Event'] = None


class MediaItem(ABC):
    """Abstract base class for all processable media."""
    def __init__(self, source_path: Path, config: AppConfig, original_job_path: Optional[Path] = None):
        self.source_path = source_path
        self.config = config
        self.original_job_path = original_job_path or source_path
        self.stream_info: Optional[VideoStreamInfo] = None
        
        # Load stream info immediately to validate
        if self.source_path.is_file():
             self.stream_info = VideoStreamInfo.from_file(self.source_path, self.config)

    @abstractmethod
    def target_directory(self) -> Path:
        """Returns the ultimate destination directory config root."""
        pass
        
    @abstractmethod
    def clean_name(self) -> str:
        """Returns the sanitized/matched name of the item."""
        pass

    @abstractmethod
    def compute_final_directory(self) -> Path:
        """Computes the exact final destination directory for the artifacts."""
        pass

    @abstractmethod
    def cleanup_source_directory(self, logger: logging.Logger, final_dir: Path) -> None:
        """Deletes original artifacts and directories if safe to do so. Moves any kept ancillary files to final_dir."""
        pass


class Movie(MediaItem):
    """Represents a discrete Movie entity."""
    
    def target_directory(self) -> Path:
        return self.config.target_movies_dir
        
    def clean_name(self) -> str:
        """Uses domain utility to sanitize the name."""
        try:
            return sanitize_movie_name(self.source_path.stem, self.config)
        except Exception as e:
            logger.warning(f"Error sanitizing movie name {self.source_path.stem}: {e}", exc_info=True)
            return self.source_path.stem

    def compute_final_directory(self) -> Path:
        return self.config.target_movies_dir / self.clean_name()

    def cleanup_source_directory(self, logger: logging.Logger, final_dir: Path) -> None:
        if not self.source_path.exists():
            return
            
        self.source_path.unlink(missing_ok=True)
        
        parent_dir = self.source_path.parent
        if parent_dir.resolve() != self.config.base_movies_root.resolve():
            cleanup_movie_directory(parent_dir, self.config)
            
            # Move remaining ancillary files to final_dir to prevent orphans
            if parent_dir.exists() and parent_dir.is_dir():
                for item in parent_dir.iterdir():
                    if item.is_file():
                        target_file = final_dir / item.name
                        if target_file.resolve() != item.resolve():
                            logger.info(f"Moving ancillary file: {item.name} -> {final_dir.name}")
                            linux_mv(item, target_file)

                # Now remove if empty
                try:
                    if not any(parent_dir.iterdir()):
                        logger.info(f"Directory empty, removing: {parent_dir}")
                        parent_dir.rmdir()
                except OSError as e:
                    logger.warning(f"Could not remove movie directory {parent_dir}: {e}", exc_info=True)


class TVEpisode(MediaItem):
    """Represents a discrete TV Episode entity."""
    
    def target_directory(self) -> Path:
        return self.config.target_tvseries_dir
        
    def clean_name(self) -> str:
        """Uses domain utility to sanitize the name."""
        try:
            return sanitize_tvseries_name(self.source_path.name)
        except Exception as e:
            logger.warning(f"Error sanitizing TV episode {self.source_path.name}: {e}", exc_info=True)
            return self.source_path.stem

    def compute_final_directory(self) -> Path:
        parent_dir = self.source_path.parent
        # Determine clean season name without moving the source dir
        season_directory_lower = parent_dir.name.lower()
        season_directory_name = parent_dir.name
        
        import re
        match = re.search(r's(\d{2})', season_directory_lower)
        if match:
            season_directory_name = f"Season{match.group(1)}"
        else:
            match = re.search(r'season[\s._-]*(\d+)', season_directory_lower)
            if match:
                season_directory_name = f"Season{match.group(1).zfill(2)}"
        
        rel_parent = parent_dir.parent.relative_to(self.config.base_tvseries_root)
        return self.config.target_tvseries_dir / rel_parent / season_directory_name

    def cleanup_source_directory(self, logger: logging.Logger, final_dir: Path) -> None:
        if not self.source_path.exists():
            return
            
        self.source_path.unlink(missing_ok=True)
        
        parent_dir = self.source_path.parent
        is_base_tv_root = parent_dir.resolve() == self.config.base_tvseries_root.resolve()
        
        if parent_dir.exists() and parent_dir.is_dir() and not is_base_tv_root:
            try:
                if not any(parent_dir.iterdir()):
                    logger.info(f"Directory empty, removing: {parent_dir}")
                    parent_dir.rmdir()
            except OSError as e:
                logger.warning(f"Could not remove season directory {parent_dir}: {e}", exc_info=True)
        
        grandparent_dir = parent_dir.parent
        is_grandparent_base = grandparent_dir.resolve() == self.config.base_tvseries_root.resolve()
        
        if grandparent_dir.exists() and grandparent_dir.is_dir() and not is_grandparent_base:
            try:
                if not any(grandparent_dir.iterdir()):
                    logger.info(f"Directory empty, removing: {grandparent_dir}")
                    grandparent_dir.rmdir()
            except OSError as e:
                logger.warning(f"Could not remove series directory {grandparent_dir}: {e}", exc_info=True)

class MediaFactory:
    """Factory for producing appropriate MediaItem domain models based on MediaType."""
    @staticmethod
    def create(media_type: MediaType, source_path: Path, config: AppConfig) -> list['MediaItem']:
        if media_type == MediaType.MOVIE:
            if source_path.is_dir():
                actual_file = get_largest_movie_file(source_path)
                if not actual_file:
                    raise ValueError(f"No valid video file found in directory: {source_path}")
                return [Movie(source_path=actual_file, config=config, original_job_path=source_path)]
            return [Movie(source_path=source_path, config=config, original_job_path=source_path)]
        elif media_type == MediaType.TVSERIES:
            if source_path.is_dir():
                episodes = []
                for ext in ('.mkv', '.mp4', '.avi', '.m4v', '.MKV', '.MP4', '.AVI', '.M4V'):
                    episodes.extend(source_path.rglob(f"*{ext}"))
                episodes.sort()
                return [TVEpisode(source_path=ep, config=config, original_job_path=source_path) for ep in episodes]
            return [TVEpisode(source_path=source_path, config=config, original_job_path=source_path)]
        else:
            logger.error(f"Cannot instantiate MediaItem for UNKNOWN media type at {source_path}")
            return []
