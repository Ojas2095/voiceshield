'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  Shield, ShieldAlert, Mic, Play, Square,
  Lock, FileText, ChevronRight, Radio, PhoneCall,
} from 'lucide-react';
import { useVoiceShield, type Verdict } from '../hooks/useVoiceShield';

const DEMO_SAMPLES = [
  { id: 'real_en', label: 'Real Voice — English', file: '/demo/real_en.wav', kind: 'real' as const },
  { id: 'cloned_en', label: 'Cloned Voice — English', file: '/demo/cloned_en.wav', kind: 'clone' as const },
  { id: 'real_hi', label: 'Real Voice — Hindi', file: '/demo/real_hi.wav', kind: 'real' as const },
  { id: 'cloned_hi', label: 'Cloned Voice — Hindi', file: '/demo/cloned_hi.wav', kind: 'clone' as const },
];

function riskMeta(v: Verdict) {
  switch (v) {
    case 'REAL': return { label: 'LOW RISK', text: 'text-risk-low', bg: 'bg-risk-low', soft: 'bg-[#e7f4ec] border-[#bfe3cd]' };
    case 'SUSPICIOUS': return { label: 'MEDIUM RISK', text: 'text-risk-med', bg: 'bg-risk-med', soft: 'bg-[#fbf3e2] border-[#f0dcae]' };
    case 'FRAUD': return { label: 'HIGH RISK', text: 'text-risk-high', bg: 'bg-risk-high', soft: 'bg-[#fbeae7] border-[#f0c3bb]' };
    default: return { label: 'AWAITING AUDIO', text: 'text-muted', bg: 'bg-muted', soft: 'bg-canvas border-line' };
  }
}

export default function Home() {
  const vs = useVoiceShield();
  const started = vs.isMonitoring || vs.logs.length > 0 || vs.hold !== null;

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <TopBar source={vs.source} started={started} onStop={vs.stop} error={vs.error} />
      {started ? <Dashboard vs={vs} /> : <StartScreen vs={vs} />}
    </div>
  );
}

