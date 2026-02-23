import pytest
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

from conversion_utils import ProcessingPipeline
from exceptions import VRAMExhaustionError
from models import JobContext, MediaFactory, MediaType

def test_vram_exhaustion_step_down(dummy_media_item, in_memory_db, mock_config):
    context = JobContext(
        config=mock_config,
        db=in_memory_db,
        media_item=dummy_media_item,
        strategy=MagicMock()
    )
    
    pipeline = ProcessingPipeline(context)
    
    # Mock execute_process to throw VRAMExhaustionError ONCE, then succeed on retry.
    with patch('conversion_utils.execute_process') as mock_execute:
        def execute_side_effect(*args, **kwargs):
            if mock_execute.call_count == 1:
                raise VRAMExhaustionError("VRAM Low")
            
            # create the output file so the size validation passes
            temp_output = dummy_media_item.source_path.with_name(f"{dummy_media_item.clean_name()}_converted.mp4")
            temp_output.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_output, 'wb') as f:
                f.write(b'0' * 1024)
                
            mock_success = MagicMock()
            mock_success.returncode = 0
            return mock_success
            
        mock_execute.side_effect = execute_side_effect
        
        # Mocking time.sleep so the test doesn't actually wait
        with patch('time.sleep'):
            # The encoding step expects the encoder builder. Let's patch the encoder to return a dummy builder.
            dummy_builder = MagicMock()
            dummy_builder.build.return_value = ["ffmpeg", "-i", "dummy"]
            context.strategy.build_command.return_value = dummy_builder
            
            temp_output = Path("/tmp/dummy.mkv")
            
            # Executing the heuristic method
            pipeline._encode_video_with_heuristics()
            
            # The function should've executed twice
            assert mock_execute.call_count == 2
            
            # First call uses BEST, the second call steps down the tier list
            # We can verify it still didn't crash.

def test_target_exists_fast_fail(dummy_media_item, in_memory_db, mock_config):
    context = JobContext(
        config=mock_config,
        db=in_memory_db,
        media_item=dummy_media_item,
        strategy=MagicMock()
    )
    
    pipeline = ProcessingPipeline(context)
    
    with patch.object(Path, 'exists', return_value=True), \
         patch.object(Path, 'unlink') as mock_unlink:
        
        # The main pipeline run execution
        pipeline.run()
        
        # It should unlink both source files and fast return
        mock_unlink.assert_called()
        # Ensure it didn't call encode
        context.strategy.build_command.assert_not_called()
