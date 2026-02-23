import unittest
from pathlib import Path
from tvseries_utils import sanitize_tvseries_name, clean_season_folder_name
from unittest.mock import patch, MagicMock

class TestTVSeriesUtils(unittest.TestCase):
    def test_sanitize_tvseries_name(self):
        # Should strip accurately up to SxxExx
        self.assertEqual(sanitize_tvseries_name("Show.Name.S01E05.1080p.mkv"), "Show.Name.S01E05")
        self.assertEqual(sanitize_tvseries_name("Show Name s02e10 WEBRip"), "Show Name s02e10")
        
        # Fallback (no SxxExx detected)
        self.assertEqual(sanitize_tvseries_name("Regular.Show.1080p.x264"), "Regular.Show")
        
    @patch('shutil.move')
    def test_clean_season_folder_name(self, mock_move):
        path = Path("/tv/Show/Season 1")
        new_path = clean_season_folder_name(path)
        self.assertEqual(new_path.name, "Season01")
        mock_move.assert_called_once_with(str(path), str(new_path))
        
        path2 = Path("/tv/Show/S02")
        new_path2 = clean_season_folder_name(path2)
        self.assertEqual(new_path2.name, "Season02")
        
        # Already clean
        path3 = Path("/tv/Show/Season03")
        new_path3 = clean_season_folder_name(path3)
        self.assertEqual(new_path3.name, "Season03")
        mock_move.reset_mock()

if __name__ == '__main__':
    unittest.main()
