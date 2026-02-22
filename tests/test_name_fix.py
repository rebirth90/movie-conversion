import sys

from pathlib import Path

# Add the project directory to sys.path so we can import movie_utils
sys.path.append(str(Path(__file__).parent.parent))

from movie_utils import sanitize_movie_name

test_cases = [
    "Millennium.Actress.1080p.BluRay.FLAC.x264-FiLELiST",
    "Some.Movie.2023.1080p.WEB-DL",
    "NoYearMovie.720p.HDTV.x264",
    "Another.Movie.4k.HDR",
    "Movie.With.No.Flags.Or.Year",
    "Movie.With.Year.1999.And.Flags.1080p"
]

print("Running Name Sanitization Tests...\n")
for filename in test_cases:
    print(f"Original:  {filename}")
    print(f"Sanitized: {sanitize_movie_name(filename)}")
    print("-" * 40)
