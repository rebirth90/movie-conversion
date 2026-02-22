
import sys
from unittest.mock import patch

from pathlib import Path

# Add the current directory to the python path so we can import encoding_utils
sys.path.append(str(Path(__file__).parent.parent))

from encoding_utils import build_qsv_command

def test_mapping_logic():
    # Mock data simulating get_stream_info
    video_info = {
        "width": 1920,
        "height": 1080,
        "pix_fmt": "yuv420p",
        "codec_name": "h264",
        "profile": "High"
    }

    # Scenario 1: Standard layout (Video, Audio, Subtitle)
    # Stream 0: Video
    # Stream 1: Audio (jpn)
    # Stream 2: Subtitle
    audio_streams_1 = [{"index": 1, "channels": 2, "lang": "jpn"}]
    
    # Scenario 2: Hello World Case (Video, Audio, Subtitle, Audio, Subtitle)
    # Stream 0: Video
    # Stream 1: Audio 1 (TrueHD)
    # Stream 2: Subtitle
    # Stream 3: Audio 2 (AC3)
    audio_streams_2 = [
        {"index": 1, "channels": 8, "lang": "jpn"},
        {"index": 3, "channels": 6, "lang": "jpn"}
    ]

    # Scenario 3: Audio First (Audio, Video) - Rare but possible
    # Stream 0: Audio
    # Stream 1: Video
    audio_streams_3 = [{"index": 0, "channels": 2, "lang": "eng"}]

    with patch('encoding_utils.get_stream_info', return_value=video_info), \
         patch('encoding_utils.get_audio_streams', side_effect=[audio_streams_1, audio_streams_2, audio_streams_3]):
        
        print("--- Scenario 1: Standard ---")
        cmd1, _ = build_qsv_command("mock.mkv", "out.mp4")
        # Check for -map 0:1
        print(f"Contains '-map 0:1': {'-map' in cmd1 and '0:1' in cmd1}")
        
        print("\n--- Scenario 2: Interleaved (Hello World) ---")
        cmd2, _ = build_qsv_command("mock.mkv", "out.mp4")
        # Check for -map 0:1 and -map 0:3
        print(f"Contains '-map 0:1': {'-map' in cmd2 and '0:1' in cmd2}")
        print(f"Contains '-map 0:3': {'-map' in cmd2 and '0:3' in cmd2}")
        print(f"Does NOT contain '-map 0:a:2': {'0:a:2' not in cmd2}")

        print("\n--- Scenario 3: Audio First ---")
        cmd3, _ = build_qsv_command("mock.mkv", "out.mp4")
        # Check for -map 0:0
        print(f"Contains '-map 0:0': {'-map' in cmd3 and '0:0' in cmd3}")

        # Scenario 4: Kimi.wa.na Case (Video, Audio, Audio, Subtitle)
        # Stream 0: Video
        # Stream 1: Audio 1
        # Stream 2: Audio 2
        # Stream 3: Subtitle
        audio_streams_4 = [
             {"index": 1, "channels": 6, "lang": "jpn"},
             {"index": 2, "channels": 2, "lang": "eng"}
        ]
        
    with patch('encoding_utils.get_stream_info', return_value=video_info), \
         patch('encoding_utils.get_audio_streams', side_effect=[audio_streams_1, audio_streams_2, audio_streams_3, audio_streams_4]):
        
        # ... (Previous validations) ...
        
        print("\n--- Scenario 4: Kimi.wa.na (Standard Multi-Audio) ---")
        cmd4, _ = build_qsv_command("mock.mkv", "out.mp4")
        print(f"Contains '-map 0:1' (Audio 1): {'-map' in cmd4 and '0:1' in cmd4}")
        print(f"Contains '-map 0:2' (Audio 2): {'-map' in cmd4 and '0:2' in cmd4}")


if __name__ == "__main__":
    test_mapping_logic()
