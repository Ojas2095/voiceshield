import { useCallback, useRef, useState } from 'react';

/**
 * useReplayStream — feeds a recorded audio file through the EXACT same path
 * the microphone uses: decode → resample to 16 kHz mono → 500 ms Int16 PCM
 * chunks → onAudioChunk() → WebSocket → backend telephony/VAD/window/model.
 *
 * There is NO fake animation and NO hardcoded score. The replay is a real
 * audio source; the backend produces the verdict. It exists as a reliable
 * stand-in for a live mic during demos, not as a scripted result.
 */
const TARGET_SR = 16000;
const CHUNK_MS = 500;
const SAMPLES_PER_CHUNK = (TARGET_SR * CHUNK_MS) / 1000; // 8000

export function useReplayStream(
  onAudioChunk: (chunk: ArrayBuffer) => void,
  onComplete?: () => void,
) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0); // 0..1
  const [level, setLevel] = useState(0);        // RMS of the last chunk (0..1)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsPlaying(false);
    setLevel(0);
  }, []);

  const start = useCallback(
    async (url: string) => {
      setError(null);
      setProgress(0);
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`Demo file not found: ${url} (${resp.status})`);
        const arrayBuf = await resp.arrayBuffer();

        // Decode, then resample to 16 kHz mono via an OfflineAudioContext.
        const AC: typeof AudioContext =
          (window as any).AudioContext || (window as any).webkitAudioContext;
        const decodeCtx = new AC();
        const decoded = await decodeCtx.decodeAudioData(arrayBuf.slice(0));
        decodeCtx.close();

        const frames = Math.max(1, Math.ceil(decoded.duration * TARGET_SR));
        const offline = new OfflineAudioContext(1, frames, TARGET_SR);
        const srcNode = offline.createBufferSource();
        srcNode.buffer = decoded;
        srcNode.connect(offline.destination);
        srcNode.start();
        const rendered = await offline.startRendering();
        const samples = rendered.getChannelData(0); // Float32 @ 16 kHz mono

        const totalChunks = Math.max(1, Math.ceil(samples.length / SAMPLES_PER_CHUNK));
        let chunkIndex = 0;
        setIsPlaying(true);

        // Emit one 500 ms chunk every 500 ms — mirrors a real-time call.
        timerRef.current = setInterval(() => {
          const startIdx = chunkIndex * SAMPLES_PER_CHUNK;
          if (startIdx >= samples.length) {
            stop();
            onComplete?.();
            return;
          }
          const slice = samples.subarray(startIdx, startIdx + SAMPLES_PER_CHUNK);
          const int16 = new Int16Array(SAMPLES_PER_CHUNK);
          let sumSq = 0;
          for (let i = 0; i < slice.length; i++) {
            const s = Math.max(-1, Math.min(1, slice[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            sumSq += s * s;
          }
          setLevel(Math.sqrt(sumSq / Math.max(slice.length, 1)));
          onAudioChunk(int16.buffer);

          chunkIndex += 1;
          setProgress(Math.min(chunkIndex / totalChunks, 1));
        }, CHUNK_MS);
      } catch (err) {
        console.error('[Replay] failed', err);
        const msg = err instanceof Error ? err.message : 'Failed to replay audio';
        setError(msg);
        stop();
        throw new Error(msg);
      }
    },
    [onAudioChunk, onComplete, stop],
  );

  return { isPlaying, error, progress, level, start, stop };
}
