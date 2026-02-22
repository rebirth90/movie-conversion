
def reproduce_mapping_logic():
    # Simulation of get_audio_streams return value for "Hello World 2019"
    # Stream #0:1 -> Audio
    # Stream #0:3 -> Audio
    audio_streams = [
        {"index": 1, "channels": 8, "lang": "jpn"},
        {"index": 3, "channels": 6, "lang": "jpn"}
    ]

    print("Current Logic Output:")
    for i, stream in enumerate(audio_streams):
        idx = stream["index"]
        # The flawed logic from encoding_utils.py
        map_arg = f"0:a:{idx - 1 if idx > 0 else 0}"
        print(f"Stream Index {idx} -> Maps to: {map_arg}")
        
    print("\nExpected/Correct Behavior:")
    print("Stream Index 1 -> Should map to: 0:1 (Absolute) or 0:a:0 (Relative)")
    print("Stream Index 3 -> Should map to: 0:3 (Absolute) or 0:a:1 (Relative)")

if __name__ == "__main__":
    reproduce_mapping_logic()
