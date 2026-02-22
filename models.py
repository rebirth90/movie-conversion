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

from exceptions import MediaValidationError
from config import AppConfig
from tvseries_utils import sanitize_tvseries_name
from movie_utils import sanitize_movie_name

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class VideoStreamInfo:
    width: int
    height: int
    codec_name: str
    profile: str
    pix_fmt: str
    
    @classmethod
    def from_file(cls, filepath: Path) -> 'VideoStreamInfo':
        """Extract stream info using native ffprobe json."""
        from config import AppConfig
        config = AppConfig()
        try:
            result = subprocess.run(
                [
                    str(config.ffprobe_path),
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name,profile,width,height,pix_fmt",
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

            if not width or not height:
                raise MediaValidationError(f"Missing width/height in {filepath}")

            return cls(
                width=int(width),
                height=int(height),
                codec_name=str(codec_name).lower(),
                profile=str(profile).lower(),
                pix_fmt=str(pix_fmt).lower()
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


class MediaItem(ABC):
    """Abstract base class for all processable media."""
    def __init__(self, source_path: Path, config: AppConfig):
        self.source_path = source_path
        self.config = config
        self.stream_info: Optional[VideoStreamInfo] = None
        
        # Load stream info immediately to validate
        if self.source_path.is_file():
             self.stream_info = VideoStreamInfo.from_file(self.source_path)

    @abstractmethod
    def target_directory(self) -> Path:
        """Returns the ultimate destination directory config root."""
        pass
        
    @abstractmethod
    def clean_name(self) -> str:
        """Returns the sanitized/matched name of the item."""
        pass


class Movie(MediaItem):
    """Represents a discrete Movie entity."""
    
    def target_directory(self) -> Path:
        return self.config.target_movies_dir
        
    def clean_name(self) -> str:
        """Uses domain utility to sanitize the name."""
        try:
            return sanitize_movie_name(self.source_path.stem)
        except Exception as e:
            logger.warning(f"Error sanitizing movie name {self.source_path.stem}: {e}")
            return self.source_path.stem


class TVEpisode(MediaItem):
    """Represents a discrete TV Episode entity."""
    
    def target_directory(self) -> Path:
        return self.config.target_tvseries_dir
        
    def clean_name(self) -> str:
        """Uses domain utility to sanitize the name."""
        try:
            return sanitize_tvseries_name(self.source_path.name)
        except Exception as e:
            logger.warning(f"Error sanitizing TV episode {self.source_path.name}: {e}")
            return self.source_path.stem

class MediaFactory:
    """Factory for producing appropriate MediaItem domain models based on MediaType."""
    @staticmethod
    def create(media_type: MediaType, source_path: Path, config: AppConfig) -> Optional[MediaItem]:
        match media_type:
            case MediaType.MOVIE:
                return Movie(source_path, config)
            case MediaType.TVSERIES:
                return TVEpisode(source_path, config)
            case _:
                logger.error(f"Cannot instantiate MediaItem for UNKNOWN media type at {source_path}")
                return None
