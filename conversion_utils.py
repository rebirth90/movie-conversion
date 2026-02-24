"""
Video processing pipeline execution logic.
Orchestrates Domain Models, Strategies, and Database heuristics for robust conversions.
"""

import logging
from pathlib import Path
import glob
from typing import Optional
import threading

from models import JobContext, EncodingTier
from file_utils import linux_mv
from encoding_utils import execute_process
from subtitle_utils import process_subtitle
from exceptions import VideoEncodingError, VRAMExhaustionError, ShutdownRequestedError

logger = logging.getLogger(__name__)

class ProcessingPipeline:
    """Enterprise OOP Pipeline for media processing."""
    def __init__(self, context: JobContext):
        self.context = context

    def run(self) -> Optional[Path]:
        """Executes the conversion pipeline."""
        logger.info(f"=== PIPELINE STARTED: {self.context.media_item.source_path.name} ===")
        
        # Fast-fail if target already exists
        try:
            final_dir = self.context.media_item.compute_final_directory()
        except ValueError as e:
            logger.error(f"Cannot compute target path to check for existence: {e}")
            return None
            
        expected_mp4 = f"{self.context.media_item.clean_name()}.mp4"
        check_path = final_dir / expected_mp4
            
        if check_path.exists():
            logger.warning(f"TARGET_EXISTS: {check_path.name}. Skipping conversion.")
            # Clean up associated subtitles to prevent orphans using glob
            source_dir = self.context.media_item.source_path.parent
            clean = self.context.media_item.clean_name()
            for ext in ['srt', 'sub', 'idx', 'ass', 'vtt', 'sup']:
                for orphan in source_dir.glob(f"{clean}*.{ext}"):
                    orphan.unlink(missing_ok=True)
                    
            # Fallback for exact source name match
            for ext in ['.srt', '.sub', '.idx', '.ass']:
                sub_file = self.context.media_item.source_path.with_suffix(ext)
                sub_file.unlink(missing_ok=True)
            self.context.media_item.cleanup_source_directory(logger, final_dir)
            return check_path.parent
        
        # --- PHASE 1: Subtitle Extraction ---
        subtitle_path = self._extract_subtitles()
        
        # 2. Encode Video
        encoded_file = self._encode_video_with_heuristics()
        
        # 3. Relocate
        final_dir = self._relocate(encoded_file, subtitle_path)
        if not final_dir:
            return None
            
        logger.info(f"=== PIPELINE SUCCESS: {final_dir} ===")
        return final_dir

    def _extract_subtitles(self) -> Path:
        """Handles subtitle extraction and standardization."""
        logger.info("-- PHASE: Subtitle Extraction --")
        try:
            sub = process_subtitle(self.context.media_item.source_path, self.context.media_item.clean_name(), self.context.config, self.context.shutdown_event)
            if not sub:
                logger.warning("No subtitle processed. Continuing with video only.")
                return None
                
            logger.info(f"Subtitle processed: {sub.name}")
            return sub
        except Exception as e:
            logger.warning(f"Subtitle processing failed: {e}", exc_info=True)
            # Continuing since subtitle failure is non-fatal usually
            return None

    def _encode_video_with_heuristics(self) -> Path:
        """
        Executes hardware encode using tiered memory logic from DatabaseManager heuristics.
        Steps down smoothly upon VRAMExhaustionError.
        """
        logger.info("-- PHASE: Video Encoding --")
        # Define base tiers
        tiers = [
            EncodingTier(bf=7, lad=40, async_depth=8, desc="Max Quality (High VRAM)"),
            EncodingTier(bf=4, lad=20, async_depth=4, desc="Balanced (Start Here)"),
            EncodingTier(bf=0, lad=10, async_depth=2, desc="Safe Mode (Low VRAM)")
        ]

        # Filter by heuristic if previously defined
        s_info = self.context.media_item.stream_info
        best_profile = None
        if s_info:
            best_profile = self.context.db.get_best_profile(
                s_info.width, s_info.height, s_info.codec_name, s_info.pix_fmt
            )
            
        if best_profile:
            best_bf, best_lad, best_async = best_profile
            logger.info(f"Loaded heuristics from DB: {best_bf}bf, {best_lad}lad")
            # Filter out tiers strictly more aggressive than the known best
            valid_tiers = [t for t in tiers if t.bf <= best_bf and t.lad <= best_lad]
            
            if valid_tiers:
                 tiers = valid_tiers
            else:
                 # If heuristics map to something weirder than tiers, inject it as top tier
                 tiers.insert(0, EncodingTier(bf=best_bf, lad=best_lad, async_depth=best_async, desc="Heuristic Model"))

        temp_output = self.context.media_item.source_path.with_name(f"{self.context.media_item.clean_name()}_temp.mp4")

        for attempt in tiers:
            if self.context.shutdown_event and self.context.shutdown_event.is_set():
                logger.info("Shutdown event detected. Breaking encode loop.")
                raise ShutdownRequestedError("Shutdown requested during execution.")
                
            logger.info(f"ATTEMPT: {attempt.desc} -> bf={attempt.bf}, lad={attempt.lad}")
            
            builder = self.context.strategy.build_command(
                self.context.media_item, temp_output, 
                bf=attempt.bf, lad=attempt.lad, async_depth=attempt.async_depth
            )
            
            cmd = builder.build()
            
            try:
                proc = execute_process(cmd, wait_for_completion=True, config=self.context.config, log_name=self.context.media_item.clean_name())
                if proc is None:
                    # Check recent log for memory strings
                    is_vram = False
                    if self.context.config.log_ffmpeg_dir.exists():
                        safe_log_name = glob.escape(self.context.media_item.clean_name())
                        candidates = list(self.context.config.log_ffmpeg_dir.glob(f"*{safe_log_name}*.log"))
                        if candidates:
                            newest_log = max(candidates, key=lambda p: p.stat().st_mtime)
                            with open(newest_log, 'r', errors='ignore') as f:
                                content = f.read().lower()
                                if any(x in content for x in ["mfx_err_memory_alloc", "mfxerr_memory_alloc", "not enough surfaces", "out of memory", "allocation failed", "cannot allocate memory"]):
                                    is_vram = True
                                    
                    if is_vram:
                        raise VRAMExhaustionError("Process returned None (Likely VRAM crash)")
                    else:
                        raise VideoEncodingError("Process returned None (Generic FFmpeg crash)")
                
                # Verify file
                if not temp_output.exists() or temp_output.stat().st_size < 1000:
                     raise VideoEncodingError("Output file missing or empty")
                     
                logger.info(f"Encoding successful on tier: {attempt.desc}")
                
                # Save success heuristics cleanly
                if s_info:
                    self.context.db.save_successful_profile(
                        s_info.width, s_info.height, s_info.codec_name, s_info.pix_fmt,
                        attempt.bf, attempt.lad, attempt.async_depth
                    )
                return temp_output

            except (VRAMExhaustionError, VideoEncodingError) as e:
                logger.warning(f"Hardware limits exceeded: {e}. Stepping down.")
                if temp_output.exists():
                     temp_output.unlink(missing_ok=True)
                if self.context.shutdown_event:
                    self.context.shutdown_event.wait(2)
                else:
                    threading.Event().wait(2)  # Cooldown HW
                continue
            except Exception as e:
                logger.exception(f"Encoding failed: {e}")
                if temp_output.exists():
                     temp_output.unlink(missing_ok=True)
                raise VideoEncodingError(f"Fatal encode error: {e}")

        # If loop exhausts
        raise VideoEncodingError("All encoding memory tiers failed.")

    def _relocate(self, encoded_file: Path, subtitle_file: Path) -> Path:
        """Moves fully processed artifacts exactly into their target Domain structure."""
        logger.info("-- PHASE: Relocation --")
        
        try:
            final_dir = self.context.media_item.compute_final_directory()
            final_dir.mkdir(parents=True, exist_ok=True)
        except ValueError as e:
            logger.error(f"Path resolution error during relocation: {e}")
            raise ValueError(f"Relocation failed (outside specific base root): {e}")
        
        # Move video
        final_video_path = final_dir / f"{self.context.media_item.clean_name()}.mp4"
        linux_mv(encoded_file, final_video_path, self.context.shutdown_event)
        
        # Move subtitle if exists
        if subtitle_file and subtitle_file.exists():
             final_sub_path = final_dir / subtitle_file.name
             linux_mv(subtitle_file, final_sub_path, self.context.shutdown_event)
             
             if subtitle_file.suffix.lower() == '.sub':
                 idx_file = subtitle_file.with_suffix('.idx')
                 if idx_file.exists():
                     final_idx_path = final_dir / idx_file.name
                     linux_mv(idx_file, final_idx_path, self.context.shutdown_event)
             
        # Cleanup original source video to save space
        self.context.media_item.cleanup_source_directory(logger, final_dir)
            
        return final_dir