"""
Video processing pipeline execution logic.
Orchestrates Domain Models, Strategies, and Database heuristics for robust conversions.
"""

import logging
from pathlib import Path
import shutil
import time

from models import JobContext, EncodingTier
from encoding_utils import execute_process
from subtitle_utils import process_subtitle
from exceptions import VideoEncodingError, VRAMExhaustionError

logger = logging.getLogger(__name__)

class ProcessingPipeline:
    """Enterprise OOP Pipeline for media processing."""
    def __init__(self, context: JobContext):
        self.context = context

    def run(self) -> Path:
        """Executes the conversion pipeline."""
        logger.info(f"=== PIPELINE STARTED: {self.context.media_item.clean_name()} ===")
        
        # 1. Extract Subtitles
        subtitle_path = self._extract_subtitles()
        
        # 2. Encode Video
        encoded_file = self._encode_video_with_heuristics()
        
        # 3. Relocate
        final_dir = self._relocate(encoded_file, subtitle_path)
        
        logger.info(f"=== PIPELINE SUCCESS: {final_dir} ===")
        return final_dir

    def _extract_subtitles(self) -> Path:
        """Handles subtitle extraction and standardization."""
        logger.info("-- PHASE: Subtitle Extraction --")
        try:
            sub = process_subtitle(self.context.media_item.source_path, self.context.media_item.clean_name())
            if not sub:
                logger.warning("No subtitle processed. Continuing with video only.")
                return None
                
            logger.info(f"Subtitle processed: {sub.name}")
            return sub
        except Exception as e:
            logger.error(f"Subtitle processing failed: {e}")
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
            EncodingTier(bf=4, lad=20, async_depth=4, desc="Balanced (Medium VRAM)"),
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
            valid_tiers = []
            for t in tiers:
                if t['bf'] <= best_bf and t['lad'] <= best_lad:
                    valid_tiers.append(t)
            
            if valid_tiers:
                 tiers = valid_tiers
            else:
                 # If heuristics map to something weirder than tiers, inject it as top tier
                 tiers.insert(0, EncodingTier(bf=best_bf, lad=best_lad, async_depth=best_async, desc="Heuristic Model"))

        temp_output = self.context.media_item.source_path.with_name(f"{self.context.media_item.clean_name()}_converted.mp4")

        for attempt in tiers:
            logger.info(f"ATTEMPT: {attempt.desc} -> bf={attempt.bf}, lad={attempt.lad}")
            
            builder = self.context.strategy.build_command(
                self.context.media_item, temp_output, 
                bf=attempt.bf, lad=attempt.lad, async_depth=attempt.async_depth
            )
            
            cmd = builder.build()
            
            try:
                proc = execute_process(cmd, wait_for_completion=True)
                if proc is None:
                    raise VRAMExhaustionError("Process returned None (Likely VRAM crash)")
                
                # Verify file
                if not temp_output.exists() or temp_output.stat().st_size < 1000:
                     raise VideoEncodingError("Output file missing or empty")
                     
                logger.info(f"Encoding successful on tier: {attempt['desc']}")
                
                # Save success heuristics cleanly
                if s_info:
                    self.context.db.save_successful_profile(
                        s_info.width, s_info.height, s_info.codec_name, s_info.pix_fmt,
                        attempt.bf, attempt.lad, attempt.async_depth
                    )
                return temp_output

            except VRAMExhaustionError as e:
                logger.warning(f"Hardware limits exceeded: {e}. Stepping down.")
                if temp_output.exists():
                     temp_output.unlink(missing_ok=True)
                time.sleep(2) # Cooldown HW
                continue
            except Exception as e:
                logger.error(f"Encoding failed: {e}")
                if temp_output.exists():
                     temp_output.unlink(missing_ok=True)
                raise VideoEncodingError(f"Fatal encode error: {e}")

        # If loop exhausts
        raise VideoEncodingError("All encoding memory tiers failed.")

    def _relocate(self, encoded_file: Path, subtitle_file: Path) -> Path:
        """Moves fully processed artifacts exactly into their target Domain structure."""
        logger.info("-- PHASE: Relocation --")
        
        target_root = self.context.media_item.target_directory()
        final_dir = target_root / self.context.media_item.clean_name()
        final_dir.mkdir(parents=True, exist_ok=True)
        
        # Move video
        final_video_path = final_dir / encoded_file.name
        shutil.move(str(encoded_file), str(final_video_path))
        
        # Move subtitle if exists
        if subtitle_file and subtitle_file.exists():
             final_sub_path = final_dir / subtitle_file.name
             shutil.move(str(subtitle_file), str(final_sub_path))
             
        # Cleanup original source video to save space
        if not self.context.media_item.source_path.exists():
             return final_dir
             
        self.context.media_item.source_path.unlink()
        return final_dir