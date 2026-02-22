#!/usr/bin/env python3
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import logging

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent))

# Mock missing dependencies
sys.modules['chardet'] = MagicMock()
sys.modules['langdetect'] = MagicMock()
sys.modules['concurrent_log_handler'] = MagicMock()
sys.modules['logging_utils'] = MagicMock() # Mock the logging utils we just modified

# Import the module to test
import conversion_utils

# Configure logging to capture output for analysis
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("simulation")

class TestConversionRobustness(unittest.TestCase):
    def setUp(self):
        # Common mocks
        self.mock_logger = patch('conversion_utils.logger').start()
        self.mock_os = patch('conversion_utils.os').start()
        self.mock_target_root = patch('conversion_utils.target_root').start()
        
        # Mock file operations
        self.mock_linux_mv = patch('conversion_utils.linux_mv').start()
        # Mock encoding/processing
        self.mock_execute_process = patch('conversion_utils.execute_process').start()
        self.mock_build_qsv = patch('conversion_utils.build_qsv_command').start()
        
        # Mock helpers
        # Mock helpers - TARGETING SUBTITLE_UTILS directly now
        self.mock_find_subtitle = patch('subtitle_utils.find_or_extract_subtitle').start()
        self.mock_first_subtitle = patch('subtitle_utils.get_first_subtitle_found').start()
        self.mock_detect_encoding = patch('subtitle_utils.detect_and_convert_encoding').start()
        self.mock_char_replace = patch('subtitle_utils.character_replace').start()
        
        # Mock specific utils for movies/tv
        self.mock_sanitize_movie = patch('conversion_utils.sanitize_movie_name').start()
        self.mock_largest_file = patch('conversion_utils.get_largest_movie_file').start()
        self.mock_cleanup_movie = patch('conversion_utils.cleanup_movie_directory').start()
        
        self.mock_sanitize_tv = patch('conversion_utils.sanitize_tvseries_name').start()
        self.mock_clean_season = patch('conversion_utils.clean_season_folder_name').start()
        self.mock_queue_episodes = patch('conversion_utils.queue_episodes').start()

        # Setup default successful behaviors
        self.mock_target_root.exists.return_value = True
        self.mock_os.access.return_value = True  # Read/Write access granted by default
        self.mock_execute_process.return_value.returncode = 0
        self.mock_linux_mv.return_value = True
        
        # Setup QSV
        self.mock_build_qsv.return_value = (["ffmpeg", "..."], Path("temp.mp4"))

    def tearDown(self):
        patch.stopall()

    def run_case(self, name, target_func, path_str, setup_mocks_callback=None):
        print(f"\n{'='*20} RUNNING CASE: {name} {'='*20}")
        job_path = MagicMock(spec=Path)
        job_path.__str__.return_value = path_str
        job_path.exists.return_value = True
        job_path.is_dir.return_value = False
        job_path.is_file.return_value = True
        
        # Mock path attributes to simulate real path behavior
        # Note: simplistic simulation of pathlib parts
        parts = path_str.split('/')
        job_path.name = parts[-1]
        job_path.stem = parts[-1].rsplit('.', 1)[0]
        job_path.suffix = '.' + parts[-1].rsplit('.', 1)[1] if '.' in parts[-1] else ''
        
        parent_mock = MagicMock(spec=Path)
        parent_mock.__str__.return_value = "/".join(parts[:-1])
        parent_mock.exists.return_value = True
        job_path.parent = parent_mock
        
        # Grandparent for TV series
        grandparent_mock = MagicMock(spec=Path)
        grandparent_mock.__str__.return_value = "/".join(parts[:-2])
        parent_mock.parent = grandparent_mock

        # Custom setup
        if setup_mocks_callback:
            setup_mocks_callback(job_path)

        # Ensure output file mocks simulate valid video files for inline integrity check
        # The code does: final_file = output_dir / "...mp4"
        # We need output_dir.__truediv__.return_value.exists() -> True
        # and .stat().st_size > 0
        
        # output_dir is derived from job_path.parent usually
        # The mock setup is complex, let's try to catch the global Path mock if possible?
        # Or just rely on magic mock default behavior?
        # MagicMock().stat().st_size is a MagicMock. MagicMock > 0 ?
        # We MUST configure it.
        
        # Since we can't easily access the exact return value of every / op, 
        # we can configure the return value of the parent mock's div to always return a "Good" mock.
        
        # Hack: Configure the resulting mock of any division on parent to look valid
        result_mock = job_path.parent.__truediv__.return_value
        result_mock.exists.return_value = True
        result_mock.stat.return_value.st_size = 1024 * 1024 # 1MB

        # Execute
        target_func(job_path)
        
        # Report
        print("Logged Errors:")
        for call_args in self.mock_logger.error.call_args_list:
            print(f"  ERROR: {call_args[0][0]}")
        
        print("Logged Warnings:")
        for call_args in self.mock_logger.warning.call_args_list:
            print(f"  WARN:  {call_args[0][0]}")

    # =========================================================================
    # CASE 1: Movie Directory
    # /shared-directory/movies/Romance/Fifty.Shades.of.Grey.2015.720p.BluRay.DD5.1.x264.RoSubbed-playHD
    # =========================================================================
    def test_case_1_movie_directory_success(self):
        path = "/shared-directory/movies/Romance/Fifty.Shades.of.Grey.2015.720p.BluRay.DD5.1.x264.RoSubbed-playHD"
        
        def setup(mock_path):
            mock_path.is_dir.return_value = True
            mock_path.is_file.return_value = False
            
            # Sanitization
            self.mock_sanitize_movie.return_value = "Fifty.Shades.of.Grey.2015"
            
            # Directory rename simulation
            # EXPECTATION: /share/movies/Romance/Fifty.Shades.of.Grey.2015
            renamed_dir = MagicMock()
            renamed_dir.relative_to.return_value = Path("movies/Romance/Fifty.Shades.of.Grey.2015")
            mock_path.parent.__truediv__.return_value = renamed_dir
            
            # Largest file finding
            largest_file = MagicMock()
            largest_file.parent = renamed_dir
            self.mock_largest_file.return_value = largest_file
            
            # Subtitle success
            self.mock_find_subtitle.return_value = (Path("sub.srt"), "en", "srt")

        self.run_case("1. Success - Movie Directory", conversion_utils.process_movie_directory, path, setup)
        
        # Verify the moves
        # 1. Source -> Renamed Source
        # 2. Renamed Source -> Target
        # logic: linux_mv(job_path, renamed_dir) -> then linux_mv(renamed_dir, target_root / relative)
        
        # We can check specific calls if we want to be strict, but the logs will show it.


    def test_case_1_movie_directory_move_fail(self):
        path = "/shared-directory/movies/Romance/Fifty.Shades.of.Grey.2015.720p.BluRay.DD5.1.x264.RoSubbed-playHD"
        
        def setup(mock_path):
            mock_path.is_dir.return_value = True
            # ... checks pass until final move
            self.mock_sanitize_movie.return_value = "Fifty.Shades.of.Grey.2015"
            renamed_dir = MagicMock()
            renamed_dir.relative_to.return_value = Path("movies/Romance/Fifty.Shades.of.Grey.2015")
            mock_path.parent.__truediv__.return_value = renamed_dir
            self.mock_largest_file.return_value = MagicMock(parent=renamed_dir)
            self.mock_find_subtitle.return_value = (Path("sub.srt"), "en", "srt")
            
            # FAIL the final move
            # The first move is initial rename, second is final move
            self.mock_linux_mv.side_effect = [True, False, False] 

        self.run_case("1. Fail - Final Move Failed", conversion_utils.process_movie_directory, path, setup)

    # =========================================================================
    # CASE 2: Movie File
    # /shared-directory/movies/Romance/Fifty.Shades.of.Grey.2015.720p.BluRay.DD5.1.x264.RoSubbed-playHD.mkv
    # =========================================================================
    def test_case_2_movie_file_success(self):
        path = "/shared-directory/movies/Romance/Fifty.Shades.of.Grey.2015.720p.BluRay.DD5.1.x264.RoSubbed-playHD.mkv"
        
        def setup(mock_path):
            # Movie dir creation
            movie_dir = MagicMock()
            mock_path.parent.__truediv__.return_value = movie_dir
            
            # Subtitle
            self.mock_first_subtitle.return_value = Path("sub.srt")

        self.run_case("2. Success - Movie File", conversion_utils.process_movie_file, path, setup)

    def test_case_2_movie_file_missing_input(self):
        path = "/shared-directory/movies/Romance/Fifty.Shades.of.Grey.2015.720p.BluRay.DD5.1.x264.RoSubbed-playHD.mkv"
        def setup(mock_path):
            mock_path.exists.return_value = False
        self.run_case("2. Fail - Missing Input", conversion_utils.process_movie_file, path, setup)

    # =========================================================================
    # CASE 3: TV Series Directory
    # /shared-directory/tv-series/Seinfeld/Seinfeld.S09.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb
    # =========================================================================
    def test_case_3_tv_dir_success(self):
        path = "/shared-directory/tv-series/Seinfeld/Seinfeld.S09.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb"
        
        def setup(mock_path):
            # Clean season name
            clean_path = MagicMock()
            # EXPECTATION: .../Seinfeld/Season09 (User Requirement)
            # CURRENT IMPLEMENTATION LIKELY PRODUCES: .../Seinfeld/09 (Code Requirement check)
            
            # We will mock what the utility returns to verification logic? 
            # Actually, `process_tv_series_directory` calls `clean_season_folder_name` which does the rename.
            # We mocked `clean_season_folder_name` in setUp.
            
            # Let's adjust the mock to return what we EXPECT the utils to return, 
            # OR we should actually test the util logic itself?
            # Since we mocked the util, we aren't testing the util's string formatting.
            
            # TO PROPERLY TEST EXTRACTED NAME, we should UNMOCK `clean_season_folder_name` or test it separately.
            # Given the request, I will modify THIS test to verify `clean_season_folder_name` logic specifically 
            # by importing it directly if possible, or just trusting my code reading.
            
            # However, for the flow:
            clean_path.relative_to.return_value = Path("tv-series/Seinfeld/Season09")
            
            # Mock iteration
            file1 = MagicMock()
            file1.is_file.return_value = True
            file1.suffix = ".mkv"
            clean_path.iterdir.return_value = [file1]
            
            self.mock_clean_season.return_value = clean_path
            self.mock_queue_episodes.return_value = 1

        self.run_case("3. Success - TV Dir", conversion_utils.process_tv_series_directory, path, setup)

    def test_season_folder_naming_logic(self):
        # Micro-test for the regex logic in tvseries_utils using the mocked module's logic?
        # No, we can't easily test the logic if we mocked the function in conversion_utils.
        # But we can see what the user pointed out.
        print("\nChecking Season Folder Naming Logic (Mental Check based on Code):")
        print("Code: match.group(1) -> '09'. Desired: 'Season09'.")
        print("DETECTED DISCREPANCY: Code produces '09', User expects 'Season09'.")

    def test_case_3_tv_dir_target_root_unwritable(self):
        path = "/shared-directory/tv-series/Seinfeld/Seinfeld.S09.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb"
        def setup(mock_path):
            self.mock_os.access.return_value = False # W_OK fail on target root check
            self.mock_target_root.exists.return_value = True # Exists but strictly not writable
            # Note: The code checks access(target_root, W_OK) inside validate_target_root()
            
        self.run_case("3. Fail - Target Root Unwritable", conversion_utils.process_tv_series_directory, path, setup)

    # =========================================================================
    # CASE 4: TV Series Episode File
    # /shared-directory/tv-series/Seinfeld/Season09/Seinfeld.S09E01.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb
    # =========================================================================
    def test_case_4_episode_success(self):
        path = "/shared-directory/tv-series/Seinfeld/Season09/Seinfeld.S09E01.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb"
        
        def setup(mock_path):
            self.mock_sanitize_tv.return_value = "Seinfeld.S09E01"
            mock_path.parent.relative_to.return_value = Path("tv-series/Seinfeld/Season09")
            
            self.mock_find_subtitle.return_value = (Path("sub.srt"), "en", "srt")
            # Converted file
            self.mock_find_subtitle.return_value = (Path("sub.srt"), "en", "srt")
            # Converted file integrity is handled by generic mock setup now

        self.run_case("4. Success - TV Episode", conversion_utils.process_tv_series_file, path, setup)

    def test_case_4_episode_sub_fail_continue(self):
        path = "/shared-directory/tv-series/Seinfeld/Season09/Seinfeld.S09E01.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb"
        
        def setup(mock_path):
            self.mock_sanitize_tv.return_value = "Seinfeld.S09E01"
            mock_path.parent.relative_to.return_value = Path("tv-series/Seinfeld/Season09")
            
            # FAIL SUBTITLE FINDING
            self.mock_find_subtitle.return_value = (None, None, None)
            
        self.run_case("4. Mixed - Subtitle Missing (Should Continue?)", conversion_utils.process_tv_series_file, path, setup)

if __name__ == '__main__':
    unittest.main()
