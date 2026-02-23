import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from encoding_utils import IntelQSVStrategy
from config import AppConfig
from models import MediaFactory, MediaType, VideoStreamInfo

class TestEncodingUtils(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()

    @patch('encoding_utils.subprocess.run')
    def test_build_qsv_command(self, mock_run):
        """Simulate a standard movie encoding pipeline using the QSV configuration."""
        
        movie_path = Path("/movies/Avatar/Avatar.mkv")
        media_item = MediaFactory.create(MediaType.MOVIE, movie_path, self.config)
        
        # Inject the mock stream data the Pipeline would usually populate
        with patch('models.VideoStreamInfo.from_file') as mock_from_file:
            media_item.stream_info = VideoStreamInfo(
                width=1920,
                height=1080,
                codec_name="h264",
                profile="high",
                pix_fmt="yuv420p10le"
            )
        target_path = Path("/archive/movies/Avatar/Avatar.mkv")
        
        with patch('encoding_utils.get_audio_streams', return_value=[{'index': 1, 'channels': 2, 'lang': 'eng'}, {'index': 2, 'channels': 6, 'lang': 'ro'}]):
            strategy = IntelQSVStrategy(self.config)
            cmd_builder = strategy.build_command(media_item, target_path, bf=3, lad=1, async_depth=4)
            cmd = cmd_builder.build()
        
        # The resulting command list should string match core FFmpeg arguments
        cmd_str = " ".join(cmd)
        self.assertIn("-hwaccel qsv", cmd_str)
        self.assertIn("-c:v hevc_qsv", cmd_str)
        self.assertIn("Avatar.mkv", cmd_str)
        # Verify streams are mapped (usually 0:v:0 and 0:a:0 etc based on the audio getter)
        self.assertIn("-map 0:v:0", cmd_str)

if __name__ == '__main__':
    unittest.main()
