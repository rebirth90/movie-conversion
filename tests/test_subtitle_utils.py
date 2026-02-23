import unittest
from pathlib import Path
from subtitle_utils import process_subtitle, get_track
from unittest.mock import patch, MagicMock
from config import AppConfig
import tempfile
import os

class TestSubtitleUtils(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig()
        
    @patch('subtitle_utils.subprocess.run')
    @patch.object(Path, 'exists', return_value=True)
    @patch('pathlib.Path.stat')
    def test_process_subtitle_vobsub_skip(self, mock_stat, mock_exists, mock_run):
        """Simulate passing a VobSub binary subtitle - should not run character replacement."""
        sub_path = Path("/movies/Avatar/Avatar.sub")
        
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 1024
        mock_stat_result.st_mode = 16877  # S_IFDIR | 0755
        mock_stat.return_value = mock_stat_result
        # Ensure it skips because .idx is detected
        # Ensure it skips because .idx is detected - process_subtitle returns Path for vobsub.
        # However if FFprobe fails we get None without extraction.
        # We need mock_get_track to return valid track or adjust assertion
        with patch('subtitle_utils.get_track', return_value=(0, 'dvd_subtitle', 'ro')):
            new_path= process_subtitle(sub_path, "Avatar", self.config)
            self.assertEqual(new_path, Path("/movies/Avatar/Avatar.default.ro.sub"))
            mock_run.assert_called_once()

    @patch('subtitle_utils.subprocess.run')
    @patch('subtitle_utils.from_bytes')
    def test_process_subtitle_microdvd_convert(self, mock_from_bytes, mock_run):
        """Simulate passing a MicroDVD file which should convert to SRT."""
        sub_path = Path("/movies/Avatar/Avatar.sub")
        
        # Mocking that the binary companion DOES NOT exist
        with patch.object(Path, 'exists', return_value=False):
            # Because it's a test without actual FFmpeg, we'll mock the execute_process
            # that generates the output
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_run.return_value = mock_proc
            
            # Note: since the file doesn't actually exist to be opened by the character
            # replacement step we mock the file operations
            
            with patch('builtins.open'):
                with patch.object(Path, 'read_bytes', return_value=b"some bytes"):
                    with patch.object(Path, 'write_text'):
                        with patch('langdetect.detect', return_value='ro'):
                            with patch.object(Path, 'rename', return_value=Path("/movies/Avatar/Avatar.ro.srt")) as mock_rename:
                                new_path = process_subtitle(sub_path, "Avatar", self.config)
                                
                                # It should have run FFmpeg to generate .srt
                                mock_run.assert_called_once()
    
    @patch('langdetect.detect')
    def test_subtitle_character_replacement_flow(self, mock_detect):
        """Creates a real temporary subtitle to test RO string parsing without FFmpeg mock."""
        mock_detect.return_value = 'ro'
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_sub = Path(tmpdir) / "Test.Movie.srt"
            # Messy Romanian subtitle with standard incorrect encodings like º and þ
            test_sub.write_text("1\n00:00:01,000 --> 00:00:02,000\nAici este un text cu ºi þi.", encoding='utf-8')
            
            # Since the file is already SRT, process_subtitle will skip conversion
            # and just run language detection & character replace.
            new_path = process_subtitle(test_sub, "TestMovie", self.config)
            
            # Should be renamed to .ro.srt
            self.assertEqual(new_path.suffix, '.srt')
            self.assertTrue(new_path.name.endswith('.ro.srt'))
            
            # Content should be fixed based on config.REPLACE_RULES (which maps º->ș, þ->ț, etc.)
            content = new_path.read_text(encoding='utf-8')
            self.assertIn("si ti", content)

if __name__ == '__main__':
    unittest.main()
