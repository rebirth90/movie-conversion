import shutil
from pathlib import Path
import subprocess

# Setup test environment
test_root = Path("test_nesting")
if test_root.exists():
    shutil.rmtree(test_root)
test_root.mkdir()

# Scenario:
# Source: test_nesting/Movie.Name.1080p
# Target: test_nesting/Movie.Name

source_dir = test_root / "Movie.Name.1080p"
source_dir.mkdir()
(source_dir / "movie.mkv").touch()

target_dir = test_root / "Movie.Name"
target_dir.mkdir() # Pre-existing target!

print(f"Source: {source_dir}")
print(f"Target: {target_dir}")

# Simulate linux_mv
def linux_mv(src, dst):
    print(f"MV {src} -> {dst}")
    subprocess.run(["mv", "-f", str(src), str(dst)], check=True)

print("\n--- Running mv ---")
linux_mv(source_dir, target_dir)

print("\n--- Checking Result ---")
# If nested, we will find target_dir / source_dir.name
nested_path = target_dir / source_dir.name
if nested_path.exists():
    print(f"ISSUE REPRODUCED: Nested directory found at {nested_path}")
else:
    print("Issue NOT reproduced (maybe flattened?)")

# cleanup
# shutil.rmtree(test_root)
