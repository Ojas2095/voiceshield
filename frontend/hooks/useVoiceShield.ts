/**
 * useVoiceShield — the single integration layer between the frontend
 * dashboard and the backend_v2 API.
 *
 * Lifecycle:
 *   startMonitoring()
 *     → POST /api/calls/start              (gets real UUID from DB)
 *     → open WS /ws/stream/{uuid}          (binary PCM frames)
 *     → startMic()                         (AudioWorklet → ws.send)
 *
 *   stopMonitoring()
 *     → stopMic()
 *     → ws.close()
 *     → POST /api/calls/{uuid}/stop        (marks call ended in DB)
 *
 * Backend WS message types received:
 *   { type: "risk_update",  fused_risk_score, spoof_probability, verdict, is_flagged, vad_active, ... }
 *   { type: "vad_update",   vad_active, timestamp_ms }
 *   { type: "hold_triggered", hold_id, mock_reference, verdict }
 *   { type: "ping" }
 *   { type: "error", detail }
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useMicStream } from './useMicStream';

// ── Backend base URL (env-overridable for production) ────────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── Frontend display state ────────────────────────────────────────────────────

export interface ShieldResponse {
  verdict: 'REAL' | 'SUSPICIOUS' | 'FRAUD' | 'WAITING';
  /** Fused risk score mapped to 0-100 for the UI ring meter */
  risk_score: number;
  layers: {
    /** spoof_probability * 100 from the voice classifier */
    voice_authenticity: number;
    /** Placeholder — Layer 2 (ASR intent) wired in later */
    intent_risk: number;
    call_signal_risk: number;
  };
  reasons?: string[];
  /** Grad-CAM base64 PNG — populated by AI layer when available */
  gradcam_png_b64: string | null;
  /** True when the VAD pipeline has detected active speech */
  vad_active: boolean;
}

export interface EvidenceLog {
  timestamp: string;
  score: number;
  verdict: string;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export const useVoiceShield = () => {
  const [data, setData] = useState<ShieldResponse>({
    verdict: 'WAITING',
    risk_score: 0,
    layers: { voice_authenticity: 0, intent_risk: 0, call_signal_risk: 0 },
    reasons: [],
    gradcam_png_b64: null,
    vad_active: false,
  });
  const [logs, setLogs] = useState<EvidenceLog[]>([]);
  const [holdAlert, setHoldAlert] = useState<string | null>(null);

  // Active call UUID returned by the backend — needed for all subsequent API calls
  const activeCallIdRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ── Audio chunk handler — fires from the AudioWorklet ────────────────────
  const handleAudioChunk = useCallback((chunk: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(chunk);
    }
  }, []);

  const { isRecording: isMonitoring, error: micError, startMic, stopMic } =
    useMicStream(handleAudioChunk);

  // ── Backend helpers ───────────────────────────────────────────────────────

  const startCallSession = useCallback(async (): Promise<string> => {
    const res = await fetch(`${API_BASE}/api/calls/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: 'mic' }),
    });
    if (!res.ok) throw new Error(`Failed to start call session: ${res.status}`);
    const json = await res.json();
    return json.call_id as string;
  }, []);

  const stopCallSession = useCallback(async (callId: string) => {
    try {
      await fetch(`${API_BASE}/api/calls/${callId}/stop`, { method: 'POST' });
    } catch (e) {
      console.warn('Failed to stop call session', e);
    }
  }, []);

  // ── WebSocket ─────────────────────────────────────────────────────────────

  const connectWebSocket = useCallback((callUuid: string) => {
    if (wsRef.current) return;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_BASE.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${wsHost}/ws/stream/${callUuid}`;

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => console.log('[VoiceShield] WS connected, call_id=', callUuid);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);

        switch (msg.type) {
          case 'risk_update':
            setData((prev) => ({
              ...prev,
              verdict: msg.verdict ?? prev.verdict,
              risk_score: Math.round((msg.fused_risk_score ?? 0) * 100),
              layers: {
                voice_authenticity: Math.round((msg.spoof_probability ?? 0) * 100),
                intent_risk: Math.round((msg.intent_risk ?? prev.layers.intent_risk) * 100),
                call_signal_risk: Math.round((msg.call_signal_risk ?? prev.layers.call_signal_risk) * 100),
              },
              reasons: msg.matched_reasons?.length
                ? msg.matched_reasons
                : msg.is_flagged ? [`spoof_p=${msg.spoof_probability?.toFixed(2)}`] : [],
              vad_active: msg.vad_active ?? prev.vad_active,
              gradcam_png_b64: msg.gradcam_png_b64 ?? prev.gradcam_png_b64 ?? null,
            }));

            if (msg.verdict && msg.verdict !== 'WAITING') {
              setLogs((prev) =>
                [
                  {
                    timestamp: new Date().toLocaleTimeString(),
                    score: Math.round((msg.fused_risk_score ?? 0) * 100),
                    verdict: msg.verdict,
                  },
                  ...prev,
                ].slice(0, 10),
              );
            }
            break;

          case 'vad_update':
            setData((prev) => ({ ...prev, vad_active: msg.vad_active }));
            break;

          case 'hold_triggered':
            setHoldAlert(`Transaction hold triggered: ${msg.mock_reference}`);
            break;

          case 'ping':
            break; // server keepalive — ignore

          case 'error':
            console.error('[VoiceShield] WS error from server:', msg.detail);
            break;

          default:
            console.warn('[VoiceShield] Unknown WS message type:', msg.type);
        }
      } catch (e) {
        console.error('[VoiceShield] Failed to parse WS message', e);
      }
    };

    ws.onclose = () => {
      console.log('[VoiceShield] WS disconnected');
      wsRef.current = null;
    };

    wsRef.current = ws;
  }, []);

  // ── Public actions ────────────────────────────────────────────────────────

  const startMonitoring = useCallback(async () => {
    try {
      const callUuid = await startCallSession();
      activeCallIdRef.current = callUuid;
      connectWebSocket(callUuid);
      await startMic();
    } catch (err) {
      console.error('[VoiceShield] startMonitoring failed:', err);
    }
  }, [startCallSession, connectWebSocket, startMic]);

  const stopMonitoring = useCallback(async () => {
    stopMic();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (activeCallIdRef.current) {
      await stopCallSession(activeCallIdRef.current);
      activeCallIdRef.current = null;
    }

    // Reset display state
    setData({
      verdict: 'WAITING',
      risk_score: 0,
      layers: { voice_authenticity: 0, intent_risk: 0, call_signal_risk: 0 },
      reasons: [],
      gradcam_png_b64: null,
      vad_active: false,
    });
    setHoldAlert(null);
  }, [stopMic, stopCallSession]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // fire-and-forget on unmount — avoid async in useEffect return
      stopMic();
      if (wsRef.current) wsRef.current.close();
      if (activeCallIdRef.current) stopCallSession(activeCallIdRef.current);
    };
  }, [stopMic, stopCallSession]);

  return {
    isMonitoring,
    micError,
    holdAlert,
    startMonitoring,
    stopMonitoring,
    data,
    logs,
  };
};
