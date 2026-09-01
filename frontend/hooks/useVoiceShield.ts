import { useState, useEffect, useRef, useCallback } from 'react';

export interface ShieldResponse {
  verdict: 'REAL' | 'SUSPICIOUS' | 'FRAUD' | 'WAITING';
  risk_score: number;
  layers: {
    voice_authenticity: number;
    intent_risk: number;
    call_signal_risk: number;
  };
  gradcam_png_b64: string | null;
}

export interface EvidenceLog {
  timestamp: string;
  score: number;
  verdict: string;
}

export const useVoiceShield = (callId: string) => {
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [data, setData] = useState<ShieldResponse>({
    verdict: 'WAITING',
    risk_score: 0,
    layers: { voice_authenticity: 0, intent_risk: 0, call_signal_risk: 0 },
    gradcam_png_b64: null,
  });
  const [logs, setLogs] = useState<EvidenceLog[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current) return;
    
    const wsUrl = `ws://localhost:8000/ws/calls/${callId}/audio`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('VoiceShield WS Connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const payload: ShieldResponse = JSON.parse(event.data);
        setData(payload);
        
        if (payload.verdict !== 'WAITING') {
            setLogs(prev => [{
                timestamp: new Date().toLocaleTimeString(),
                score: payload.risk_score,
                verdict: payload.verdict
            }, ...prev].slice(0, 10)); // Keep last 10
        }
      } catch (e) {
        console.error('Error parsing WS message', e);
      }
    };
    
    ws.onclose = () => {
      console.log('VoiceShield WS Disconnected');
      wsRef.current = null;
      if (isMonitoring) {
          setTimeout(connectWebSocket, 1000); // Reconnect
      }
    };
    
    wsRef.current = ws;
  }, [callId, isMonitoring]);

  const startMonitoring = useCallback(() => {
    setIsMonitoring(true);
    connectWebSocket();
    // Placeholder: Start capturing mic audio and sending chunks
  }, [connectWebSocket]);

  const stopMonitoring = useCallback(() => {
    setIsMonitoring(false);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    // Placeholder: Stop mic capture
  }, []);

  useEffect(() => {
    return () => {
      stopMonitoring();
    };
  }, [stopMonitoring]);

  return {
    isMonitoring,
    startMonitoring,
    stopMonitoring,
    data,
    logs
  };
};
