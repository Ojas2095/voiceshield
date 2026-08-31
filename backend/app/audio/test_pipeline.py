"""
Audio Pipeline Verification Script
Tests silence, short clip (<2s), continuous speech, background noise.
Includes TODO for accented/Hinglish audio testing.
"""

import numpy as np
from backend.app.audio.pipeline import AudioPipeline, SAMPLE_RATE, WINDOW_SAMPLES, HOP_SAMPLES


def run_pipeline_tests():
    pipeline = AudioPipeline()
    call_id = "test-audio-call-123"

    print("Running Audio Pipeline Tests...")

    # 1. Silence Test
    silence_pcm = np.zeros(16000, dtype=np.int16).tobytes()
    windows = pipeline.process_frame(call_id, silence_pcm)
    assert len(windows) == 0, f"Expected 0 windows for 1s silence, got {len(windows)}"
    print("[PASS] Silence test passed (no speech windows emitted).")

    # 2. Short Clip (<2s)
    short_speech = (np.sin(2 * np.pi * 440 * np.arange(8000) / SAMPLE_RATE) * 10000).astype(np.int16).tobytes()
    windows = pipeline.process_frame(call_id, short_speech)
    assert len(windows) == 0, f"Expected 0 windows for total 1.5s audio (<2s), got {len(windows)}"
    print("[PASS] Short clip (<2s) test passed (buffered, waiting for 2s window).")

    # 3. Continuous Speech (3 seconds total accumulated audio)
    t = np.arange(24000) / SAMPLE_RATE
    continuous_signal = (
        np.sin(2 * np.pi * 300 * t) + 
        0.5 * np.sin(2 * np.pi * 600 * t) +
        0.25 * np.sin(2 * np.pi * 1200 * t)
    ) * 12000
    speech_pcm = continuous_signal.astype(np.int16).tobytes()
    windows = pipeline.process_frame(call_id, speech_pcm)
    assert len(windows) >= 1, f"Expected at least 1 window for 3s audio, got {len(windows)}"
    print(f"[PASS] Continuous speech test passed ({len(windows)} window(s) processed with VAD).")
    for w in windows:
        print(f"  - Window: [{w.window_start_ms}ms - {w.window_end_ms}ms], len={len(w.audio_data)}")

    # 4. Background Noise Test
    pipeline.cleanup_call(call_id)
    noise = (np.random.randn(32000) * 100).astype(np.int16).tobytes()
    noise_windows = pipeline.process_frame(call_id, noise)
    assert len(noise_windows) == 0, "Low amplitude background noise should be filtered out by VAD"
    print("[PASS] Background noise test passed (filtered out low-amplitude noise).")

    # Cleanup
    pipeline.cleanup_call(call_id)
    print("All Audio Pipeline Tests Passed Cleanly!")


# TODO (Team Integration): Add test runner with real team-recorded Hinglish / accented audio clips.


if __name__ == "__main__":
    run_pipeline_tests()
