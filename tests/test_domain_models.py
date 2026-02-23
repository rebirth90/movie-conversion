import unittest
from pathlib import Path
from models import MediaFactory, MediaType, Movie, TVEpisode, VideoStreamInfo
from config import AppConfig
from exceptions import MediaValidationError
from unittest.mock import patch, MagicMock

class TestDomainModels(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()

    @patch('models.VideoStreamInfo.from_file')
    def test_media_factory_movie(self, mock_stream_info):
        mock_info = VideoStreamInfo(width=1920, height=1080, codec_name='h264', profile='main', pix_fmt='yuv420p')
        mock_stream_info.return_value = mock_info
        
        test_path = Path("/data/scratch/movies/The.Matrix.1999.1080p/The.Matrix.mkv")
        media_item = MediaFactory.create(MediaType.MOVIE, test_path, self.config)
        
        self.assertIsInstance(media_item, Movie)
        self.assertEqual(media_item.clean_name(), "The Matrix 1999 1080p")
        self.assertEqual(media_item.stream_info.width, 1920)

    @patch('models.VideoStreamInfo.from_file')
    def test_media_factory_tvseries(self, mock_stream_info):
        mock_info = VideoStreamInfo(width=1280, height=720, codec_name='h264', profile='main', pix_fmt='yuv420p')
        mock_stream_info.return_value = mock_info
        
        test_path = Path("/data/scratch/tv-series/Breaking.Bad/Season.01/Breaking.Bad.S01E01.mkv")
        media_item = MediaFactory.create(MediaType.TVSERIES, test_path, self.config)
        
        self.assertIsInstance(media_item, TVEpisode)
        self.assertEqual(media_item.clean_name(), "Breaking Bad S01E01")
        
    def test_media_factory_unknown(self):
        test_path = Path("/data/scratch/random.txt")
        with self.assertRaises(MediaValidationError):
            MediaFactory.create(MediaType.UNKNOWN, test_path, self.config)

if __name__ == '__main__':
    unittest.main()