/* ────────────────────────────── Top bar ────────────────────────────── */
function TopBar({ source, started, onStop, error }: any) {
  const statusLabel = source === 'mic' ? 'LIVE' : source === 'replay' ? 'REPLAY' : 'READY';
  const live = source !== null;
  return (
    <header className="bg-surface border-b border-line">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Shield className="w-5 h-5 text-brand" />
          <span className="font-semibold text-navy tracking-tight">VoiceShield</span>
          <span className="text-muted text-xs border-l border-line pl-2.5 ml-1 hidden sm:inline">
            Real-Time Voice Authenticity
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/evidence" className="text-sm text-brand hover:text-brand-dark flex items-center gap-1.5">
            <FileText className="w-4 h-4" /> Evidence &amp; History
          </Link>
          <span className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md border ${
            live ? 'text-risk-low border-[#bfe3cd] bg-[#e7f4ec]' : 'text-muted border-line bg-canvas'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${live ? 'bg-risk-low animate-pulse' : 'bg-muted'}`} />
            {statusLabel}
          </span>
          {started && (
            <button onClick={onStop}
              className="text-sm font-medium text-risk-high border border-[#f0c3bb] bg-[#fbeae7] hover:bg-[#f7ddd7] px-3 py-1.5 rounded-md flex items-center gap-1.5">
              <Square className="w-3.5 h-3.5" /> Stop
            </button>
          )}
        </div>
      </div>
      {error && (
        <div className="bg-[#fbf3e2] border-t border-[#f0dcae] text-[#8a5a10] text-sm px-6 py-2 text-center">
          {error}
        </div>
      )}
    </header>
  );
}

/* ────────────────────────────── Start screen ────────────────────────────── */
function StartScreen({ vs }: any) {
  const [sample, setSample] = useState(DEMO_SAMPLES[1].id);
  const chosen = DEMO_SAMPLES.find((s) => s.id === sample)!;
  return (
    <main className="max-w-3xl mx-auto px-6 py-16">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-navy tracking-tight">VoiceShield</h1>
        <p className="text-muted mt-2">
          Real-time detection &amp; prevention of AI voice-cloning fraud on telephony audio.
        </p>
        <div className="mt-3 inline-flex items-center gap-2 text-xs text-muted">
          <span className="font-semibold text-brand">DETECT</span><ChevronRight className="w-3 h-3" />
          <span className="font-semibold text-risk-med">PREVENT</span><ChevronRight className="w-3 h-3" />
          <span className="font-semibold text-evidence">PROVE</span>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        {/* Live */}
        <div className="panel p-6 flex flex-col">
          <Mic className="w-6 h-6 text-brand" />
          <h2 className="mt-3 font-semibold text-navy">Start Live Call</h2>
          <p className="text-sm text-muted mt-1 flex-1">
            Capture your microphone and analyse it in real time through the telephony pipeline.
          </p>
          <button onClick={vs.startLive}
            className="mt-4 bg-brand hover:bg-brand-dark text-white font-medium rounded-md py-2.5 flex items-center justify-center gap-2">
            <Mic className="w-4 h-4" /> Start Live Call
          </button>
        </div>

        {/* Replay */}
        <div className="panel p-6 flex flex-col">
          <Play className="w-6 h-6 text-brand" />
          <h2 className="mt-3 font-semibold text-navy">Replay Demo Call</h2>
          <p className="text-sm text-muted mt-1">
            Feed a recorded sample through the <em>same</em> real pipeline — no scripted result.
          </p>
          <select value={sample} onChange={(e) => setSample(e.target.value)}
            className="mt-3 w-full border border-line rounded-md px-3 py-2 text-sm bg-surface text-ink">
            {DEMO_SAMPLES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <button onClick={() => vs.startReplay(chosen.file, chosen.label)}
            className="mt-3 border border-brand text-brand hover:bg-[#eaf1f9] font-medium rounded-md py-2.5 flex items-center justify-center gap-2">
            <Play className="w-4 h-4" /> Replay Selected
          </button>
        </div>
      </div>

      <div className="mt-4 panel p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-evidence" />
          <div>
            <p className="text-sm font-medium text-navy">Call History &amp; Evidence Chain</p>
            <p className="text-xs text-muted">Review past calls and verify the tamper-proof evidence log.</p>
          </div>
        </div>
        <Link href="/evidence" className="text-sm text-brand hover:text-brand-dark flex items-center gap-1">
          Open <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      <p className="text-center text-xs text-muted mt-6">
        Demo audio goes in <code className="mono">frontend/public/demo/</code>. Backend must be running on port 8000.
      </p>
    </main>
  );
}

/* ────────────────────────────── Dashboard ────────────────────────────── */
function Dashboard({ vs }: any) {
  const meta = riskMeta(vs.data.verdict);
  const elapsed = useElapsed(vs.isMonitoring);

  return (
    <main className="max-w-6xl mx-auto px-6 py-6 space-y-4">
      <StageBar isMonitoring={vs.isMonitoring} verdict={vs.data.verdict} hold={vs.hold} events={vs.logs.length} />

      {/* Row 1: call status + risk */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="panel p-5">
          <p className="eyebrow">Call Status</p>
          <div className="mt-3 flex items-center gap-2">
            {vs.source === 'mic' ? <Mic className="w-4 h-4 text-brand" /> : <PhoneCall className="w-4 h-4 text-brand" />}
            <span className="font-medium text-navy">
              {vs.source === 'mic' ? 'Live Microphone' : vs.source === 'replay' ? (vs.replaySample ?? 'Replay') : 'Ended'}
            </span>
          </div>
          <div className="mt-4 flex items-center gap-6">
            <div>
              <p className="text-xs text-muted">Duration</p>
              <p className="mono text-lg text-navy">{elapsed}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Speech (VAD)</p>
              <p className={`text-sm font-semibold ${vs.data.vadActive ? 'text-risk-low' : 'text-muted'}`}>
                {vs.data.vadActive ? 'SPEECH DETECTED' : vs.isMonitoring ? 'LISTENING…' : 'IDLE'}
              </p>
            </div>
          </div>
        </div>

        <div className={`panel p-5 lg:col-span-2 border ${meta.soft}`}>
          <div className="flex items-start justify-between">
            <div>
              <p className="eyebrow">Current Risk</p>
              <div className="mt-2 flex items-end gap-3">
                <span className={`text-6xl font-bold leading-none ${meta.text}`}>{vs.data.riskScore}</span>
                <span className="text-muted mb-1 text-sm">/ 100</span>
              </div>
              <p className={`mt-2 font-semibold ${meta.text}`}>{meta.label}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted">Synthetic-voice probability</p>
              <p className={`text-3xl font-bold ${meta.text}`}>{vs.data.spoofProbability}%</p>
              {vs.data.reasons?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1 justify-end max-w-xs">
                  {vs.data.reasons.slice(0, 3).map((r: string, i: number) => (
                    <span key={i} className="mono text-[11px] bg-canvas border border-line text-muted px-1.5 py-0.5 rounded">{r}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Waveform */}
      <div className="panel p-5">
        <p className="eyebrow mb-3">Live Audio</p>
        <Waveform bars={vs.waveform} active={vs.isMonitoring} />
      </div>

      {/* Row 2: signal + authenticity */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="panel p-5">
          <p className="eyebrow mb-3">Signal Pipeline</p>
          <dl className="space-y-2.5 text-sm">
            <Row k="VAD" v={vs.data.vadActive ? 'Active' : 'Idle'} vClass={vs.data.vadActive ? 'text-risk-low' : 'text-muted'} />
            <Row k="Telephony" v="8 kHz · µ-law · noise" />
            <Row k="Window" v="2.00 s" />
            <Row k="Hop" v="500 ms" />
          </dl>
        </div>

        <div className="panel p-5 lg:col-span-2">
          <p className="eyebrow mb-3">Authenticity Breakdown</p>
          <Bar label="Voice authenticity (Layer 1)" value={vs.data.layers.voice} color="bg-brand" />
          <Bar label="Intent risk (Layer 2)" value={vs.data.layers.intent} color="bg-[#7a5bd0]" />
          <Bar label="Call signals (Layer 3)" value={vs.data.layers.signal} color="bg-risk-med" />
        </div>
      </div>

      {/* Risk over time */}
      <div className="panel p-5">
        <p className="eyebrow mb-3">Risk Over Time</p>
        <RiskTimeline history={vs.riskHistory} verdict={vs.data.verdict} />
      </div>

      {/* PREVENT */}
      {vs.hold && <PreventCard hold={vs.hold} risk={vs.data.riskScore} />}

      {/* Event log */}
      <div className="panel overflow-hidden">
        <div className="px-5 py-3 border-b border-line"><p className="eyebrow">Detection Events</p></div>
        <table className="w-full text-sm">
          <thead className="text-muted">
            <tr className="text-left">
              <th className="px-5 py-2 font-medium">Time</th>
              <th className="px-5 py-2 font-medium">Risk</th>
              <th className="px-5 py-2 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {vs.logs.length === 0 ? (
              <tr><td colSpan={3} className="px-5 py-6 text-center text-muted">No events yet — waiting for speech…</td></tr>
            ) : vs.logs.map((l: any, i: number) => {
              const m = riskMeta(l.verdict);
              return (
                <tr key={i}>
                  <td className="px-5 py-2.5 mono text-ink">{l.t}</td>
                  <td className={`px-5 py-2.5 mono font-semibold ${m.text}`}>{l.risk}</td>
                  <td className="px-5 py-2.5"><span className={`text-xs font-semibold px-2 py-0.5 rounded border ${m.soft} ${m.text}`}>{l.verdict}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </main>
  );
}

/* ────────────────────────────── Small pieces ────────────────────────────── */
function Row({ k, v, vClass = 'text-navy' }: { k: string; v: string; vClass?: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{k}</dt>
      <dd className={`mono ${vClass}`}>{v}</dd>
    </div>
  );
}

function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-ink">{label}</span>
        <span className="mono text-muted">{value}%</span>
      </div>
      <div className="h-2 bg-canvas border border-line rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function Waveform({ bars, active }: { bars: number[]; active: boolean }) {
  return (
    <div className="flex items-center gap-[3px] h-20">
      {bars.map((b, i) => (
        <div key={i} className={`flex-1 rounded-sm ${active ? 'bg-brand/70' : 'bg-line'}`}
          style={{ height: `${Math.max(b * 100, 3)}%`, transition: 'height 120ms linear' }} />
      ))}
    </div>
  );
}

function RiskTimeline({ history, verdict }: { history: number[]; verdict: Verdict }) {
  const W = 900, H = 120, pad = 4;
  if (history.length < 2) {
    return <div className="h-[120px] flex items-center justify-center text-muted text-sm">Collecting data…</div>;
  }
  const stroke = verdict === 'FRAUD' ? '#c0392b' : verdict === 'SUSPICIOUS' ? '#b7791f' : '#2563a8';
  const stepX = (W - pad * 2) / (history.length - 1);
  const pts = history.map((v, i) => `${pad + i * stepX},${pad + (H - pad * 2) * (1 - v / 100)}`);
  const area = `${pad},${H - pad} ${pts.join(' ')} ${pad + (history.length - 1) * stepX},${H - pad}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[120px]" preserveAspectRatio="none">
      {/* threshold lines: 60 suspicious, 70 fraud */}
      {[60, 70].map((t) => (
        <line key={t} x1={pad} x2={W - pad} y1={pad + (H - pad * 2) * (1 - t / 100)} y2={pad + (H - pad * 2) * (1 - t / 100)}
          stroke={t === 70 ? '#f0c3bb' : '#f0dcae'} strokeWidth="1" strokeDasharray="4 4" />
      ))}
      <polygon points={area} fill={stroke} opacity="0.08" />
      <polyline points={pts.join(' ')} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function StageBar({ isMonitoring, verdict, hold, events }: any) {
  const detect = events > 0 || isMonitoring ? (isMonitoring ? 'active' : 'complete') : 'idle';
  const prevent = hold ? 'triggered' : verdict === 'FRAUD' ? 'triggered' : 'waiting';
  const prove = hold ? 'logged' : events > 0 ? 'logging' : 'waiting';
  const stages = [
    { icon: Radio, name: 'DETECT', state: detect, color: 'text-brand', dot: 'bg-brand' },
    { icon: ShieldAlert, name: 'PREVENT', state: prevent, color: 'text-risk-med', dot: 'bg-risk-med' },
    { icon: Lock, name: 'PROVE', state: prove, color: 'text-evidence', dot: 'bg-evidence' },
  ];
  return (
    <div className="panel px-5 py-4 flex items-center justify-between">
      {stages.map((s, i) => (
        <div key={s.name} className="flex items-center flex-1 last:flex-none">
          <div className="flex items-center gap-2.5">
            <span className={`w-8 h-8 rounded-full flex items-center justify-center ${
              s.state === 'idle' || s.state === 'waiting' ? 'bg-canvas border border-line text-muted' : `${s.dot} text-white`
            }`}>
              <s.icon className="w-4 h-4" />
            </span>
            <div>
              <p className={`text-sm font-semibold ${s.state === 'idle' || s.state === 'waiting' ? 'text-muted' : s.color}`}>{s.name}</p>
              <p className="text-[11px] text-muted uppercase tracking-wide">{s.state}</p>
            </div>
          </div>
          {i < stages.length - 1 && <div className="flex-1 h-px bg-line mx-4" />}
        </div>
      ))}
    </div>
  );
}

function PreventCard({ hold, risk }: { hold: any; risk: number }) {
  return (
    <div className="panel border border-[#f0c3bb] bg-[#fbeae7] p-5">
      <div className="flex items-start gap-4">
        <ShieldAlert className="w-6 h-6 text-risk-high mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-risk-high">Transaction Hold Triggered</h3>
          <p className="text-sm text-ink mt-1">
            High-confidence synthetic voice detected. The associated transaction has been temporarily blocked pending verification.
          </p>
          <div className="mt-3 grid sm:grid-cols-3 gap-3 text-sm">
            <div><p className="text-xs text-muted">Risk</p><p className="mono font-semibold text-risk-high">{risk}%</p></div>
            <div><p className="text-xs text-muted">Status</p><p className="font-semibold text-risk-high">HOLD ACTIVE</p></div>
            <div><p className="text-xs text-muted">Reference</p><p className="mono text-navy">{hold.reference}</p></div>
          </div>
          <Link href="/evidence" className="inline-flex items-center gap-1 text-sm text-brand hover:text-brand-dark mt-3">
            View Evidence <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}

function useElapsed(active: boolean) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!active) return;
    setS(0);
    const t = setInterval(() => setS((p) => p + 1), 1000);
    return () => clearInterval(t);
  }, [active]);
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}
