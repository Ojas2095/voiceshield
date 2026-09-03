/**
 * useVoiceShield — the single integration layer between the console UI and
 * backend_v2. Supports two real audio sources that both flow through the
 * identical pipeline (WS → telephony → VAD → windows → model → fusion):
 *
 *   startLive()            → mic (AudioWorklet)     source="mic"
 *   startReplay(url,label) → recorded demo file     source="replay"
 *
 * No source produces a scripted result — the backend decides the verdict.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMicStream } from './useMicStream';
import { useReplayStream } from './useReplayStream';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Verdict = 'REAL' | 'SUSPICIOUS' | 'FRAUD' | 'WAITING';
export type Source = 'mic' | 'replay' | null;

export interface ShieldData {
  verdict: Verdict;
  riskScore: number;          // fused risk 0..100
  spoofProbability: number;   // Layer-1 P(fake) 0..100
  layers: { voice: number; intent: number; signal: number };
  reasons: string[];
  vadActive: boolean;
  gradcam: string | null;     // base64 PNG
}

export interface EventLog {
  t: string;
  risk: number;
  verdict: string;
}

export interface HoldInfo {
  reference: string;
  risk: number;
  at: string;
}

const EMPTY: ShieldData = {
  verdict: 'WAITING',
  riskScore: 0,
  spoofProbability: 0,
  layers: { voice: 0, intent: 0, signal: 0 },
  reasons: [],
  vadActive: false,
  gradcam: null,
};

const WAVE_LEN = 72;      // waveform bars retained
const HISTORY_LEN = 90;   // risk-timeline points retained

export function useVoiceShield() {
  const [source, setSource] = useState<Source>(null);
  const [replaySample, setReplaySample] = useState<string | null>(null);
  const [data, setData] = useState<ShieldData>(EMPTY);
  const [logs, setLogs] = useState<EventLog[]>([]);
  const [riskHistory, setRiskHistory] = useState<number[]>([]);
  const [waveform, setWaveform] = useState<number[]>(Array(WAVE_LEN).fill(0));
  const [level, setLevel] = useState(0);
  const [hold, setHold] = useState<HoldInfo | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const callIdRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ── PCM chunk handler shared by mic + replay ──────────────────────────────
  const handleAudioChunk = useCallback((chunk: ArrayBuffer) => {
    // Uniform audio level for the waveform, computed from the actual PCM.
    const view = new Int16Array(chunk);
    let sumSq = 0;
    for (let i = 0; i < view.length; i++) {
      const s = view[i] / 32768;
      sumSq += s * s;
    }
    const rms = Math.sqrt(sumSq / Math.max(view.length, 1));
    setLevel(rms);
    setWaveform((prev) => [...prev.slice(1), Math.min(rms * 3, 1)]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(chunk);
    }
  }, []);

  const mic = useMicStream(handleAudioChunk);
  const finishRef = useRef<() => void>(() => {});
  const replay = useReplayStream(handleAudioChunk, () => finishRef.current());

  // ── Backend REST ──────────────────────────────────────────────────────────
  const startCall = useCallback(async (src: 'mic' | 'replay'): Promise<string> => {
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/calls/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: src }),
      });
    } catch {
      throw new Error('Cannot reach the backend on port 8000 — is it running?');
    }
    if (!res.ok) throw new Error(`Backend error starting call (HTTP ${res.status}).`);
    const json = await res.json();
    return json.call_id as string;
  }, []);

  const endCall = useCallback(async (callId: string) => {
    try {
      await fetch(`${API_BASE}/api/calls/${callId}/stop`, { method: 'POST' });
    } catch {
      /* non-fatal */
    }
  }, []);

  // ── WebSocket ──────────────────────────────────────────────────────────────
  const connectWS = useCallback((callId: string) => {
    const proto = API_BASE.startsWith('https') ? 'wss:' : 'ws:';
    const host = API_BASE.replace(/^https?:\/\//, '');
    const ws = new WebSocket(`${proto}//${host}/ws/stream/${callId}`);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => setStatus(null);
    ws.onerror = () => setStatus('Connection issue — is the backend running on :8000?');
    ws.onclose = () => {
      wsRef.current = null;
    };

    ws.onmessage = (event) => {
      let msg: any;
      try {
        msg = JSON.parse(event.data as string);
      } catch {
        return;
      }
      switch (msg.type) {
        case 'risk_update': {
          const risk = Math.round((msg.fused_risk_score ?? 0) * 100);
          setData((prev) => ({
            verdict: msg.verdict ?? prev.verdict,
            riskScore: risk,
            spoofProbability: Math.round((msg.spoof_probability ?? 0) * 100),
            layers: {
              voice: Math.round((msg.spoof_probability ?? 0) * 100),
              intent: Math.round((msg.intent_risk ?? 0) * 100),
              signal: Math.round((msg.call_signal_risk ?? 0) * 100),
            },
            reasons: msg.matched_reasons?.length ? msg.matched_reasons : prev.reasons,
            vadActive: msg.vad_active ?? prev.vadActive,
            gradcam: msg.gradcam_png_b64 ?? prev.gradcam,
          }));
          setRiskHistory((prev) => [...prev, risk].slice(-HISTORY_LEN));
          if (msg.verdict && msg.verdict !== 'WAITING') {
            setLogs((prev) =>
              [{ t: new Date().toLocaleTimeString(), risk, verdict: msg.verdict }, ...prev].slice(0, 12),
            );
          }
          break;
        }
        case 'vad_update':
          setData((prev) => ({ ...prev, vadActive: msg.vad_active }));
          break;
        case 'hold_triggered':
          setHold({
            reference: msg.mock_reference ?? 'VS-HOLD',
            risk: data.riskScore || 85,
            at: new Date(msg.triggered_at ?? Date.now()).toLocaleTimeString(),
          });
          break;
        case 'error':
          setStatus(msg.detail ?? 'Server error');
          break;
        default:
          break;
      }
    };
    wsRef.current = ws;
  }, []);

  // ── Teardown (optionally keep the last results on screen) ──────────────────
  const teardown = useCallback(
    (reset: boolean) => {
      mic.stopMic();
      replay.stop();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (callIdRef.current) {
        endCall(callIdRef.current);
        callIdRef.current = null;
      }
      setLevel(0);
      setSource(null);
      if (reset) {
        setData(EMPTY);
        setLogs([]);
        setRiskHistory([]);
        setWaveform(Array(WAVE_LEN).fill(0));
        setHold(null);
        setReplaySample(null);
      }
    },
    [mic, replay, endCall],
  );

  // Replay auto-finish keeps results visible (don't wipe the verdict/hold).
  finishRef.current = () => teardown(false);

  // ── Public actions ─────────────────────────────────────────────────────────
  const beginSession = useCallback(
    async (src: 'mic' | 'replay') => {
      mic.stopMic();
      replay.stop();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setData(EMPTY);
      setLogs([]);
      setRiskHistory([]);
      setWaveform(Array(WAVE_LEN).fill(0));
      setHold(null);
      setStatus(null);
      setSource(src);
      const callId = await startCall(src);
      callIdRef.current = callId;
      connectWS(callId);
      return callId;
    },
    [mic, replay, startCall, connectWS],
  );

  const startLive = useCallback(async () => {
    try {
      await beginSession('mic');
      await mic.startMic();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Failed to start live call');
      teardown(true);
    }
  }, [beginSession, mic, teardown]);

  const startReplay = useCallback(
    async (url: string, label: string) => {
      try {
        setReplaySample(label);
        await beginSession('replay');
        await replay.start(url);
      } catch (err) {
        setStatus(err instanceof Error ? err.message : 'Failed to replay demo');
        teardown(true);
      }
    },
    [beginSession, replay, teardown],
  );

  const stop = useCallback(() => teardown(true), [teardown]);

  useEffect(() => {
    return () => {
      mic.stopMic();
      replay.stop();
      if (wsRef.current) wsRef.current.close();
      if (callIdRef.current) endCall(callIdRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isMonitoring = source !== null;
  const error = mic.error || replay.error || status;

  return {
    source,
    replaySample,
    isMonitoring,
    error,
    data,
    logs,
    riskHistory,
    waveform,
    level,
    hold,
    replayProgress: replay.progress,
    callId: callIdRef.current,
    startLive,
    startReplay,
    stop,
  };
}
