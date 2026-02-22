"""
Domain models for the video conversion system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from enum import Enum, auto
import logging
from pymediainfo import MediaInfo
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
        """Extract stream info using pymediainfo, replacing brittle subprocess ffprobe calls."""
        try:
            media_info = MediaInfo.parse(str(filepath))
            video_tracks = [t for t in media_info.tracks if t.track_type == "Video"]
            
            if not video_tracks:
                raise MediaValidationError(f"No video tracks found in {filepath}")
                
            track = video_tracks[0]
            
            # Defensive fetching since pymediainfo attributes can be None
            width = track.width
            height = track.height
            codec_name = track.format or track.codec_id
            profile = track.format_profile or "unknown"
            # pymediainfo uses 'color_space' and 'bit_depth'
            # We map this approximately to ffprobe's 'pix_fmt' strings we used
            bit_depth = track.bit_depth or 8
            if bit_depth >= 10:
                pix_fmt = "p010le" # General 10-bit format we used to check simply for "10"
            else:
                pix_fmt = "yuv420p"

            if not width or not height:
                raise MediaValidationError(f"Missing width/height in {filepath}")

            return cls(
                width=int(width),
                height=int(height),
                codec_name=str(codec_name).lower(),
                profile=str(profile).lower(),
                pix_fmt=str(pix_fmt)
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
