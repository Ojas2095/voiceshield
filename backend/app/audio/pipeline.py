import dataclasses
import logging
from typing import Dict, List, Optional
import numpy as np

try:
    import torch
    import torchaudio
except ImportError:
    torch = None
    torchaudio = None

logger = logging.getLogger("voiceshield.audio")

SAMPLE_RATE = 16000
TELEPHONY_RATE = 8000
WINDOW_SAMPLES = 32000  # 2.0 seconds at 16kHz
HOP_SAMPLES = 8000      # 0.5 seconds (500ms) at 16kHz


@dataclasses.dataclass
class SpeechWindow:
    audio_data: np.ndarray  # float32 1D numpy array normalized to [-1, 1]
    window_start_ms: int
    window_end_ms: int


class TelephonySimulator:
    """
    Real DSP Telephony Simulator:
    16kHz input -> resample to 8kHz -> G.711 mu-law encode/decode -> subtle noise injection -> resample to 16kHz.
    """
    def __init__(self):
        if torchaudio is not None:
            self.resample_down = torchaudio.transforms.Resample(orig_freq=SAMPLE_RATE, new_freq=TELEPHONY_RATE)
            self.resample_up = torchaudio.transforms.Resample(orig_freq=TELEPHONY_RATE, new_freq=SAMPLE_RATE)
            self.mulaw_enc = torchaudio.transforms.MuLawEncoding(quantization_channels=256)
            self.mulaw_dec = torchaudio.transforms.MuLawDecoding(quantization_channels=256)
        else:
            self.resample_down = None
            self.resample_up = None
            self.mulaw_enc = None
            self.mulaw_dec = None

    def process(self, audio_tensor):
        if torchaudio is None or torch is None:
            return audio_tensor
        if audio_tensor.numel() == 0:
            return audio_tensor
        
        # Ensure 2D (1, num_samples) for torchaudio transforms
        if audio_tensor.ndim == 1:
            audio_tensor = audio_tensor.unsqueeze(0)
            
        try:
            # 1. Downsample to 8kHz telephony band
            telephony_audio = self.resample_down(audio_tensor)
            
            # 2. G.711 Mu-law quantization pass
            encoded = self.mulaw_enc(telephony_audio)
            decoded = self.mulaw_dec(encoded)
            
            # 3. Controlled noise injection (SNR ~ 30dB)
            noise_std = 0.005
            noise = torch.randn_like(decoded) * noise_std
            telephony_noisy = decoded + noise
            
            # 4. Upsample back to 16kHz
            processed = self.resample_up(telephony_noisy)
            return processed.squeeze(0)
        except Exception as e:
            logger.warning(f"Telephony DSP processing fallback: {e}")
            return audio_tensor.squeeze(0)


class SileroVADWrapper:
    """
    Wrapper around Silero VAD for speech activity gating.
    Loads once at startup with fallback to energy-based VAD if model download is restricted.
    """
    def __init__(self):
        self.model = None
        self._load_vad()

    def _load_vad(self):
        if torch is None:
            self.model = None
            return
        try:
            # Load silero vad from PyTorch Hub
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            self.model = model
            logger.info("Silero VAD model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load Silero VAD from PyTorch Hub ({e}). Using energy-based VAD fallback.")
            self.model = None

    def is_speech(self, audio_tensor, sample_rate: int = SAMPLE_RATE) -> bool:
        """
        Evaluate if a 2-second audio frame contains speech by processing in 512-sample chunks.
        """
        if torch is not None and self.model is not None and isinstance(audio_tensor, torch.Tensor):
            try:
                # Ensure 1D float32 tensor
                if audio_tensor.ndim > 1:
                    audio_tensor = audio_tensor.squeeze()
                
                chunk_size = 512
                num_samples = len(audio_tensor)
                probs = []

                # Reset VAD model internal state between independent window evaluations
                if hasattr(self.model, "reset_states"):
                    self.model.reset_states()

                for i in range(0, num_samples - chunk_size + 1, chunk_size):
                    chunk = audio_tensor[i:i+chunk_size]
                    prob = self.model(chunk, sample_rate).item()
                    probs.append(prob)

                if probs:
                    max_prob = max(probs)
                    avg_prob = sum(probs) / len(probs)
                    return max_prob >= 0.40 or avg_prob >= 0.30
            except Exception as e:
                logger.warning(f"Silero VAD inference error: {e}. Falling back to energy VAD.")
        
        # Energy-based VAD fallback
        if torch is not None and isinstance(audio_tensor, torch.Tensor):
            rms = torch.sqrt(torch.mean(audio_tensor ** 2)).item()
        else:
            rms = float(np.sqrt(np.mean(np.array(audio_tensor) ** 2)))
        return rms > 0.01


