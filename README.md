# Movie & TV Series Conversion System

## **Project Overview**

This project is a robust, automated media processing pipeline designed to standardize and optimize a personal media library. It automatically detects, cleans, converts, and organizes movies and TV series, ensuring a consistent high-quality viewing experience across all devices.

The system is built to run as a background daemon, utilizing a modern **object-oriented Domain-Driven Design (DDD)** architecture. It monitors a queue of content and processes it with industrial-grade reliability, leveraging a local SQLite database for **heuristic learning** and state tracking. It harnesses **Intel Quick Sync Video (QSV)** hardware acceleration for high-speed encoding, and implements intelligent fallback and retry logic to gracefully handle the nuances of media files, from subtitle character encoding to complex season folder structures.
---

## **Installation & Requirements**

### **1. System Dependencies**
Ensure your system has the required multimedia tools installed.
```bash
sudo apt update
sudo apt install ffmpeg mkvtoolnix
```
*Note: `ffmpeg` must be compiled with **Intel QSV** support (or VAAPI as a fallback) for optimal performance on Intel platforms.*

### **2. Python Dependencies**
Install the necessary Python modules. We prioritize system packages (`apt`) where available for stability.
```bash
# Core modules
sudo apt install python3-chardet python3-langdetect

# Additional utilities (via pip if not in repo)
# concurrent-log-handler is typically not in apt
pip3 install concurrent-log-handler
```

---

## **Key Features**

### **1. Automated Queue Management & Heuristics**
*   **Daemonized Worker**: Runs continuously in the background, polling for new jobs using modern pipeline patterns.
*   **File-Based Ingestion**: Simple integration via a text file (`/share/conversion.txt`). Adding content is as easy as appending a path.
*   **Heuristic Learning Database (New!)**: Uses a local SQLite database (`conversion_data.db`) to track processing history.
*   **Smart Retries**: Implements intelligent retry loops that adjust encoding parameters (e.g., modifying `extra_hw_frames`, `bf` or hardware padding) if conversion fails due to memory exhaustion.
*   **Concurrency Control**: Uses an SQLite database queue with atomic transactions to safely handle file ingest operations, paired with robust state management.

### **2. Intelligent Content Handling**
*   **Smart Detection**: Automatically distinguishes between **Movies** and **TV Series** based on folder structure and file patterns.
*   **Advanced Metadata Lookup (New!)**:
    *   Integrates with **TheMovieDB (TMDB)** API to accurately identify movies.
    *   Automatically sanitizes filenames to `Name.Year` format (e.g., `The.Matrix.1999`) based on API data, falling back to regex extraction if needed.
*   **Overwrite Protection**: Smart safeguards prevent accidental processing if the target directory already exists.
*   **TV Series Logic**:
    *   Identifies and standardizes Season folders (e.g., renames `Season.01`, `s1` to `Season01`).
    *   Parses episode filenames to extract standard `SxxExx` numbering.
    *   Queues entire seasons or individual episodes efficiently.
*   **Movie Logic**:
    *   Intelligently selects the largest video file in a folder as the main feature, ignoring samples or extras.

### **3. High-Performance Video Pipeline**
*   **Intel QSV Hardware Acceleration**: Primarily utilizes **Intel Quick Sync Video (`hevc_qsv`)** for high-speed HEVC (H.265) encoding, explicitly optimized for Gen9.5 iGPUs and drastically reducing CPU and VRAM usage.
*   **Smart Scaling & Hardware Filtering**:
    *   **Preserves Quality**: Content smaller than 1080p is kept at native resolution, using hardware VPP filters for padding and mod-16 alignment to prevent encoding artifacts and alignment bugs.
    *   **Standardizes High-Res**: 1080p, 4K, and larger content is automatically scaled to a consistent, high-efficiency 1920x1072 resolution.
*   **Universal Compatibility**: Converts all video to **HEVC (H.265)** in an **MP4 container** (NV12 format) for broad device support.

