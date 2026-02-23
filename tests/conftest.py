import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from config import AppConfig
from db_utils import DatabaseManager
from models import MediaFactory, MediaType, VideoStreamInfo

@pytest.fixture
def mock_config(tmp_path):
    # Setup safe temporary paths
    (tmp_path / "scratch" / "movies").mkdir(parents=True)
    (tmp_path / "scratch" / "tv-series").mkdir(parents=True)
    (tmp_path / "archive" / "movies").mkdir(parents=True)
    (tmp_path / "archive" / "tv-series").mkdir(parents=True)
    
    # Touch dummy tool binaries
    tools = [
        tmp_path / "ffmpeg",
        tmp_path / "ffprobe",
        tmp_path / "mkvextract"
    ]
    for tool in tools:
        tool.touch()
        tool.chmod(0o755)

    qsv_dev = tmp_path / "renderD128"
    qsv_dev.touch()

    db_path = tmp_path / "scratch" / "conversion_data.db"
    queue_file = tmp_path / "scratch" / "conversion.txt"

    return AppConfig(
        log_dir=tmp_path / "log",
        ffmpeg_path=tools[0],
        ffprobe_path=tools[1],
        mkvextract_path=tools[2],
        scratch_dir=tmp_path / "scratch",
        archive_dir=tmp_path / "archive",
        base_movies_root=tmp_path / "scratch" / "movies",
        base_tvseries_root=tmp_path / "scratch" / "tv-series",
        target_movies_dir=tmp_path / "archive" / "movies",
        target_tvseries_dir=tmp_path / "archive" / "tv-series",
        queue_file=queue_file,
        db_path=db_path,
        tmdb_read_access_token="dummy_token",
        email_smtp_username="dummy_user",
        email_smtp_password="dummy_password",
        email_recipient="dummy@example.com",
        qsv_device=str(qsv_dev)
    )

@pytest.fixture
def in_memory_db(tmp_path):
    # DatabaseManager creates its DB natively. We use a temporary file path so the tables persist across connection threads.
    db_file = tmp_path / "test.db"
    return DatabaseManager(db_file)

@pytest.fixture
def dummy_media_item(mock_config):
    movie_path = mock_config.base_movies_root / "Avatar.2009.mkv"
    movie_path.touch()
    
    with patch('models.VideoStreamInfo.from_file') as mock_from_file:
        mock_from_file.return_value = VideoStreamInfo(
            width=1920,
            height=1080,
            codec_name="hevc",
            profile="main10",
            pix_fmt="yuv420p10le"
        )
        item = MediaFactory.create(MediaType.MOVIE, movie_path, mock_config)
        yield item
