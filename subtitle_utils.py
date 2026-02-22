#!/usr/bin/env python3
import logging
from pathlib import Path
import subprocess
import json
import time
import re
from charset_normalizer import from_bytes
import glob
from langdetect import detect, LangDetectException
from typing import Tuple, Optional
from config import REPLACE_RULES, AppConfig
import shutil


logger = logging.getLogger(__name__)

CODEC_MAP = {
    "subrip": "srt",
    "srt": "srt",
    "ass": "ass",
    "ssa": "ssa",
    "webvtt": "vtt",
    "mov_text": "srt",
    "dvb_subtitle": "sub",
    "hdmv_pgs_subtitle": "sup",
    "dvd_subtitle": "sub",
    "pgs": "sup",
    "text": "txt",
}

LANG_MAP = {
    "rum": "ro",
    "ro": "ro",
    "rom": "ro",
    "eng": "en",
    "en": "en",
    "english": "en"
}

def get_track(movie_file: Path, config: AppConfig) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    try:
        result = subprocess.run(
            [
                str(config.ffprobe_path),
                "-v",
                "error",
                "-select_streams",
                "s",
                "-show_entries",
                "stream=index,codec_name:stream_tags=language",
                "-of",
                "json",
                str(movie_file),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        probe_data = json.loads(result.stdout)
        subtitle_tracks = probe_data.get("streams", [])

        # Priority resolution
        for track in subtitle_tracks:
            lang_tag = track.get("tags", {}).get("language", "").lower()
            mapped_lang = LANG_MAP.get(lang_tag)
            
            if mapped_lang == "ro":
                return track["index"], track.get("codec_name", "").lower(), "ro"

        # Fallback resolution
        for track in subtitle_tracks:
            lang_tag = track.get("tags", {}).get("language", "").lower()
            mapped_lang = LANG_MAP.get(lang_tag)
            
            if mapped_lang == "en":
                return track["index"], track.get("codec_name", "").lower(), "en"

        return None, None, None

    except subprocess.CalledProcessError as e:
        logger.error(f"FFPROBE_ERROR: {e.stderr if e.stderr else e}")
        return None, None, None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(
            f"PARSE_ERROR_getting_subtitle_track: {type(e).__name__}: {e}"
        )
        return None, None, None
    except Exception:
        logger.exception("UNEXPECTED_ERROR_getting_subtitle_track")
        return None, None, None


def ffmpeg_extract_subtitle(movie_file: Path, movie_name: str, folder: Path, track_id: int, codec: str, language: str, config: AppConfig) -> Optional[Tuple[Path, str]]:
    # Resolve codec extension
    extension = CODEC_MAP.get(codec)
    if not extension:
        # Partial match fallback
        for key, ext in CODEC_MAP.items():
            if key in codec:
                extension = ext
                break
    if not extension:
        logger.warning(f"Unknown subtitle codec: {codec}, defaulting to .srt")
        extension = "srt"

    # Construct filename inline
    if language == 'ro': 
        new_subtitle_name = f"{movie_name}.default.ro.{extension}"
    else: 
        new_subtitle_name = f"{movie_name}.{language}.{extension}"
    subtitle_path = folder / new_subtitle_name

    logger.info(f"Extracting {codec} subtitle as .{extension}: {subtitle_path}")

    try:
        match codec:
            case "subrip":
                args = [
                    "-i",
                    str(movie_file),
                    "-map",
                    f"0:{track_id}",
                    str(subtitle_path),
                ]
                subprocess.run(
                    [str(config.ffmpeg_path)] + args,
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    check=True,
                )
            case _:
                # Use mkvextract for MKV containers (preserves codec)
                args = ["tracks", str(movie_file), f"{track_id}:{subtitle_path}"]
                subprocess.run(
                    [str(config.mkvextract_path)] + args,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        if subtitle_path.exists():
            logger.info(f"Successfully extracted subtitle: {subtitle_path}")
            return subtitle_path, extension

        logger.error(f"Extraction completed but file not found: {subtitle_path}")
        return None

    except subprocess.CalledProcessError as e:
        logger.error(f"EXTRACTION_ERROR: {e.stderr if e.stderr else e}")
        return None
    except (FileNotFoundError, PermissionError) as e:
        # These are likely permanent failures
        logger.error(f"FILE_ERROR extracting subtitle: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.exception(f"UNEXPECTED_ERROR extracting subtitle: {e}")
        return None

def extract_subtitle(movie_file, movie_name, output_dir, config: AppConfig):
    track_id, codec, language = get_track(movie_file, config)

    if track_id is None or codec is None or language is None:
        return None, None, None

    logger.info(f"Extracting subtitle track {track_id} ({language}, codec: {codec})")
    result = ffmpeg_extract_subtitle(movie_file, movie_name, output_dir, track_id, codec, language, config)
    
    if not result:
        return None, None, None

    subtitle_file, extension = result
    time.sleep(0.5)

    if not subtitle_file.exists():
        logger.warning(f"Extracted subtitle file does not exist: {subtitle_file}")
        return None, None, None

    file_size = subtitle_file.stat().st_size
    if file_size == 0:
        logger.warning(f"Extracted subtitle file is empty: {subtitle_file}")
        return None, None, None

    logger.info(f"Subtitle file size: {file_size} bytes")
    
    return subtitle_file, language, extension

def detect_and_convert_encoding(file_path: Path) -> str:
    with open(file_path, 'rb') as f:
        raw_data = f.read()

    # 1. Fast path: Check for Byte Order Mark (BOM)
    if raw_data.startswith(b'\xef\xbb\xbf'):
        logger.info("Detected UTF-8 BOM")
        content = raw_data.decode('utf-8-sig')
    elif raw_data.startswith(b'\xff\xfe'):
        logger.info("Detected UTF-16LE BOM")
        content = raw_data.decode('utf-16-le')
    elif raw_data.startswith(b'\xfe\xff'):
        logger.info("Detected UTF-16BE BOM")
        content = raw_data.decode('utf-16-be')
    else:
        # 2. Try strict UTF-8 (most common for modern files)
        try:
            content = raw_data.decode('utf-8')
            logger.info("Detected UTF-8 (No BOM)")
            # Sanity check: if it decodes as UTF-8 but has A LOT of nulls, it might be UTF-16 without BOM
            # But strict UTF-8 usually fails often on random binary.
        except UnicodeDecodeError:
            content = None

    # 3. Use charset_normalizer for intelligent detection if strict UTF-8 failed
    if content is None:
        results = from_bytes(raw_data)
        best_match = results.best()
        
        if best_match:
            detected_encoding = best_match.encoding
            logger.info(f"Charset Normalizer analysis: {detected_encoding}")
            try:
                content = str(best_match)
            except UnicodeDecodeError:
                logger.warning(f"Charset Normalizer detected {detected_encoding} but decode failed.")
                pass

    # 4. Fallback to common legacy encodings (Safe 8-bit)
    if content is None:
        fallback_encodings = ['cp1250', 'iso-8859-2', 'cp1252', 'latin-1']
        for enc in fallback_encodings:
            try:
                logger.info(f"Fallback attempt with: {enc}")
                content = raw_data.decode(enc)
                break
            except UnicodeDecodeError:
                continue

    # 5. Final safety net (Replace errors)
    if content is None:
        logger.warning("All encoding attempts failed. Forcing latin-1 with replacement.")
        content = raw_data.decode('latin-1', errors='replace')

    # Cleanup: Remove BOM and null bytes if they persist
    if content.startswith('\ufeff'):
        content = content.replace('\ufeff', '')
    
    # Text file shouldn't have null bytes usually, but some bad encodings might leave them
    if '\x00' in content:
         logger.warning("Null bytes found in text content, removing them.")
         content = content.replace('\x00', '')

    content = content.strip()

    # Write back as standard UTF-8
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return content

def character_replace(input_path: Path, output_path: Path) -> None:
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        total_replacements = 0

        for find, repl in REPLACE_RULES:
            count = content.count(find)
            if count > 0:
                content = content.replace(find, repl)
                total_replacements += count
                logger.info("REPLACED: '%s' -> '%s': %d", find, repl, count)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    except Exception as e:
        logger.error("ERROR_in_clean_subtitle_file: %s", e)
        raise

def get_language(subtitle_path: str | Path) -> str:
    """
    Detect language of a subtitle file using langdetect.
    Returns 'unknown' if detection fails or text is too short.
    """
    path = Path(subtitle_path)
    
    # 1. Check filename for language code (e.g. movie.en.srt)
    # path.stem for 'movie.en.srt' is 'movie.en' -> split giving ['movie', 'en']
    parts = path.stem.split('.')
    if len(parts) > 0:
        potential_lang = parts[-1].lower()
        
        if potential_lang in ['ro', 'rum', 'rom']:
            logger.info(f"Language detected from filename: {potential_lang} -> ro")
            return 'ro'
            
        if potential_lang in ['en', 'eng', 'english']:
            logger.info(f"Language detected from filename: {potential_lang} -> en")
            return 'en'

    if not path.exists():
        logger.error(f"Subtitle file not found for language detection: {path}")
        return "error_file_not_found"

    try:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback: Detect encoding for legacy files (Windows-1252, Shift-JIS, etc.)
            logger.warning(f"UTF-8 decode failed for {path.name}, attempting auto-detection")
            with open(path, 'rb') as f:
                raw_data = f.read()
                best_match = from_bytes(raw_data).best()
                encoding = best_match.encoding if best_match else 'utf-8'
                logger.info(f"Auto-detected encoding: {encoding}")
                content = str(best_match) if best_match else raw_data.decode('utf-8', errors='replace')

        # Clean up text for better detection
        content = re.sub(r'\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s-->\s\d{1,2}:\d{2}:\d{2}[,.]\d{3}', ' ', content)
        content = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'\{[^}]+\}', ' ', content) # Common in .ass files
        clean_text = content.strip()

        if len(clean_text) < 10 or not re.search(r'[a-zA-Z\u00C0-\u00FF]', clean_text):
            logger.warning(f"Text too short or invalid for language detection in {path.name}")
            return "unknown"
        
        sample_text = clean_text[:2000] 
        lang = detect(sample_text)
        logger.info(f"Detected language for {path.name}: {lang}")
        return lang

    except LangDetectException:
        logger.warning(f"Language detection failed for {path.name}")
        return "unknown"
    except Exception as e:
        logger.error(f"Error detecting language for {path.name}: {e}")
        return f"error: {str(e)}"

def get_first_subtitle_found(movie_file: Path) -> Optional[Path]:
    """
    Search for existing external subtitle files (srt, vtt, ass, sub) matching the movie filename.
    Returns the first match found, or None.
    """
    extensions = ["srt", "vtt", "ass", "sub"]
    movie_stem = movie_file.stem
    safe_stem = glob.escape(movie_stem)
    parent_dir = movie_file.parent

    for ext in extensions:
        # Check simple match: movie_name.srt
        matches = list(parent_dir.glob(f"{safe_stem}*.{ext}"))
        if matches:
            found = matches[0]
            logger.info(f"Found external subtitle: {found.name}")
            return found

    return None

def find_or_extract_subtitle(movie_file: Path, movie_name: str, output_dir: Path, config: AppConfig) -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """
    Strategy:
    1. Look for existing external subtitle.
    2. If not found, try to extract embedded subtitle from the video file.
    """
    existing_subtitle_file = get_first_subtitle_found(movie_file)

    if existing_subtitle_file:
        logger.info(f"Using existing local subtitle: {existing_subtitle_file}")
        language = get_language(existing_subtitle_file)
        extension = existing_subtitle_file.suffix.lstrip(".")
        
        # Inline renaming logic
        if language == 'ro': 
            new_subtitle_name = f"{movie_name}.default.ro.{extension}"
        else: 
            new_subtitle_name = f"{movie_name}.{language}.{extension}"
        subtitle_path = output_dir / new_subtitle_name
        
        # FIX: Rename the file if the name is different
        if subtitle_path != existing_subtitle_file:
            logger.info(f"Renaming subtitle: {existing_subtitle_file.name} -> {subtitle_path.name}")
            try:
                shutil.move(str(existing_subtitle_file), str(subtitle_path))
                logger.info("Subtitle renamed successfully")
            except OSError as e:
                logger.error(f"Failed to rename subtitle: {e}")
                return None, None, None

        return subtitle_path, language, extension
        
    else:
        logger.info("No external subtitle found, attempting extraction...")
        extracted_subtitle_file, language, extension = extract_subtitle(movie_file, movie_name, output_dir, config)
        
        if extracted_subtitle_file:
            logger.info(f"Using extracted embedded subtitle: {extracted_subtitle_file}")
            return extracted_subtitle_file, language, extension
        else:
            logger.warning("No subtitle found locally or embedded.")
            return None, None, None

def convert_sub_to_srt(sub_file: Path, config: AppConfig) -> Optional[Path]:
    """
    Converts MicroDVD (.sub) to SubRip (.srt) using ffmpeg.
    Returns the path to the new .srt file if successful.
    """
    srt_file = sub_file.with_suffix('.srt')
    
    cmd = [
        str(config.ffmpeg_path), "-y",
        "-i", str(sub_file),
        str(srt_file)
    ]
    
    try:
        logger.info(f"CONVERTING: {sub_file.name} -> .srt")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if srt_file.exists() and srt_file.stat().st_size > 0:
            logger.info("CONVERSION_SUCCESSFUL")
            # Optional: Delete the original .sub file after successful conversion
            # sub_file.unlink() 
            return srt_file
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to convert .sub to .srt: {e}")
    
    return None

def process_subtitle(job_path: Path, cleaned_video_name: str, config: AppConfig) -> Optional[Path]:
    """
    Handle subtitle extraction/discovery and conversion (UTF-8, character replacement).
    SAFEGUARD: Skips text processing if .idx file exists (VobSub).
    Returns path to the processed subtitle file, or None if failed.
    """
    output_dir = job_path.parent
    subtitle_file, language, extension = find_or_extract_subtitle(job_path, cleaned_video_name, output_dir, config)

    if not subtitle_file:
        return None

    if subtitle_file.stat().st_size == 0:
        logger.warning(f"Empty subtitle file found: {subtitle_file}")
        return None

    # --- SAFEGUARD: Check for VobSub (.idx existence) ---
    # If a .idx file exists with the same name, this is a binary VobSub file.
    # We must NOT touch it with text encoding/replacement tools.
    if subtitle_file.with_suffix('.idx').exists():
        logger.info(f"VobSub detected (.idx found): Skipping text processing for {subtitle_file.name}")
        return subtitle_file
    # ----------------------------------------------------

    if language == "ro":
        # Check if it's a VobSub file (binary) by checking header signatures as a secondary safeguard
        if subtitle_file.suffix.lower() == '.sub':
            try:
                with open(subtitle_file, 'rb') as f:
                    header = f.read(32)
                    # Check for MPEG-PS Pack Header (0x000001BA)
                    if header.startswith(b'\x00\x00\x01\xba'):
                        logger.info(f"Binary VobSub detected (MPEG-PS header): Skipping text processing for {subtitle_file.name}")
                        return subtitle_file
                    
                    # Fallback: if it doesn't look like text (doesn't start with {)
                    # and has null bytes, assume binary to be safe.
                    if b'{' not in header and b'\x00' in header:
                         logger.info(f"Binary file detected (Null bytes found, no MicroDVD header): Skipping text processing for {subtitle_file.name}")
                         return subtitle_file

            except Exception as e:
                logger.warning(f"Failed to check file header for {subtitle_file.name}: {e}")

        # 1. Repair Encoding
        detect_and_convert_encoding(subtitle_file)
        
        # 2. Convert .sub to .srt (MicroDVD to SubRip)
        if subtitle_file.suffix.lower() == '.sub':
            # Check if it's text-based MicroDVD (starts with '{')
            try:
                with open(subtitle_file, 'r', encoding='utf-8', errors='ignore') as f:
                    first_char = f.read(1)
                
                if first_char == '{':
                    new_srt = convert_sub_to_srt(subtitle_file, config)
                    if new_srt:
                        subtitle_file = new_srt  # Switch to using the new .srt file
            except Exception as e:
                logger.warning(f"Failed to check/convert .sub file: {e}")

        # 3. Apply Character Replacement Rules
        character_replace(subtitle_file, subtitle_file)
    
    return subtitle_file




