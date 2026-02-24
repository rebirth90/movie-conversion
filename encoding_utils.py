"""
Encoder strategies and command builders for FFmpeg.
Implements the Strategy and Builder patterns for Domain-Driven Design.
"""

from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
import logging
import subprocess
import json
import datetime

from config import AppConfig
from models import MediaItem

logger = logging.getLogger(__name__)

def get_audio_streams(movie_file: Path, config: AppConfig) -> List[dict]:
    try:
        result = subprocess.run(
            [
                str(config.ffprobe_path),
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index,channels:stream_tags=language",
                "-of",
                "json",
                str(movie_file),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        probe_data = json.loads(result.stdout)
        audio_streams = []
        for stream in probe_data.get("streams", []):
            index = stream.get("index")
            channels = stream.get("channels", 2)
            lang = stream.get("tags", {}).get("language", "und").lower()
            audio_streams.append({"index": index, "channels": channels, "lang": lang})

        return audio_streams
    except Exception as e:
        logger.warning(f"Error extracting audio streams: {e}", exc_info=True)
        return []

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
        self._output_opts: List[str] = []
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

    def add_output_option(self, flag: str, value: str = ""):
        self._output_opts.append(flag)
        if value:
            self._output_opts.append(value)
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
        final_cmd.extend(self._output_opts)
        
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

        aspect_ratio = stream_info.width / stream_info.height
        # Note: AV1, VC1, MPEG2, and VP8 deliberately fall to hybrid mode based on Gen9.5 capabilities.
        profile_lower = str(stream_info.profile or "").lower()
        is_h264_10bit = (
            stream_info.codec_name == "h264" and
            ("high 10" in profile_lower or "10" in stream_info.pix_fmt)
        )
        is_hw_supported = (
            stream_info.codec_name in ["hevc", "h264", "vp9"] and
            stream_info.codec_name != "av1" and
            "high 4:4:4" not in profile_lower and
            not is_h264_10bit and
            "444" not in stream_info.pix_fmt and
            "422" not in stream_info.pix_fmt and
            stream_info.width == 1920 and
            stream_info.height == 1080
        )

        if stream_info.width > 1920:
            logger.warning("4K source detected. Forcing Hybrid Software Decode to perform 1080p downscale.")

        # Base hwaccel options
        if is_hw_supported:
            builder.add_global_option("-hwaccel", "qsv")
            builder.add_global_option("-qsv_device", self.config.qsv_device)
            builder.add_global_option("-hwaccel_output_format", "qsv")
        else:
            builder.add_global_option("-init_hw_device", f"qsv=hw:{self.config.qsv_device}")
            builder.add_global_option("-filter_hw_device", "hw")
        
        # HDR metadata preservation
        builder.add_video_option("-map_metadata", "0")

        # Smart fallback threading
        if not is_hw_supported:
            logger.info(f"PIPELINE: HYBRID (Software Decode -> Hardware Encode) [BF={bf}]")
            builder.add_global_option("-threads", "6")
        else:
            logger.info(f"PIPELINE: FULL HW (Hardware Decode -> Hardware Encode) [BF={bf}]")

        # Maximize thread queue size
        builder.add_global_option("-thread_queue_size", "4096")
        
        builder.add_input(str(media_item.source_path))

        # Standard maps
        builder.add_map("0:v:0")
        builder.add_video_option("-map_chapters", "-1")
        builder.add_video_option("-sn")
        builder.add_video_option("-dn")
        
        # Audio mapping
        audio_streams = get_audio_streams(media_item.source_path, self.config)
        for i, stream in enumerate(audio_streams):
            idx = stream.get('index')
            channels = stream.get('channels', 2)
            lang = stream.get('lang', 'und')
            builder.add_map(f"0:{idx}")
            builder.add_audio_option(f"-c:a:{i}", "aac")
            builder.add_audio_option(f"-ac:{i}", "2")
            builder.add_audio_option(f"-af:{i}", "aresample=ochl=stereo")
            if channels >= 6:
                builder.add_audio_option(f"-b:a:{i}", "256k")
            else:
                builder.add_audio_option(f"-b:a:{i}", "192k")
            builder.add_audio_option(f"-metadata:s:a:{i}", f"language={lang}")

        # --- FILTERS ---
        if not is_hw_supported and (stream_info.width != 1920 or stream_info.height != 1080):
            pad_filter = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
            builder.add_filter(pad_filter)
            sw_fmt = "p010le" if ('10' in stream_info.pix_fmt or 'p010' in stream_info.pix_fmt) else "nv12"
            builder.add_filter(f"format={sw_fmt},hwupload")
        elif not is_hw_supported:
            sw_fmt = "p010le" if ('10' in stream_info.pix_fmt or 'p010' in stream_info.pix_fmt) else "nv12"
            builder.add_filter(f"format={sw_fmt},hwupload")
        else:
            hw_format = "p010le" if ('10' in stream_info.pix_fmt or 'p010' in stream_info.pix_fmt) else "nv12"
            w_h = ""
            if stream_info.width != 1920 or stream_info.height != 1080:
                 w_h = ":w=1920:h=1080"
                 
            # Just use static high denoise since it's hardware
            denoise_level = self.config.qsv_denoise_level
            
            filter_parts = []
            if denoise_level > 0:
                filter_parts.append(f"denoise={denoise_level}")
            if w_h:
                filter_parts.append(w_h.lstrip(':'))
                
            if filter_parts:
                filter_parts.append(f"format={hw_format}")
                vpp_filter = f"vpp_qsv={':'.join(filter_parts)}"
                builder.add_filter(vpp_filter)

        # --- ENCODER OPTIONS ---
        builder.add_video_option("-c:v", "hevc_qsv")
        enc_profile = "main10" if ('10' in stream_info.pix_fmt or 'p010' in stream_info.pix_fmt) else "main"
        builder.add_video_option("-profile:v", enc_profile)
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
        builder.add_video_option("-g", "240")
        builder.add_video_option("-rc_mode", "icq")
        
        # Output options
        builder.add_output_option("-max_muxing_queue_size", "9999")
        builder.add_output_option("-avoid_negative_ts", "make_zero")

        # Output
        builder.set_output(str(temp_output))
        
        return builder

def execute_process(args: List[str], wait_for_completion: bool = True, config: Optional[AppConfig] = None, log_name: str = "ffmpeg") -> Optional[subprocess.Popen]:
    """Execute generic subprocess correctly."""
    log_file = None
    try:
        if config:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = config.log_ffmpeg_dir / f"{log_name}_{timestamp}.log"
            log_file = open(log_file_path, "w", encoding="utf-8")
            log_file.write(f"Start: {datetime.datetime.now()}\nCommand: {' '.join(str(a) for a in args)}\n" + "-"*80 + "\n")
            log_file.flush()
            proc = subprocess.Popen(args, stdout=log_file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
        else:
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True)
        
        if not wait_for_completion:
            proc.log_file = log_file
            return proc
            
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            if config:
                logger.error(f"Command failed. Check log at: {log_file_path}")
            else:
                logger.error(f"Command failed: {stderr}")
            if log_file:
                log_file.close()
            return None
            
        if log_file:
            log_file.close()
        return proc
    except Exception as e:
        if log_file:
            log_file.close()
        logger.exception(f"Failed to execute process: {e}")
        return None