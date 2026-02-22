"""
Custom exceptions for the video conversion domain.
"""

class ConversionError(Exception):
    """Base exception for all conversion-related errors."""
    pass

class VideoEncodingError(ConversionError):
    """Raised when the video encoding process fails."""
    pass

class SubtitleExtractionError(ConversionError):
    """Raised when subtitle extraction or conversion fails."""
    pass

class VRAMExhaustionError(VideoEncodingError):
    """Raised specifically when hardware encoding fails due to VRAM exhaustion."""
    pass

class MediaValidationError(ConversionError):
    """Raised when media validation fails (e.g., missing stream info)."""
    pass
