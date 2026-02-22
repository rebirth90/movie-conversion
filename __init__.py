#!/usr/bin/env python3

"""
Movie and TV Series Conversion System

A comprehensive system for converting movies and TV series with:
- VAAPI HEVC encoding (hardware accelerated)
- Subtitle extraction and processing
- LibreTranslate integration for English subtitle translation
- Queue-based batch processing
- Support for TV series (full seasons and single episodes)

Version: 2.1
Author: Homelab Media Automation
"""

__version__ = "2.1.0"

__all__ = [
    "config",
    "file_utils",
    "tvseries_utils",
    "core",
    "subtitle_utils",
    "conversion_utils",
    "encoding_utils",
    "logging_utils",
    "main",
    "movie_utils",
    "email_utils",
    "metadata_utils",
    "db_utils",
    "exceptions",
    "models"
]