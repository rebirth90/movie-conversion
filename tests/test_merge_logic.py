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
sys.modules['config'].BASE_MOVIES_ROOT = Path("/shared-directory/movies")

from conversion_utils import process_movie_directory

# Create dummy local files
root_dir = Path("test_merge")
if root_dir.exists():
    shutil.rmtree(root_dir)
root_dir.mkdir()

# Scenario:
# Source: test_merge/Movie.Name.1080p
# Target: test_merge/Movie.Name (Already exists)

source_dir = root_dir / "Movie.Name.1080p"
source_dir.mkdir()
(source_dir / "movie.mkv").touch()
(source_dir / "movie.sub").touch()

target_dir = root_dir / "Movie.Name"
target_dir.mkdir()
# Target might have some old files
(target_dir / "old_junk.txt").touch()

print(f"Source: {source_dir}")
print(f"Target: {target_dir}")

print("\n--- Testing Merge Logic ---")

# Mock linux_mv to simulate move
# We need linux_mv to actually DO the move or at least print
# Since we are using real files, let's use a wrapper that calls shutil.move for simulation of linux_mv behavior in test env
# But our code calls `linux_mv`.
# We should patch linux_mv to use shutil.move so we can verify file positions.

def side_effect_mv(src, dst):
    print(f"MV {src} -> {dst}")
    # Simulate mv behavior. If dst exists and is dir, mv moves src INSIDE dst.
    # But our CODE now calls `linux_mv(item, renamed_dir / item.name)`.
    # So dst is full path to file. 
    # shutil.move(src, dst) works.
    
    # Ensure parent exists
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)
    return True

with patch('conversion_utils.linux_mv', side_effect=side_effect_mv) as mock_mv, \
     patch('conversion_utils.validate_target_root', return_value=True), \
     patch('conversion_utils.target_root', Path("/share")), \
     patch('conversion_utils.get_largest_movie_file') as mock_get_largest, \
     patch('conversion_utils.process_subtitle_and_video') as mock_process, \
     patch('conversion_utils.cleanup_movie_directory'), \
     patch('conversion_utils.sanitize_movie_name', return_value="Movie.Name"):

    # Mock success to trigger cleanup (though we mocked cleanup)
    mock_process.return_value = (Path("sub"), Path("vid"))
    mock_get_largest.return_value = Path("dummy")

    try:
        process_movie_directory(source_dir)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

print("\n--- Checking Result ---")
# If merge worked:
# source_dir should be empty or gone
# target_dir should contain movie.mkv and movie.sub

mkv_in_target = target_dir / "movie.mkv"
sub_in_target = target_dir / "movie.sub"

if mkv_in_target.exists():
    print("SUCCESS: movie.mkv found in target main root.")
else:
    print("FAILURE: movie.mkv NOT found in target main root.")

# Check for nesting
nested_dir = target_dir / "Movie.Name.1080p"
if nested_dir.exists():
    print(f"FAILURE: Nested directory found: {nested_dir}")
else:
    print("SUCCESS: No nested directory found.")

# Cleanup
# if root_dir.exists():
#    shutil.rmtree(root_dir)
