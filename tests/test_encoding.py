import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from encoding_utils import IntelQSVStrategy
from models import VideoStreamInfo
from config import AppConfig

def test_qsv_1080p_command(dummy_media_item, mock_config):
    dummy_media_item.stream_info = VideoStreamInfo(
        width=1920,
        height=1080,
        codec_name="hevc",
        profile="main10",
        pix_fmt="yuv420p10le"
    )
    
    target_path = Path("/archive/movies/dummy/dummy.mkv")
    
    with patch('encoding_utils.get_audio_streams', return_value=[]):
        strategy = IntelQSVStrategy(mock_config)
        cmd_builder = strategy.build_command(dummy_media_item, target_path, bf=3, lad=1, async_depth=4)
        cmd = cmd_builder.build()
        
    cmd_str = " ".join(cmd)
    
    # Assert purely hardware configuration
    assert "-hwaccel qsv" in cmd_str
    assert "vpp_qsv" in cmd_str
    assert "-c:v hevc_qsv" in cmd_str

def test_qsv_4k_widescreen_padding(dummy_media_item, mock_config):
    dummy_media_item.stream_info = VideoStreamInfo(
        width=3840,
        height=1600,
        codec_name="hevc",
        profile="main10",
        pix_fmt="yuv420p10le"
    )
    
    target_path = Path("/archive/movies/dummy/dummy.mkv")
    
    with patch('encoding_utils.get_audio_streams', return_value=[]):
        strategy = IntelQSVStrategy(mock_config)
        cmd_builder = strategy.build_command(dummy_media_item, target_path, bf=3, lad=1, async_depth=4)
        cmd = cmd_builder.build()
        
    cmd_str = " ".join(cmd)
    
    # Assert fallback to software padding due to non-standard sizing
    assert "vpp_qsv" not in cmd_str
    assert "pad=1920:1080:(ow-iw)/2:(oh-ih)/2" in cmd_str
    assert "-threads 6" in cmd_str  # Hybrid mode fallback indicates software decode

def test_audio_downmix(dummy_media_item, mock_config):
    # Testing Audio track extraction mapping logic
    target_path = Path("/archive/movies/dummy/dummy.mkv")
    
    mock_audio_tracks = [
        {"index": 1, "channels": 6, "lang": "eng"},  # 5.1 Surround
        {"index": 2, "channels": 2, "lang": "ro"}    # Stereo
    ]
    
    with patch('encoding_utils.get_audio_streams', return_value=mock_audio_tracks):
        strategy = IntelQSVStrategy(mock_config)
        cmd_builder = strategy.build_command(dummy_media_item, target_path, bf=3, lad=1, async_depth=4)
        cmd = cmd_builder.build()
        
    cmd_str = " ".join(cmd)
    
    # Assert both tracks are mapped
    assert "-map 0:1" in cmd_str
    assert "-map 0:2" in cmd_str
    
    # Assert downmixing to stereo is applied universally
    assert "-ac:0 2" in cmd_str
    assert "-af:0 aresample=ochl=stereo" in cmd_str
    assert "-ac:1 2" in cmd_str
    assert "-af:1 aresample=ochl=stereo" in cmd_str
    
    # Assert bitrate allocations
    assert "-b:a:0 256k" in cmd_str  # 6 channel -> 2
    assert "-b:a:1 192k" in cmd_str  # 2 channel -> 2
    
    # Assert language tags
    assert "language=eng" in cmd_str
    assert "language=ro" in cmd_str