### **4. Audio Normalization**
*   **Stereo Standardization**: Downmixes all audio tracks (5.1, 7.1, etc.) to **Stereo AAC**.
*   **Bitrate Optimization**:
    *   Surround sources (5.1+) -> High-quality **256k AAC**.
    *   Stereo/Mono sources -> Standard **192k/128k AAC**.
*   **Multi-Language Support**: Preserves *all* audio tracks found in the source file, tagging them with their correct language metadata.

### **5. Advanced Subtitle Management**
*   **Smart Extraction**: Scans for internal (embedded) subtitles and external files (`.srt`, `.ass`, `.sub`, `.idx`).
*   **Format Support**: Handles text-based subtitles (`.srt`, `.ass`, `.sub` MicroDVD) and binary formats (`.sub` VobSub), preserving or converting them as needed.
*   **Language Prioritization**:
    *   **Primary**: Romanian (`ro`). Automatically detected and flagged as default.
    *   **Secondary**: English (`en`).
*   **Character Repair**: Automatically fixes common encoding issues in Romanian subtitles (e.g., `ş` vs `ș`, `ţ` vs `ț`) and converts legacy encodings (Windows-1250, ISO-8859-2) to standard **UTF-8**.

### **6. Robustness & Notification**
*   **Email Notifications (New!)**: Sends an email via SMTP (e.g., Gmail) whenever a conversion fails, attaching relevant FFmpeg and application logs for immediate debugging.
*   **Sanitization**: Renames files and folders to remove "scene" tags (e.g., `WEB-DL`, `x264`, `BluRay`), resulting in clean, readable filenames like `Movie.Title.2023.mp4` or `Series.Title.S01E05.mp4`.
*   **Housekeeping**: Automatically deletes source files after successful conversion and removes empty directories to keep the source folder clutter-free.

---

## **Project Structure**

The project has been refactored into modular components following Domain-Driven Design (DDD) principles:

*   **`core.py`**: The main entry point and worker orchestration.
*   **`models.py`**: Domain-Driven Design (DDD) domain models and data structures.
*   **`exceptions.py`**: Centralized custom exceptions for robust error handling.
*   **`db_utils.py`**: SQLite database operations for queue state and heuristic learning.
*   **`conversion_utils.py`**: Strategy and pipeline logic for processing movies and TV series.
*   **`movie_utils.py` & `tvseries_utils.py`**: Specialized logic for naming and metadata.
*   **`encoding_utils.py`**: FFmpeg QSV command generation, stream handling, and pipeline patterns.
*   **`email_utils.py`**: SMTP email notification logic.
*   **`logging_utils.py`**: Centralized logging logic.
*   **`metadata_utils.py`**: TMDB API integration.
*   **`tests/`**: Contains all unit and integration tests (`test_*.py`, `reproduce_*.py`).

---

## **Workflow**

1.  **Ingestion**: A file or folder path is added to `conversion.txt`.
2.  **Detection**: The worker reads the path and determines if it's a Movie or TV Series.
3.  **Preparation**:
    *   **Movies**: The folder is sanitized via TMDB lookup.
    *   **TV Series**: Season folders are standardized, and episodes are queued individually.
4.  **Processing (Per File)**:
    *   **Subtitle**: Extracted, converted to UTF-8, and character-corrected.
    *   **Video**: Transcoded to HEVC using Intel QSV hardware acceleration + VPP filtering.
    *   **Audio**: Downmixed to Stereo AAC.
5.  **Finalization**:
    *   The processed `.mp4` and `.srt` are moved to the target directory (`/share/...`).
    *   The original source file is deleted.
    *   Empty ancestor folders are removed.
    *   **On Failure**: An email is sent to the configured recipient with logs.

---

## **Logging & Monitoring**
*   **Centralized Logs**: All activities are logged to `/var/log/conversion`.
*   **Process Isolation**: Each conversion job generates a unique, timestamped log file (including PID) to prevent write conflicts and allow detailed debugging of specific files.
*   **Console Output**: Real-time status updates are printed to the console for monitoring the active worker.