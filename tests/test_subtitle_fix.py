import sys
import shutil
import logging
from unittest.mock import patch
from pathlib import Path

# Add the project directory to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Mock logging
logging.basicConfig(level=logging.INFO)

# Mock linux_mv BEFORE importing subtitle_utils/conversion_utils if they import it directly
# But process_subtitle calls find_or_extract_subtitle which calls linux_mv.
# We will use unittest.mock.patch

from subtitle_utils import process_subtitle

# Create a dummy .sub file with binary content
test_dir = Path("test_vobsub")
test_dir.mkdir(exist_ok=True)

movie_name = "TestMovie"
sub_file = test_dir / f"{movie_name}.ro.sub"
# Note: process_subtitle expects the file to likely be renamed already if it went through find_or_extract
# But here we are calling process_subtitle with the path.
# process_subtitle calls find_or_extract_subtitle.
# find_or_extract_subtitle will try to rename it.

# Create fake VobSub content (MPEG-PS header)
with open(sub_file, 'wb') as f:
    f.write(b'\x00\x00\x01\xba\x44\x55\x66')

print("\n--- Testing VobSub Content Detection ---")
print(f"Created binary .sub file: {sub_file}")

# We need to mock linux_mv to just return True and do the 'move' (or pretend to)
# find_or_extract_subtitle calls get_first_subtitle_found.
# Then it calls linux_mv.
# Then returns path.

with patch('subtitle_utils.linux_mv') as mock_mv:
    mock_mv.return_value = True
    
    # We also need get_first_subtitle_found to return our file
    # But get_first_subtitle_found uses glob.
    
    # Actually, verify what find_or_extract_subtitle changes the path to.
    # It will try to rename to TestMovie.default.ro.sub
    
    # We need to ensure that when process_subtitle receives the NEW path, 
    # it checks the CONTENT of that file.
    # Since linux_mv is mocked, the file WON'T actually move on disk.
    # So if the code tries to read the NEW path, it will fail (File not found).
    
    # Logic fix: in the test, we should move the file manually if we want to test end-to-end,
    # OR we mock the rename so it doesn't rename, 
    # OR we simulate the move in the mock.
    
    def side_effect_mv(src, dst):
        print(f"MOCK MV: {src} -> {dst}")
        # Actually move it so the read works
        shutil.move(src, dst)
        return True

    mock_mv.side_effect = side_effect_mv
    
    try:
        result = process_subtitle(sub_file, movie_name)
        
        expected_name = f"{movie_name}.default.ro.sub"
        print(f"Result Path: {result}")
        
        if result and result.name == expected_name:
            print("SUCCESS: File was renamed/returned.")
            
            # Verify content is still binary (not corrupted/converted)
            with open(result, 'rb') as f:
                content = f.read()
            if content.startswith(b'\x00\x00\x01\xba'):
                print("SUCCESS: Content is still binary VobSub.")
            else:
                print("FAILURE: Content was modified/corrupted!")
        else:
             print(f"FAILURE: Unexpected result path {result}")

    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)
