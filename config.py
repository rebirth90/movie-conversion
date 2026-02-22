#!/usr/bin/env python3

"""
Configuration module for movie conversion system.
Centralized settings for paths, tools, and encoding parameters.
Refactored to use a dataclass for Domain-Driven Design.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Set
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class AppConfig:
    # Logging
    log_dir: Path = Path("/var/log/conversion")
    log_general_dir: Path = field(init=False)
    log_ffmpeg_dir: Path = field(init=False)

    # Tools
    ffmpeg_path: Path = Path("/usr/bin/ffmpeg")
    ffprobe_path: Path = Path("/usr/bin/ffprobe")
    mkvextract_path: Path = Path("/usr/bin/mkvextract")

    # Paths
    scratch_dir: Path = Path("/data/scratch")
    archive_dir: Path = Path("/data/archive")
    base_movies_root: Path = Path("/data/scratch/movies")
    base_tvseries_root: Path = Path("/data/scratch/tv-series")
    target_movies_dir: Path = Path("/data/archive/movies")
    target_tvseries_dir: Path = Path("/data/archive/tv-series")
    queue_file: Path = Path("/data/scratch/conversion.txt")
    db_path: Path = Path("/data/scratch/conversion_data.db")

    # TMDB API
    tmdb_read_access_token: str = field(default_factory=lambda: os.getenv("TMDB_READ_ACCESS_TOKEN", ""))

    # Email Configuration
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_ssl: bool = False
    email_smtp_username: str = "rebirth90@gmail.com"
    email_smtp_password: str = field(default_factory=lambda: os.getenv("EMAIL_SMTP_PASSWORD", ""))
    email_recipient: str = "codrut.butnariu@gmail.com"

    # Hardware Encoding Configuration
    vaapi_device: str = "/dev/dri/renderD128" # Kept for backwards compatibility but we are shifting to QSV
    qsv_device: str = "/dev/dri/renderD128"
    global_quality_default: int = 23
    qsv_denoise_level: int = 15

    # Character replacement rules for Romanian subtitles
    replace_rules: List[Tuple[str, str]] = field(default_factory=lambda: [
        ("ș", "s"), ("Ș", "S"), ("Ă", "A"), ("Î", "I"), ("î", "i"),
        ("ă", "a"), ("â", "a"), ("Â", "A"), ("Ş", "S"), ("ţ", "t"),
        ("Ț", "T"), ("ş", "s"), ("Ţ", "T"), ("ț", "t"), ("º", "s"),
        ("ª", "S"), ("ã", "a"), ("þ", "t"), ("Þ", "T"),
    ])

    # Valid extensions for files to keep during cleanup
    valid_extensions: Set[str] = field(default_factory=lambda: {'.mp4', '.srt', '.sub', '.ass', '.sup', '.idx'})

    def __post_init__(self):
        object.__setattr__(self, 'log_general_dir', self.log_dir / "general")
        object.__setattr__(self, 'log_ffmpeg_dir', self.log_dir / "ffmpeg")

    def validate(self) -> bool:
        """Validate all configuration at startup."""
        errors = []

        if not self.tmdb_read_access_token:
            errors.append("Missing TMDB_READ_ACCESS_TOKEN in environment.")

        if not self.email_smtp_password:
            errors.append("Missing EMAIL_SMTP_PASSWORD in environment.")

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_general_dir.mkdir(parents=True, exist_ok=True)
            self.log_ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create log directories: {e}")

        for path_name, path in [
            ("base_movies_root", self.base_movies_root),
            ("base_tvseries_root", self.base_tvseries_root),
        ]:
            if not path.exists():
                errors.append(f"Missing path {path_name}: {path}")

        for tool_name, tool_path in [
            ("FFmpeg", self.ffmpeg_path),
            ("FFprobe", self.ffprobe_path),
            ("MKVExtract", self.mkvextract_path),
        ]:
            if not tool_path.exists():
                errors.append(f"Missing tool {tool_name}: {tool_path}")

        if not Path(self.vaapi_device).exists() and not Path(self.qsv_device).exists():
            errors.append(f"Hardware device not found at {self.qsv_device}")

        if not 1 <= self.global_quality_default <= 51:
            errors.append(f"Invalid quality (must be 1-51): {self.global_quality_default}")

        if errors:
            for err in errors:
                logger.error(f"CONFIG_ERROR: {err}")
            return False

        logger.info("APP_CONFIG_VALIDATED_SUCCESSFULLY")
        return True
