import sys
import shutil
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Mock logging
logging.basicConfig(level=logging.INFO)

# Mock config to avoid import errors or filesystem checks
sys.modules['config'] = MagicMock()
sys.modules['config'].FFMPEG_PATH = Path('/usr/bin/ffmpeg')
sys.modules['config'].VALID_EXTENSIONS = {'.mp4', '.srt', '.sub', '.idx'}

# We need to test process_movie_file and process_tv_series_file logic for moving .idx
# But those functions do a lot (validation, conversion, etc).
# It's easier to unit test the specific logic block if we could, but integration test is better.
# We will mock almost everything except the move logic.

# However, since we modified conversion_utils.py, we can import it.
# We need to mock 'linux_mv', 'validate_target_root', 'get_first_subtitle_found', 'process_subtitle_and_video'

from conversion_utils import process_movie_file

# Create dummy files
test_dir = Path("test_idx_move")
test_dir.mkdir(exist_ok=True)
movie_file = test_dir / "TestMovie.mkv"
sub_file = test_dir / "TestMovie.sub"
idx_file = test_dir / "TestMovie.idx"

movie_file.touch()
sub_file.touch()
idx_file.touch()

print("\n--- Testing .idx Move Logic ---")

with patch('conversion_utils.linux_mv') as mock_mv, \
     patch('conversion_utils.validate_target_root', return_value=True), \
     patch('conversion_utils.get_first_subtitle_found') as mock_get_sub:

    # Setup mocks
    mock_get_sub.return_value = sub_file
    
    # We simulate process_movie_file
    # It should:
    # 1. Create directory
    # 2. Move movie file
    # 3. Move subtitle file
    # 4. Move idx file (NEW)
    
    # We don't want it to actually create directories on disk if we can avoid it, 
    # but the function calls mkdir. Let's let it try or mock pathlib.Path.mkdir if needed.
    # Actually, let's just let it run. failed mkdir checks are fine if handled.
    
    try:
        # Mocking mkdir to avoid permission errors if run in restricted env, though we are in wsl.
        # But we can just use a real temp dir structure.
        
        # Call the function
        result_dir = process_movie_file(movie_file)
        
        # Analyze mock_mv calls
        # We expect:
        # 1. mv movie_file -> movie_dir
        # 2. mv sub_file -> movie_dir
        # 3. mv idx_file -> movie_dir (THIS IS WHAT WE ARE TESTING)
        
        print(f"Total mv calls: {mock_mv.call_count}")
        
        found_idx_move = False
        for call in mock_mv.call_args_list:
            src, dst = call[0]
            print(f"MV Call: {src} -> {dst}")
            if str(src).endswith('.idx'):
                found_idx_move = True
        
        if found_idx_move:
            print("SUCCESS: .idx file move detected.")
        else:
            print("FAILURE: .idx file was NOT moved.")

    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)
