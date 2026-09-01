'use client';
import Link from 'next/link';
import { useVoiceShield } from '../hooks/useVoiceShield';
import { Shield, ShieldAlert, ShieldCheck, Activity, Mic, MicOff, Hash } from 'lucide-react';

export default function Dashboard() {
  const { isMonitoring, micError, holdAlert, startMonitoring, stopMonitoring, data, logs } = useVoiceShield();
  
  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case 'REAL': return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
      case 'SUSPICIOUS': return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
      case 'FRAUD': return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
      default: return 'text-slate-400 bg-slate-800 border-slate-700';
    }
  };

  const getRiskColor = (score: number) => {
    if (score < 30) return 'text-emerald-500';
    if (score < 70) return 'text-amber-500';
    return 'text-rose-500';
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col relative overflow-hidden">
      {/* Fraud Alert Banner */}
      <div className={`absolute top-0 left-0 right-0 z-50 transition-transform duration-500 ${data.verdict === 'FRAUD' ? 'translate-y-0' : '-translate-y-full'}`}>
        <div className="bg-rose-500 text-white px-4 py-3 flex items-center justify-center gap-2 shadow-lg shadow-rose-500/20">
          <ShieldAlert className="w-5 h-5 animate-pulse" />
          <span className="font-bold tracking-wider">FRAUD DETECTED: Deepfake or Malicious Intent Identified</span>
        </div>
      </div>

      {/* Hold Alert Banner */}
      {holdAlert && (
        <div className="absolute top-12 left-0 right-0 z-50">
          <div className="bg-amber-500 text-white px-4 py-2 flex items-center justify-center gap-2 shadow-md shadow-amber-500/20">
            <ShieldAlert className="w-4 h-4" />
            <span className="text-sm font-semibold">{holdAlert}</span>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm p-4 flex justify-between items-center sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Shield className="w-8 h-8 text-indigo-500" />
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">VoiceShield</h1>
            <p className="text-xs text-slate-400 uppercase tracking-widest">SIH 2026 Core Module</p>
          </div>
          <Link
            href="/evidence"
            className="ml-4 flex items-center gap-1.5 text-xs text-slate-400 hover:text-indigo-400 border border-slate-700 hover:border-indigo-500/40 px-2.5 py-1.5 rounded-md transition-colors"
          >
            <Hash className="w-3.5 h-3.5" /> Evidence Audit
          </Link>
        </div>
        <div className="flex items-center gap-4">
          {micError && (
            <div className="text-rose-500 text-xs font-semibold px-3 py-1.5 rounded-full bg-rose-500/10 border border-rose-500/20">
              {micError}
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800">
            <div className={`w-2 h-2 rounded-full ${isMonitoring ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse' : 'bg-slate-600'}`} />
            <span className="text-sm font-medium text-slate-300">{isMonitoring ? 'LIVE' : 'INACTIVE'}</span>
          </div>
          {isMonitoring && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors duration-300 ${
              data.vad_active
                ? 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20'
                : 'text-slate-500 bg-slate-900 border-slate-800'
            }`}>
              <Activity className="w-3 h-3" />
              {data.vad_active ? 'VOICE' : 'SILENCE'}
            </div>
          )}
          <button
            onClick={isMonitoring ? stopMonitoring : startMonitoring}
            className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
              isMonitoring 
                ? 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border border-rose-500/20' 
                : 'bg-indigo-500 hover:bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
            }`}
          >
            {isMonitoring ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            {isMonitoring ? 'Stop Monitoring' : 'Start Monitoring'}
          </button>
        </div>
      </header>

      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-7xl mx-auto w-full">
        {/* Left Column: Risk & Verdict */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          {/* Verdict Card */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent to-slate-900/80" />
            <div className="relative z-10 flex flex-col items-center">
              <h2 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-4">Current Verdict</h2>
              <div className={`px-6 py-3 rounded-lg border-2 flex items-center gap-3 ${getVerdictColor(data.verdict)}`}>
                {data.verdict === 'REAL' && <ShieldCheck className="w-6 h-6" />}
                {data.verdict === 'FRAUD' && <ShieldAlert className="w-6 h-6" />}
                {data.verdict === 'SUSPICIOUS' && <Activity className="w-6 h-6" />}
                <span className="text-2xl font-black tracking-widest">{data.verdict}</span>
              </div>
              {data.reasons && data.reasons.length > 0 && (
                <div className="mt-4 w-full flex flex-col gap-1.5 items-center">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Detected Signals:</span>
                  <div className="flex flex-wrap gap-1.5 justify-center">
                    {data.reasons.map((r, i) => (
                      <span key={i} className="text-xs font-mono bg-rose-950/80 text-rose-300 border border-rose-800/60 px-2 py-0.5 rounded">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Risk Meter */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 flex flex-col items-center">
            <h2 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-6">Threat Risk Meter</h2>
            <div className="relative w-48 h-48 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90">
                <circle cx="96" cy="96" r="88" className="stroke-slate-800 fill-none" strokeWidth="12" />
                <circle 
                  cx="96" cy="96" r="88" 
                  className={`fill-none transition-all duration-1000 ${getRiskColor(data.risk_score)}`}
                  strokeWidth="12" 
                  strokeDasharray={`${(data.risk_score / 100) * 553} 553`}
                  strokeLinecap="round"
                  stroke="currentColor"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={`text-5xl font-black ${getRiskColor(data.risk_score)}`}>{Math.round(data.risk_score)}</span>
                <span className="text-slate-500 text-xs font-bold mt-1">/ 100</span>
              </div>
            </div>
            
            {/* Layer Breakdown */}
            <div className="w-full mt-8 space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-400">Voice Authenticity (L1)</span>
                <span className="font-mono text-slate-200">{Math.round(data.layers.voice_authenticity)}%</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div className="bg-cyan-500 h-full transition-all duration-500" style={{ width: `${data.layers.voice_authenticity}%` }} />
              </div>
              
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-400">Intent Risk (L2)</span>
                <span className="font-mono text-slate-200">{Math.round(data.layers.intent_risk)}%</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div className="bg-indigo-500 h-full transition-all duration-500" style={{ width: `${data.layers.intent_risk}%` }} />
              </div>

              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-400">Call Signals (L3)</span>
                <span className="font-mono text-slate-200">{Math.round(data.layers.call_signal_risk)}%</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div className="bg-amber-500 h-full transition-all duration-500" style={{ width: `${data.layers.call_signal_risk}%` }} />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: GradCAM & Logs */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          {/* Grad-CAM Heatmap */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 flex flex-col flex-1 min-h-[300px]">
            <h2 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-4">Acoustic Analysis (Grad-CAM)</h2>
            <div className="flex-1 bg-slate-950 rounded-lg border border-slate-800/50 flex items-center justify-center overflow-hidden relative min-h-[300px]">
              {data.gradcam_png_b64 ? (
                <img 
                  src={`data:image/png;base64,${data.gradcam_png_b64}`} 
                  alt="Grad-CAM Heatmap" 
                  className="w-full h-full object-cover opacity-80 mix-blend-screen"
                />
              ) : (
                <div className="flex flex-col items-center justify-center text-slate-600 gap-3 h-full">
                  <Activity className="w-8 h-8 opacity-50" />
                  <span className="text-sm font-medium">Awaiting audio telemetry...</span>
                </div>
              )}
              {/* Scanline effect */}
              <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.25)_50%)] bg-[length:100%_4px] mix-blend-overlay" />
            </div>
          </div>

          {/* Evidence Logs */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-800">
              <h2 className="text-slate-400 text-sm font-semibold uppercase tracking-wider">Detection Event Log</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-900/80 text-slate-400">
                  <tr>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                    <th className="px-4 py-3 font-medium">Risk Score</th>
                    <th className="px-4 py-3 font-medium">Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-4 py-6 text-center text-slate-500">No events recorded yet</td>
                    </tr>
                  ) : (
                    logs.map((log, i) => (
                      <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-4 py-3 font-mono text-slate-300">{log.timestamp}</td>
                        <td className="px-4 py-3">
                          <span className={`font-mono font-bold ${getRiskColor(log.score)}`}>{Math.round(log.score)}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-bold px-2 py-1 rounded border ${getVerdictColor(log.verdict)}`}>
                            {log.verdict}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
