'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { 
  Phone, PhoneOff, PhoneCall, ShieldAlert, ShieldCheck, Shield, 
  Volume2, Mic, MicOff, AlertTriangle, Lock, ArrowLeft, RefreshCw, 
  CheckCircle2, AlertOctagon, Info, ExternalLink, Zap
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Scenario {
  id: string;
  name: string;
  number: string;
  organization: string;
  reportedSpam: number;
  scriptType: 'cloned' | 'real';
  audioFile: string;
  subtitle: string;
}

const SCENARIOS: Scenario[] = [
  {
    id: 'cbi_extortion',
    name: 'Officer Vikram Rathore',
    number: '+91 98110 24891',
    organization: 'Central Cyber Crime Bureau (Extortion)',
    reportedSpam: 842,
    scriptType: 'cloned',
    audioFile: '/demo/cloned_en.wav',
    subtitle: '🚨 Digital Arrest Scam: High-urgency clone demanding ₹50,000 via UPI.'
  },
  {
    id: 'family_emergency',
    name: 'Aman (Son — Impersonated)',
    number: '+91 94250 11982',
    organization: 'Police Station / Emergency Impersonation',
    reportedSpam: 319,
    scriptType: 'cloned',
    audioFile: '/demo/cloned_hi.wav',
    subtitle: '🚨 Family Distress Scam: Cloned voice claiming urgent bail money.'
  },
  {
    id: 'apollo_clinic',
    name: 'Dr. Sharma Clinic',
    number: '+91 11 2659 4000',
    organization: 'Apollo Healthcare (Appointment Desk)',
    reportedSpam: 0,
    scriptType: 'real',
    audioFile: '/demo/real_en.wav',
    subtitle: '🟢 Genuine Call: Routine health checkup appointment confirmation.'
  },
  {
    id: 'sbi_bank',
    name: 'State Bank of India',
    number: '+91 22 2282 3550',
    organization: 'SBI Branch Customer Service',
    reportedSpam: 2,
    scriptType: 'real',
    audioFile: '/demo/real_hi.wav',
    subtitle: '🟢 Genuine Call: Passbook collection notification.'
  }
];

