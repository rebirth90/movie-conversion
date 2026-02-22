import sys
import shutil
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Mock logging
logging.basicConfig(level=logging.INFO)

# Mock config
sys.modules['config'] = MagicMock()
sys.modules['config'].FFMPEG_PATH = Path('/usr/bin/ffmpeg')
sys.modules['config'].VALID_EXTENSIONS = {'.mp4', '.srt', '.sub', '.idx'}
sys.modules['config'].BASE_TVSERIES_ROOT = Path("/shared-directory/tv-series")
sys.modules['config'].TARGET_TVSERIES_DIR = Path("/share/tv-series")

from conversion_utils import process_movie_file, process_tv_series_file

# Create dummy local files for movie test
root_dir = Path("shared-directory")
root_dir.mkdir(exist_ok=True)
movie_dir = root_dir / "movies"
movie_dir.mkdir(exist_ok=True)
movie_file = movie_dir / "TestMovie.mkv"
sub_file = movie_dir / "TestMovie.sub"
idx_file = movie_dir / "TestMovie.idx"
movie_file.touch()
sub_file.touch()
idx_file.touch()

print("\n--- Testing .idx Move Logic ---")

# Mock linux_mv
# Mock validate_target_root
# Mock target_root

with patch('conversion_utils.linux_mv') as mock_mv, \
     patch('conversion_utils.validate_target_root', return_value=True), \
     patch('conversion_utils.target_root', Path("/share")), \
     patch('conversion_utils.get_first_subtitle_found') as mock_get_sub, \
     patch('conversion_utils.process_subtitle_and_video') as mock_process_video:
    
    # --- Test Movie ---
    print("\n[MOVIE TEST]")
    mock_get_sub.return_value = sub_file
    try:
        process_movie_file(movie_file)
    except Exception as e:
        print(f"Movie Error: {e}")
        import traceback
        traceback.print_exc()

    # Check movie results
    found_movie_idx = False
    for call in mock_mv.call_args_list:
        if call.args: # Check if args tuple is not empty
             src, dst = call.args[0], call.args[1]
             if str(src).endswith('.idx') and "TestMovie" in str(src):
                 print(f"MV Call (Movie): {src} -> {dst}")
                 found_movie_idx = True
    
    # --- Test TV Series ---
    print("\n[TV SERIES TEST]")
    mock_mv.reset_mock()
    
    # Define fake absolute paths for TV Series.
    # Note: These paths strictly speaking don't exist on disk, so we rely on mocking exists()
    
    fake_ep_path = Path("/shared-directory/tv-series/TestShow/Season 1/TestShow.S01E01.mkv")
    fake_sub_path = Path("/shared-directory/tv-series/TestShow/Season 1/TestShow.S01E01.sub")
    
    # This must be returned by process_subtitle_and_video
    fake_converted_path = Path("/shared-directory/tv-series/TestShow/Season 1/TestShow.S01E01.mp4")
    
    mock_process_video.return_value = (fake_sub_path, fake_converted_path)
    
    # We patch Path.exists globally as True to bypass checks, 
    # but we need iterdir to return empty list eventually for cleanup.
    
    # We need a custom side_effect for exists so that:
    # 1. fake_ep_path.exists() -> True
    # 2. fake_sub_path.with_suffix('.idx').exists() -> True (CRITICAL for test)
    
    def side_effect_exists(self):
        # Always return True for simplicity unless we want to test failure
        return True

    with patch('pathlib.Path.exists', side_effect=side_effect_exists, autospec=True), \
         patch('os.access', return_value=True), \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.unlink'), \
         patch('pathlib.Path.rmdir'), \
         patch('pathlib.Path.iterdir', return_value=[]):
         
         try:
            process_tv_series_file(fake_ep_path)
         except Exception as e:
            print(f"TV Series Error: {e}")
            import traceback
            traceback.print_exc()

    # Check TV results
    found_tv_idx = False
    for call in mock_mv.call_args_list:
        if call.args:
            src, dst = call.args[0], call.args[1]
            if str(src).endswith('.idx'):
                print(f"MV Call (TV): {src} -> {dst}")
                found_tv_idx = True

    if found_movie_idx:
        print("\nSUCCESS: Movie .idx move detected.")
    else:
        print("\nFAILURE: Movie .idx NOT moved.")

    if found_tv_idx:
        print("SUCCESS: TV Series .idx move detected.")
    else:
        print("FAILURE: TV Series .idx NOT moved.")

    # Cleanup
    if root_dir.exists():
        shutil.rmtree(root_dir)
