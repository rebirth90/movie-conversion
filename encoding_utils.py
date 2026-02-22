"""
Encoder strategies and command builders for FFmpeg.
Implements the Strategy and Builder patterns for Domain-Driven Design.
"""

from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
import logging

from config import AppConfig
from models import MediaItem

logger = logging.getLogger(__name__)

class FFmpegCommandBuilder:
    """Builder pattern for constructing FFmpeg commands cleanly."""
    
    def __init__(self, config: AppConfig):
        self._cmd: List[str] = [str(config.ffmpeg_path), "-y"]
        self._inputs: List[str] = []
        self._filters: List[str] = []
        self._maps: List[str] = []
        self._video_opts: List[str] = []
        self._audio_opts: List[str] = []
        self._global_opts: List[str] = []
        self._output: str = ""

    def add_global_option(self, flag: str, value: str = ""):
        self._global_opts.append(flag)
        if value:
            self._global_opts.append(value)
        return self

    def add_input(self, input_path: str):
        self._inputs.extend(["-i", input_path])
        return self

    def add_map(self, map_val: str):
        self._maps.extend(["-map", map_val])
        return self

    def add_filter(self, filter_str: str):
        self._filters.append(filter_str)
        return self

    def add_video_option(self, flag: str, value: str = ""):
        self._video_opts.append(flag)
        if value:
            self._video_opts.append(value)
        return self

    def add_audio_option(self, flag: str, value: str = ""):
        self._audio_opts.append(flag)
        if value:
            self._audio_opts.append(value)
        return self

    def set_output(self, output_path: str):
        self._output = output_path
        return self

    def build(self) -> List[str]:
        final_cmd = self._cmd.copy()
        final_cmd.extend(self._global_opts)
        final_cmd.extend(self._inputs)
        final_cmd.extend(self._maps)
        
        if self._filters:
            # Join multiple filters with comma
            final_cmd.extend(["-vf", ",".join(self._filters)])
            
        final_cmd.extend(self._video_opts)
        final_cmd.extend(self._audio_opts)
        
        if not self._output:
            raise ValueError("Output path not set for FFmpegCommandBuilder")
            
        final_cmd.append(self._output)
        return final_cmd


class EncoderStrategy(ABC):
    """Abstract Strategy for encoding video to HEVC."""
    def __init__(self, config: AppConfig):
        self.config = config

    @abstractmethod
    def build_command(self, media_item: MediaItem, temp_output: Path, bf: int, lad: int, async_depth: int) -> FFmpegCommandBuilder:
        """Construct the FFmpeg encoding command."""
        pass


class IntelQSVStrategy(EncoderStrategy):
    """Concrete Strategy maximizing Intel Gen9.5 QSV hardware acceleration."""

    def build_command(self, media_item: MediaItem, temp_output: Path, bf: int, lad: int, async_depth: int) -> FFmpegCommandBuilder:
        builder = FFmpegCommandBuilder(self.config)
        stream_info = media_item.stream_info
        
        if not stream_info:
            raise ValueError("Stream info missing from MediaItem")

        # Determine Hardware Pipeline capabilities
        is_hw_supported = (
            stream_info.codec_name in ["hevc", "h264", "vp9"] and 
            stream_info.profile != "high 4:4:4 predictive" and 
            stream_info.profile != "high 10"
        )

        # Base hwaccel options
        builder.add_global_option("-hwaccel", "qsv")
        builder.add_global_option("-qsv_device", self.config.qsv_device)
        builder.add_global_option("-hwaccel_output_format", "qsv")

        # Smart fallback threading
        if not is_hw_supported:
            logger.info(f"PIPELINE: HYBRID (Software Decode -> Hardware Encode) [BF={bf}]")
            builder.add_global_option("-threads", "6")

        # Maximize thread queue size
        builder.add_global_option("-thread_queue_size", "4096")
        
        builder.add_input(str(media_item.source_path))

        # Standard maps
        builder.add_map("0:v:0")
        builder.add_map("-1") # Discard chapters
        
        # Audio mapping
        for track in getattr(media_item, 'audio_tracks', []):
            builder.add_map(f"0:{track}")

        # --- FILTERS ---
        hw_format = "p010" # Forced 10-bit Squeeze
        w_h = ""
        if stream_info.width != 1920 or stream_info.height != 1080:
             w_h = ":w=1920:h=1080"
             
        # Just use static high denoise since it's hardware
        denoise_level = 15
        
        filter_parts = []
        if denoise_level > 0:
            filter_parts.append(f"denoise={denoise_level}")
        if w_h:
            filter_parts.append(w_h.lstrip(':'))
            
        filter_parts.append(f"format={hw_format}")
        
        vpp_filter = f"vpp_qsv={':'.join(filter_parts)}"
        builder.add_filter(vpp_filter)

        # --- ENCODER OPTIONS ---
        builder.add_video_option("-c:v", "hevc_qsv")
        builder.add_video_option("-profile:v", "main10") # Forced Squeeze
        builder.add_video_option("-level:v", "5.1")
        builder.add_video_option("-preset", "veryslow")
        builder.add_video_option("-global_quality", str(self.config.global_quality_default))
        builder.add_video_option("-b:v", "0")
        
        # QSV Customizations
        builder.add_video_option("-look_ahead", "1")
        builder.add_video_option("-look_ahead_depth", str(lad))
        builder.add_video_option("-async_depth", str(async_depth))
        
        # Golden standard controls
        builder.add_video_option("-bf", str(bf))
        builder.add_video_option("-b_strategy", "1")
        builder.add_video_option("-g", "600")
        builder.add_video_option("-mbbrc", "1")
        builder.add_video_option("-rc_mode", "icq")
        builder.add_video_option("-max_muxing_queue_size", "9999")
        builder.add_video_option("-avoid_negative_ts", "make_zero")

        # Output
        builder.set_output(str(temp_output))
        
        return builder

def execute_process(args: List[str], wait_for_completion: bool = True):
    """Execute generic subprocess correctly."""
    import subprocess
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        
        if not wait_for_completion:
            return proc
            
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            logger.error(f"Command failed: {stderr}")
            return None
            
        return proc
    except Exception as e:
        logger.error(f"Subprocess Execution Error: {e}")
        return None