
import sys

from pathlib import Path

# Add the parent directory to the python path so we can import encoding_utils
sys.path.append(str(Path(__file__).parent.parent))

from encoding_utils import is_hw_decode_supported

def test_hw_decode_support():
    # Test case 1: H.264 4:2:0 (Standard) - Should be True
    case1 = {
        "codec_name": "h264",
        "profile": "High",
        "pix_fmt": "yuv420p"
    }
    
    # Test case 2: H.264 4:4:4 (The problematic file) - Should be False
    case2 = {
        "codec_name": "h264",
        "profile": "High 4:4:4 Predictive",
        "pix_fmt": "yuv444p"
    }

    # Test case 3: H.264 4:2:2 - Should be False
    case3 = {
        "codec_name": "h264",
        "profile": "High 4:2:2",
        "pix_fmt": "yuv422p"
    }

    # Test case 4: H.264 10-bit - Should be False (Existing check)
    case4 = {
        "codec_name": "h264",
        "profile": "High 10",
        "pix_fmt": "yuv420p10le"
    }
    
    print(f"Case 1 (H.264 4:2:0): {is_hw_decode_supported(case1)} (Expected: True)")
    print(f"Case 2 (H.264 4:4:4): {is_hw_decode_supported(case2)} (Expected: False)")
    print(f"Case 3 (H.264 4:2:2): {is_hw_decode_supported(case3)} (Expected: False)")
    print(f"Case 4 (H.264 10-bit): {is_hw_decode_supported(case4)} (Expected: False)")

if __name__ == "__main__":
    test_hw_decode_support()