class AudioBufferState:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.samples_buffer = np.array([], dtype=np.float32)
        self.total_samples_received: int = 0
        self.processed_hop_index: int = 0  # track window hop offset


class AudioPipeline:
    """
    Per-call audio pipeline managing ring buffer, sliding 2s window / 500ms hop,
    telephony DSP pass, and Silero VAD gating.
    """
    def __init__(self):
        self.telephony_sim = TelephonySimulator()
        self.vad = SileroVADWrapper()
        self.buffers: Dict[str, AudioBufferState] = {}

    def process_frame(self, call_id: str, pcm_bytes: bytes) -> List[SpeechWindow]:
        """
        Processes incoming PCM bytes for call_id.
        Expected PCM format: 16kHz, mono, 16-bit int (or 32-bit float).
        Returns list of valid SpeechWindows.
        """
        if call_id not in self.buffers:
            self.buffers[call_id] = AudioBufferState(call_id)
        
        state = self.buffers[call_id]

        # Convert PCM bytes to float32 numpy array [-1.0, 1.0]
        # Check if bytes length aligns with 16-bit integer PCM (2 bytes/sample)
        if len(pcm_bytes) % 2 == 0:
            int_samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            float_samples = int_samples.astype(np.float32) / 32768.0
        elif len(pcm_bytes) % 4 == 0:
            float_samples = np.frombuffer(pcm_bytes, dtype=np.float32)
        else:
            logger.warning(f"Received misaligned PCM bytes length ({len(pcm_bytes)}) for call {call_id}")
            return []

        if len(float_samples) == 0:
            return []

        # Append incoming float samples to call ring buffer
        state.samples_buffer = np.concatenate([state.samples_buffer, float_samples])
        state.total_samples_received += len(float_samples)

        speech_windows: List[SpeechWindow] = []

        # Extract 2-second windows with 500ms hop
        while len(state.samples_buffer) >= WINDOW_SAMPLES:
            # Extract 2-second window
            raw_window = state.samples_buffer[:WINDOW_SAMPLES]
            
            # Compute window timestamps in milliseconds
            start_sample = state.total_samples_received - len(state.samples_buffer)
            end_sample = start_sample + WINDOW_SAMPLES
            
            start_ms = int((start_sample * 1000) / SAMPLE_RATE)
            end_ms = int((end_sample * 1000) / SAMPLE_RATE)

            if torch is not None:
                # Apply Telephony Simulation DSP pass
                tensor_win = torch.from_numpy(raw_window)
                telephony_win_tensor = self.telephony_sim.process(tensor_win)
                is_sp = self.vad.is_speech(telephony_win_tensor, SAMPLE_RATE)
                processed_np = telephony_win_tensor.detach().cpu().numpy() if isinstance(telephony_win_tensor, torch.Tensor) else raw_window
            else:
                is_sp = self.vad.is_speech(raw_window, SAMPLE_RATE)
                processed_np = raw_window

            # Run Silero VAD gating
            if is_sp:
                speech_windows.append(
                    SpeechWindow(
                        audio_data=processed_np,
                        window_start_ms=start_ms,
                        window_end_ms=end_ms
                    )
                )

            # Advance buffer by hop (500ms = HOP_SAMPLES)
            state.samples_buffer = state.samples_buffer[HOP_SAMPLES:]

        return speech_windows

    def cleanup_call(self, call_id: str) -> None:
        """
        Cleanup per-call audio buffer state on call disconnect.
        """
        if call_id in self.buffers:
            del self.buffers[call_id]
            logger.info(f"Cleaned up audio pipeline state for call_id={call_id}")


# Singleton instance of AudioPipeline
global_audio_pipeline = AudioPipeline()
