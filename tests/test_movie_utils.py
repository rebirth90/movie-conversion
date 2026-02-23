import unittest
from pathlib import Path
from movie_utils import sanitize_movie_name, get_largest_movie_file
from unittest.mock import patch, MagicMock
from config import AppConfig

class TestMovieUtils(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()
        
    @patch('movie_utils.search_movie_tmdb')
    def test_sanitize_movie_name_tmdb(self, mock_search):
        mock_search.return_value = ("The Matrix", "1999")
        clean = sanitize_movie_name("The.Matrix.1999.1080p.BluRay.mkv", self.config)
        self.assertEqual(clean, "The.Matrix.1999")
        
    @patch('movie_utils.search_movie_tmdb')
    def test_sanitize_movie_name_fallback_regex(self, mock_search):
        mock_search.return_value = None
        clean = sanitize_movie_name("The.Matrix.1999.1080p.BluRay.mkv", self.config)
        self.assertEqual(clean, "The.Matrix.1999")
        
        clean2 = sanitize_movie_name("Unknown.Movie.1080p.x264", self.config)
        self.assertEqual(clean2, "Unknown.Movie")

    @patch.object(Path, 'is_file', return_value=False)
    @patch.object(Path, 'glob')
    def test_get_largest_movie_file(self, mock_glob, mock_is_file):
        folder = Path("/movies/Matrix")
        
        # Mocking files with stat logic
        f1 = MagicMock(spec=Path)
        f1.name = "small.mp4"
        f1.stat.return_value.st_size = 100
        
        f2 = MagicMock(spec=Path)
        f2.name = "large.mkv"
        f2.stat.return_value.st_size = 5000
        
        # Provide files for glob
        def mock_glob_side_effect(pattern):
            if pattern == '*.mkv':
                return [f2]
            if pattern == '*.mp4':
                return [f1]
            return []
            
        mock_glob.side_effect = mock_glob_side_effect
        
        largest = get_largest_movie_file(folder)
        self.assertIsNotNone(largest)
        self.assertEqual(largest.name, "large.mkv")

if __name__ == '__main__':
    unittest.main()