export default function MobileSimulatorPage() {
  const [callState, setCallState] = useState<'idle' | 'ringing' | 'connected' | 'ended'>('ringing');
  const [selectedScenario, setSelectedScenario] = useState<Scenario>(SCENARIOS[0]);
  const [callDuration, setCallDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [speakerOn, setSpeakerOn] = useState(true);
  
  // Real-time detection states
  const [fusedRisk, setFusedRisk] = useState<number>(0.0);
  const [verdict, setVerdict] = useState<'ANALYZING' | 'REAL' | 'SUSPICIOUS' | 'FRAUD'>('ANALYZING');
  const [holdTriggered, setHoldTriggered] = useState(false);
  const [holdReference, setHoldReference] = useState<string | null>(null);
  const [callId, setCallId] = useState<string | null>(null);
  const [vadActive, setVadActive] = useState(false);
  const [audioStreamMode, setAudioStreamMode] = useState<'simulator' | 'mic'>('simulator');
  const [isFrozen, setIsFrozen] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioSourceRef = useRef<AudioNode | null>(null);

  // Call timer
  useEffect(() => {
    if (callState === 'connected') {
      setCallDuration(0);
      timerRef.current = setInterval(() => {
        setCallDuration(d => d + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callState]);

  // Clean up WebSocket on teardown
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  const formatDuration = (sec: number) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const startSession = async () => {
    try {
      setCallState('connected');
      setFusedRisk(0.05);
      setVerdict('ANALYZING');
      setHoldTriggered(false);
      setHoldReference(null);
      setIsFrozen(false);

      // 1. Call Backend to start call session
      const res = await fetch(`${API_BASE}/api/calls/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'phone_sim' })
      });
      const data = await res.json();
      const newCallId = data.call_id;
      setCallId(newCallId);

      // 2. Open WebSocket to backend
      const wsProtocol = API_BASE.startsWith('https') ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${API_BASE.replace(/^https?:\/\//, '')}/ws/stream/${newCallId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'risk_update') {
            setFusedRisk(msg.fused_risk_score ?? 0);
            setVerdict(msg.verdict ?? 'REAL');
          } else if (msg.type === 'hold_triggered') {
            setHoldTriggered(true);
            setHoldReference(msg.mock_reference ?? `HOLD-${new Date().toISOString().slice(0, 10)}`);
          } else if (msg.type === 'vad_update') {
            setVadActive(msg.vad_active);
          }
        } catch {
          // ignore
        }
      };

      // 3. Play and stream the selected scenario audio
      if (audioStreamMode === 'simulator') {
        streamAudioFile(ws, selectedScenario.audioFile);
      }
    } catch (err) {
      console.error('Failed to start call session:', err);
    }
  };

  const streamAudioFile = async (ws: WebSocket, audioPath: string) => {
    try {
      const response = await fetch(audioPath);
      const arrayBuffer = await response.arrayBuffer();
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = ctx;
      
      const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
      const floatData = audioBuffer.getChannelData(0);
      
      // Also play through speaker if enabled
      const bufferSource = ctx.createBufferSource();
      bufferSource.buffer = audioBuffer;
      bufferSource.connect(ctx.destination);
      bufferSource.start();
      audioSourceRef.current = bufferSource;

      // Convert float32 to Int16 PCM and stream chunks
      const int16Data = new Int16Array(floatData.length);
      for (let i = 0; i < floatData.length; i++) {
        const s = Math.max(-1, Math.min(1, floatData[i]));
        int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      // Stream in 200ms chunks (3200 samples = 6400 bytes)
      const chunkSize = 3200;
      let offset = 0;

      const interval = setInterval(() => {
        if (ws.readyState !== WebSocket.OPEN || offset >= int16Data.length) {
          clearInterval(interval);
          return;
        }
        const chunk = int16Data.subarray(offset, offset + chunkSize);
        ws.send(chunk.buffer);
        offset += chunkSize;
      }, 100);
    } catch (err) {
      console.error('Audio streaming error:', err);
    }
  };

  const handleDeclineOrDrop = () => {
    setCallState('ended');
    if (wsRef.current) wsRef.current.close();
    if (audioSourceRef.current) {
      try { (audioSourceRef.current as AudioBufferSourceNode).stop(); } catch {}
    }
    setTimeout(() => {
      setCallState('ringing');
    }, 2000);
  };

  const handleManualHold = async () => {
    if (!callId) return;
    try {
      setIsFrozen(true);
      const res = await fetch(`${API_BASE}/api/calls/${callId}/hold`, { method: 'POST' });
      const data = await res.json();
      setHoldTriggered(true);
      setHoldReference(data.mock_reference);
    } catch (err) {
      console.error('Failed to trigger hold:', err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      {/* Top Header / Context Banner */}
      <header className="w-full max-w-4xl mb-4 flex items-center justify-between">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-emerald-400 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Enterprise SOC Console
        </Link>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800">
            <Zap className="w-3.5 h-3.5" /> Mobile Companion Mode
          </span>
          <span className="text-xs text-slate-500 font-mono">Truecaller-Style Call Overlay</span>
        </div>
      </header>

      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        
        {/* Left Control & Scenario Panel */}
        <div className="md:col-span-5 flex flex-col gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 mb-3">
              <PhoneCall className="w-4 h-4 text-emerald-400" /> Incoming Call Simulator
            </h2>
            <p className="text-xs text-slate-400 mb-4 leading-relaxed">
              Demonstrates how VoiceShield intercepts incoming mobile phone calls in real time using a floating in-call security HUD.
            </p>

            {/* Scenario Selector */}
            <label className="text-xs font-medium text-slate-400 block mb-1.5">Select Demo Threat Vector</label>
            <div className="flex flex-col gap-2 mb-4">
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setSelectedScenario(s);
                    if (callState === 'connected') handleDeclineOrDrop();
                  }}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    selectedScenario.id === s.id
                      ? 'bg-slate-800/90 border-emerald-500/80 shadow-md shadow-emerald-950/30'
                      : 'bg-slate-900/60 border-slate-800 hover:bg-slate-800/50 text-slate-400'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-slate-200">{s.name}</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                      s.scriptType === 'cloned' ? 'bg-rose-950/80 text-rose-400 border border-rose-800/60' : 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60'
                    }`}>
                      {s.scriptType === 'cloned' ? 'AI Voice Clone' : 'Genuine Voice'}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 font-mono mb-1">{s.number}</div>
                  <div className="text-[11px] text-slate-400 leading-tight">{s.subtitle}</div>
                </button>
              ))}
            </div>

            {/* Technical Proof Note */}
            <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-lg text-xs text-slate-400 flex flex-col gap-1.5 font-mono">
              <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
                <Info className="w-3.5 h-3.5 text-cyan-400" /> Truecaller Parity Specs:
              </div>
              <div>• Native Android: <code className="text-cyan-300">CallScreeningService</code></div>
              <div>• Floating HUD: <code className="text-cyan-300">TYPE_APPLICATION_OVERLAY</code></div>
              <div>• BSA 2023 §63: Ed25519 tamper-proof log</div>
              <div>• Inference: ~2.26ms MelCNN on GPU</div>
            </div>
          </div>
        </div>

        {/* Right Smartphone Simulator */}
        <div className="md:col-span-7 flex justify-center">
          <div className="w-[360px] h-[720px] bg-slate-900 border-[10px] border-slate-800 rounded-[48px] shadow-2xl overflow-hidden relative flex flex-col justify-between select-none">
            
            {/* Phone Top Notch & Status Bar */}
            <div className="w-full bg-slate-900/90 backdrop-blur-md pt-3 px-6 pb-2 flex items-center justify-between text-[11px] text-slate-400 font-mono z-30">
              <span>13:26</span>
              {/* Speaker notch */}
              <div className="w-20 h-4 bg-slate-950 rounded-full flex items-center justify-center">
                <div className="w-3 h-3 bg-slate-800 rounded-full" />
              </div>
              <div className="flex items-center gap-1.5">
                <span>5G</span>
                <span>88%</span>
              </div>
            </div>

            {/* Main Phone Screen Content */}
            <div className="flex-1 flex flex-col justify-between p-6 relative overflow-hidden">
              
              {/* INCOMING CALL SCREEN */}
              {callState === 'ringing' && (
                <div className="flex-1 flex flex-col items-center justify-between py-8 text-center animate-fade-in">
                  
                  {/* Caller Identity */}
                  <div className="flex flex-col items-center mt-6">
                    <div className="relative mb-4">
                      <div className="w-24 h-24 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center text-3xl font-bold text-slate-300 shadow-lg">
                        {selectedScenario.name[0]}
                      </div>
                      {selectedScenario.scriptType === 'cloned' && (
                        <div className="absolute -bottom-1 -right-1 p-1.5 bg-rose-600 rounded-full text-white shadow-md animate-pulse">
                          <AlertTriangle className="w-4 h-4" />
                        </div>
                      )}
                    </div>
                    
                    <h3 className="text-xl font-bold text-slate-100 mb-1">{selectedScenario.name}</h3>
                    <div className="text-xs text-slate-400 font-mono mb-2">{selectedScenario.number}</div>
                    
                    {/* Truecaller-style reputation badge */}
                    <div className={`px-3 py-1 rounded-full text-xs font-medium border flex items-center gap-1.5 ${
                      selectedScenario.scriptType === 'cloned'
                        ? 'bg-rose-950/70 border-rose-800/80 text-rose-300'
                        : 'bg-emerald-950/70 border-emerald-800/80 text-emerald-300'
                    }`}>
                      {selectedScenario.scriptType === 'cloned' ? (
                        <>
                          <AlertOctagon className="w-3.5 h-3.5" /> High Extortion Risk ({selectedScenario.reportedSpam} reports)
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" /> Verified Business Caller
                        </>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-2">{selectedScenario.organization}</div>
                  </div>

                  {/* VoiceShield Pre-Call Protection Pill */}
                  <div className="w-full bg-slate-950/80 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                      <span>VoiceShield AI Active</span>
                    </div>
                    <span className="text-[10px] bg-emerald-950 text-emerald-400 px-2 py-0.5 rounded font-mono">BEE PROTECTED</span>
                  </div>

                  {/* Answer / Decline Controls */}
                  <div className="w-full flex items-center justify-around mt-4">
                    <button
                      onClick={handleDeclineOrDrop}
                      className="w-16 h-16 rounded-full bg-rose-600 hover:bg-rose-700 flex items-center justify-center text-white shadow-lg transition-transform active:scale-95"
                      title="Decline Call"
                    >
                      <PhoneOff className="w-7 h-7" />
                    </button>
                    <button
                      onClick={startSession}
                      className="w-16 h-16 rounded-full bg-emerald-500 hover:bg-emerald-600 flex items-center justify-center text-white shadow-lg transition-transform active:scale-95 animate-bounce"
                      title="Answer Call"
                    >
                      <Phone className="w-7 h-7" />
                    </button>
                  </div>
                </div>
              )}

              {/* CONNECTED CALL SCREEN WITH VOICESHIELD FLOATING HUD */}
              {callState === 'connected' && (
                <div className="flex-1 flex flex-col justify-between py-2 text-center animate-fade-in relative">
                  
                  {/* Top Caller Info & Timer */}
                  <div className="flex flex-col items-center mt-2">
                    <h3 className="text-lg font-bold text-slate-100">{selectedScenario.name}</h3>
                    <span className="text-xs text-slate-400 font-mono">{formatDuration(callDuration)}</span>
                  </div>

                  {/* FLOATING VOICESHIELD TRUECALLER HUD OVERLAY */}
                  <div className={`my-auto rounded-2xl border p-4 shadow-2xl backdrop-blur-md transition-all duration-300 ${
                    verdict === 'FRAUD'
                      ? 'bg-rose-950/90 border-rose-500/80 shadow-rose-950/50 ring-2 ring-rose-500/40 animate-pulse'
                      : verdict === 'SUSPICIOUS'
                      ? 'bg-amber-950/90 border-amber-500/80 shadow-amber-950/50'
                      : 'bg-slate-900/90 border-emerald-500/50 shadow-emerald-950/30'
                  }`}>
                    
                    {/* HUD Header */}
                    <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 mb-3">
                      <div className="flex items-center gap-1.5">
                        <Shield className={`w-4 h-4 ${verdict === 'FRAUD' ? 'text-rose-400' : 'text-emerald-400'}`} />
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-200">VoiceShield In-Call HUD</span>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                        verdict === 'FRAUD' ? 'bg-rose-900 text-rose-200' : 'bg-emerald-900 text-emerald-200'
                      }`}>
                        {verdict}
                      </span>
                    </div>

                    {/* Threat Metric */}
                    <div className="flex flex-col items-center my-2">
                      <div className="text-3xl font-extrabold font-mono tracking-tight text-white mb-1">
                        {(fusedRisk * 100).toFixed(1)}%
                      </div>
                      <span className="text-[11px] text-slate-300 font-medium">
                        {verdict === 'FRAUD'
                          ? '🚨 CRITICAL: AI Voice Clone Impersonation'
                          : verdict === 'SUSPICIOUS'
                          ? '⚠️ Unnatural Spectral Phasing Detected'
                          : '🟢 Verified Natural Human Speech'}
                      </span>
                    </div>

                    {/* VAD & Forensic indicators */}
                    <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-800/80 text-[10px] font-mono text-left">
                      <div className="flex items-center gap-1 text-slate-400">
                        <span className={`w-2 h-2 rounded-full ${vadActive ? 'bg-emerald-400 animate-ping' : 'bg-slate-600'}`} />
                        <span>Speech VAD: {vadActive ? 'Active' : 'Silence'}</span>
                      </div>
                      <div className="text-right text-slate-400">
                        <span>Latency: &lt; 3ms</span>
                      </div>
                    </div>

                    {/* FRAUD AUTO-PROTECTION ACTIONS */}
                    {verdict === 'FRAUD' && (
                      <div className="flex flex-col gap-2 mt-3 pt-2">
                        <button
                          onClick={handleManualHold}
                          disabled={holdTriggered}
                          className={`w-full py-2.5 px-3 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg transition-all ${
                            holdTriggered
                              ? 'bg-emerald-600 text-white'
                              : 'bg-rose-600 hover:bg-rose-500 text-white animate-bounce'
                          }`}
                        >
                          <Lock className="w-4 h-4" />
                          {holdTriggered ? 'Banking & UPI Frozen (Safe)' : 'Freeze Banking Sessions'}
                        </button>
                        {holdReference && (
                          <div className="text-[10px] font-mono text-emerald-300 bg-emerald-950/80 py-1 px-2 rounded border border-emerald-800/60">
                            Ref: {holdReference}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Standard In-Call Dialpad Controls */}
                  <div className="grid grid-cols-3 gap-3 my-2 text-slate-400 text-xs">
                    <button 
                      onClick={() => setIsMuted(!isMuted)} 
                      className={`p-3 rounded-full flex flex-col items-center gap-1 ${isMuted ? 'bg-rose-900/60 text-rose-300' : 'bg-slate-800 hover:bg-slate-700'}`}
                    >
                      {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                      <span className="text-[9px]">Mute</span>
                    </button>
                    <button 
                      onClick={() => setSpeakerOn(!speakerOn)}
                      className={`p-3 rounded-full flex flex-col items-center gap-1 ${speakerOn ? 'bg-emerald-900/60 text-emerald-300' : 'bg-slate-800 hover:bg-slate-700'}`}
                    >
                      <Volume2 className="w-5 h-5" />
                      <span className="text-[9px]">Speaker</span>
                    </button>
                    <button 
                      onClick={handleManualHold}
                      className={`p-3 rounded-full flex flex-col items-center gap-1 ${isFrozen ? 'bg-emerald-900 text-emerald-300' : 'bg-slate-800 hover:bg-slate-700'}`}
                    >
                      <Lock className="w-5 h-5" />
                      <span className="text-[9px]">Hold Bank</span>
                    </button>
                  </div>

                  {/* Drop Call Button */}
                  <div className="mt-2">
                    <button
                      onClick={handleDeclineOrDrop}
                      className="w-16 h-16 mx-auto rounded-full bg-rose-600 hover:bg-rose-700 flex items-center justify-center text-white shadow-xl active:scale-95 transition-transform"
                    >
                      <PhoneOff className="w-7 h-7" />
                    </button>
                  </div>
                </div>
              )}

              {/* CALL ENDED STATE */}
              {callState === 'ended' && (
                <div className="flex-1 flex flex-col items-center justify-center text-center animate-fade-in">
                  <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center mb-4 text-slate-400">
                    <PhoneOff className="w-8 h-8" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-200 mb-1">Call Terminated</h3>
                  <p className="text-xs text-slate-500 mb-4 font-mono">Duration: {formatDuration(callDuration)}</p>
                  
                  {callId && (
                    <Link
                      href={`/evidence?call_id=${callId}`}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600/90 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-all"
                    >
                      <ExternalLink className="w-3.5 h-3.5" /> View BSA §63 Forensic Log
                    </Link>
                  )}
                </div>
              )}

            </div>

            {/* Bottom Android Home Indicator */}
            <div className="w-full pb-2 flex justify-center z-30">
              <div className="w-32 h-1 bg-slate-700 rounded-full" />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
