
from pathlib import Path

# Mocking the get_language function to test logic in isolation
def get_language_mock(subtitle_path: str | Path) -> str:
    path = Path(subtitle_path)
    
    # --- PROPOSED NEW LOGIC START ---
    # Check for language code in filename (e.g. movie.en.srt)
    # Get the suffix parts. Path.suffixes returns ['.en', '.srt'] for 'movie.en.srt'
    # But we want the part specifically before the extension.
    
    parts = path.stem.split('.')
    if len(parts) > 1:
        potential_lang = parts[-1].lower()
        
        # Simple whitelist for now based on user context
        # You might want to expand this list
        if potential_lang in ['en', 'eng', 'ro', 'rum', 'rom']:
            # Normalize map
            if potential_lang in ['rum', 'rom']: return 'ro'
            if potential_lang in ['eng']: return 'en'
            return potential_lang
    # --- PROPOSED NEW LOGIC END ---

    return "fallback_to_detection"

# Test cases
test_files = [
    "Runway.34.2022.en.srt",
    "Runway.34.2022.ro.srt",
    "Movie.Title.eng.srt",
    "NCIS.Origins.S01E01.Enter.Sandman.Part.1.1080p.AMZN.WEB-DL.DDP5.1.H.264-FLUX.srt",
    "Just.A.Movie.Name.srt",
    "Another.Movie.rum.srt"
]

print(f"{'Filename':<80} | {'Detected Language'}")
print("-" * 100)

for f in test_files:
    lang = get_language_mock(f)
    print(f"{f:<80} | {lang}")
