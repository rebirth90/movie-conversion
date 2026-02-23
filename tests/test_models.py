import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from models import MediaFactory, MediaType, Movie, TVEpisode, VideoStreamInfo

def test_media_factory_movie(mock_config):
    movie_path = mock_config.base_movies_root / "Avatar.mkv"
    movie_path.touch()
    
    with patch('models.VideoStreamInfo.from_file'):
        item = MediaFactory.create(MediaType.MOVIE, movie_path, mock_config)
        assert isinstance(item, Movie)

def test_media_factory_tv(mock_config):
    tv_path = mock_config.base_tvseries_root / "Breaking.Bad.S01E01.mkv"
    tv_path.touch()
    
    with patch('models.VideoStreamInfo.from_file'):
        item = MediaFactory.create(MediaType.TVSERIES, tv_path, mock_config)
        assert isinstance(item, TVEpisode)

def test_clean_name(mock_config):
    tv_path = mock_config.base_tvseries_root / "Breaking.Bad.S01E01.1080p.mkv"
    tv_path.touch()
    
    with patch('models.VideoStreamInfo.from_file'):
        item = MediaFactory.create(MediaType.TVSERIES, tv_path, mock_config)
        assert item.clean_name() == "Breaking.Bad.S01E01"

@patch('subprocess.run')
def test_video_stream_info_parsing(mock_run, mock_config):
    dummy_json = '''
    {
        "streams": [
            {
                "codec_name": "hevc",
                "profile": "Main 10",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p10le"
            }
        ]
    }
    '''
    mock_proc = MagicMock()
    mock_proc.stdout = dummy_json
    mock_run.return_value = mock_proc
    
    file_path = mock_config.base_movies_root / "Avatar.mkv"
    file_path.touch()
    
    info = VideoStreamInfo.from_file(file_path, mock_config)
    
    assert info.width == 1920
    assert info.height == 1080
    assert info.codec_name == "hevc"
    assert info.profile == "main 10"  # Note it's converted to lower case inside
    assert info.pix_fmt == "yuv420p10le"
