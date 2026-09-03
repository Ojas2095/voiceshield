'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  Mic, Square, Radio, ShieldAlert, ShieldCheck, Activity, Lock, ChevronRight, AudioWaveform,
  MessageSquareQuote, AlertTriangle, UserCheck,
} from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { VoiceIntegrityRail } from '../components/VoiceIntegrityRail';
import { useVoiceShield, type Verdict } from '../hooks/useVoiceShield';

function riskMeta(v: Verdict, threat?: string) {
  if (threat === 'HUMAN_VISHING') {
    return { label: 'HUMAN VISHING SCAM', text: 'text-amber-400', soft: 'bg-amber-500/15 border-amber-500/40' };
  }
  if (threat === 'AI_SYNTHETIC' || v === 'FRAUD') {
    return { label: 'SYNTHETIC VOICE DETECTED', text: 'text-risk-high', soft: 'bg-high-soft border-high-line' };
  }
  if (v === 'REAL' || threat === 'LEGITIMATE_HUMAN') {
    return { label: 'AUTHENTIC HUMAN VOICE', text: 'text-risk-low', soft: 'bg-low-soft border-low-line' };
  }
  if (v === 'SUSPICIOUS') {
    return { label: 'REVIEW REQUIRED', text: 'text-risk-med', soft: 'bg-med-soft border-med-line' };
  }
  return { label: 'AWAITING AUDIO', text: 'text-muted', soft: 'bg-surface-low border-line' };
}

export default function LiveProtection() {
  const vs = useVoiceShield();
  const hasResults = vs.logs.length > 0 || vs.hold !== null;

  return (
    <AppShell>
      <CallBar vs={vs} hasResults={hasResults} />
      {vs.error && (
        <div className="bg-med-soft border-b border-med-line text-risk-med text-body-sm px-6 py-2">{vs.error}</div>
      )}

      <div className="px-6 py-3 space-y-3">
        <VoiceIntegrityRail
          monitoring={vs.isMonitoring}
          hasResults={hasResults}
          vadActive={vs.data.vadActive}
          verdict={vs.data.verdict}
          spoofProbability={vs.data.spoofProbability}
          sourceLabel={vs.source === 'mic' ? 'Live Microphone' : vs.source === 'replay' ? (vs.replaySample ?? 'Replay') : '—'}
          held={vs.hold !== null}
          holdReference={vs.hold?.reference}
        />

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          {/* Center column */}
          <div className="xl:col-span-2 space-y-3">
            <AcousticMonitor waveform={vs.waveform} verdict={vs.data.verdict} active={vs.isMonitoring} vad={vs.data.vadActive} />
            <DualBranch vs={vs} />
            <ConversationalIntelligencePanel vs={vs} />
          </div>
          {/* Right inspector */}
          <div className="space-y-3">
            <VerdictPanel vs={vs} />
            <RiskTrajectory history={vs.riskHistory} verdict={vs.data.verdict} />
            <PreventionPanel hold={vs.hold} risk={vs.data.riskScore} verdict={vs.data.verdict} threat={vs.data.threatCategory} />
            <EvidencePanel hasResults={hasResults} held={vs.hold !== null} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

/* ── Active-call bar + start/stop ── */
function CallBar({ vs, hasResults }: any) {
  const elapsed = useElapsed(vs.isMonitoring);
  return (
    <div className="bg-surface border-b border-line px-6 py-2.5 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-3 min-w-0">
        <span className="text-body-sm font-semibold text-navy uppercase tracking-tight">Live Protection</span>
        {vs.isMonitoring ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-high-soft text-risk-high">
            <span className="w-2 h-2 rounded-full bg-risk-high animate-pulse" />
            <span className="eyebrow">Active Call — {vs.source === 'mic' ? 'Microphone' : vs.replaySample ?? 'Replay'}</span>
          </span>
        ) : (
          <span className="eyebrow">{hasResults ? 'Call ended' : 'No active call'}</span>
        )}
        {vs.isMonitoring && (
          <div className="flex items-center gap-3 mono text-data text-muted">
            <span className="inline-flex items-center gap-1 bg-surface-high px-2 py-0.5 rounded text-navy">
              <span className="w-1.5 h-1.5 rounded-full bg-risk-high animate-ping" />{elapsed}
            </span>
            <span className="hidden md:inline">8 kHz Telephony PCM (G.711)</span>
            {vs.callId && <span className="hidden lg:inline">ID: {vs.callId.slice(0, 8).toUpperCase()}</span>}
          </div>
        )}
      </div>
      <div>
        {vs.isMonitoring ? (
          <button onClick={vs.stop}
            className="inline-flex items-center gap-2 px-3 h-8 rounded bg-high-soft text-risk-high border border-high-line hover:bg-risk-high hover:text-white transition-colors text-body-sm font-semibold">
            <Square className="w-3.5 h-3.5" /> Terminate Call
          </button>
        ) : (
          <button onClick={vs.startLive}
            className="inline-flex items-center gap-2 px-3 h-8 rounded bg-navy text-surface hover:bg-brand transition-colors text-body-sm font-semibold">
            <Mic className="w-3.5 h-3.5" /> Start Live Call
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Acoustic monitor (dark) with real waveform ── */
function AcousticMonitor({ waveform, verdict, active, vad }: any) {
  const fraud = verdict === 'FRAUD';
  return (
    <div className="panel overflow-hidden">
      <div className="panel-head px-4 h-9 flex items-center justify-between">
        <span className="eyebrow text-navy flex items-center gap-1.5"><AudioWaveform className="w-3.5 h-3.5 text-brand" /> Acoustic Frequency Monitor</span>
        <span className="mono text-data-sm text-muted">8000 Hz · G.711u {vad ? '· VAD 1.0' : ''}</span>
      </div>
      <div className="bg-[#0b1420] p-4">
        <div className="flex items-center gap-[3px] h-32">
          {waveform.map((b: number, i: number) => (
            <div key={i} className="flex-1 rounded-sm"
              style={{
                height: `${Math.max(b * 100, 2)}%`,
                background: fraud && b > 0.25 ? '#ef5350' : active ? '#4f8fe0' : '#334155',
                transition: 'height 110ms linear',
              }} />
          ))}
        </div>
        <div className="flex items-center justify-between mono text-data-sm mt-2">
          <span className="text-[#7f93ad]">CH-A · primary caller stream</span>
          {fraud && <span className="text-[#ef7a70] font-semibold">SYNTHETIC PHASE DISCONTINUITY DETECTED</span>}
        </div>
      </div>
    </div>
  );
}

/* ── Dual-branch deterministic telemetry ── */
function DualBranch({ vs }: any) {
  const spoof = vs.data.spoofProbability;
  return (
    <div className="panel">
      <div className="panel-head px-4 h-9 flex items-center"><span className="eyebrow text-navy">Dual-Branch Deterministic Inference</span></div>
      <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Field k="DSP Front-End" v="Bandpass 300–3400 Hz" sub="Nyquist 4.0 kHz · 8 kHz PCM" />
        <Field k="Voice Activity" v={vs.data.vadActive ? 'Speech Active' : 'Idle'} sub="Silero VAD" vClass={vs.data.vadActive ? 'text-risk-low' : 'text-muted'} />
        <Field k="Analysis Window" v="2.00 s Rolling" sub="500 ms hop (50% overlap)" />
      </div>
      <div className="px-4 pb-4">
        <div className="border border-line rounded">
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-line">
            <Branch title="Branch A · Acoustic (wav2vec2)" desc="Phonetic trajectory vs. human vocal-tract geometry." metric="Voice authenticity" value={`${spoof}%`} tone={spoof >= 70 ? 'high' : spoof >= 40 ? 'med' : 'low'} />
            <Branch title="Branch B · Spectral (MelCNN)" desc="Vocoder artifact / phase-alignment signature." metric="Fused risk" value={`${vs.data.riskScore}%`} tone={vs.data.riskScore >= 70 ? 'high' : vs.data.riskScore >= 40 ? 'med' : 'low'} />
          </div>
          <div className="panel-head px-4 py-2 flex items-center justify-between mono text-data-sm">
            <span className="text-muted">ENSEMBLE FUSION · threshold 0.70</span>
            <span className={vs.data.verdict === 'FRAUD' ? 'text-risk-high font-semibold' : vs.data.verdict === 'REAL' ? 'text-risk-low font-semibold' : 'text-muted'}>
              {vs.data.verdict === 'WAITING' ? 'awaiting' : `${vs.data.riskScore}% ${vs.data.verdict}`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Branch({ title, desc, metric, value, tone }: any) {
  const tc = tone === 'high' ? 'text-risk-high' : tone === 'med' ? 'text-risk-med' : 'text-risk-low';
  return (
    <div className="p-4">
      <p className="text-body-sm font-semibold text-navy">{title}</p>
      <p className="text-body-sm text-muted mt-1 leading-snug">{desc}</p>
      <div className="flex items-center justify-between mt-3 mono text-data">
        <span className="text-muted uppercase">{metric}</span>
        <span className={`font-semibold ${tc}`}>{value}</span>
      </div>
    </div>
  );
}

/* ── Right inspector panels ── */
function VerdictPanel({ vs }: any) {
  const threat = vs.data.threatCategory;
  const m = riskMeta(vs.data.verdict, threat);
  const Icon = threat === 'HUMAN_VISHING' ? AlertTriangle : vs.data.verdict === 'FRAUD' ? ShieldAlert : vs.data.verdict === 'REAL' ? ShieldCheck : Activity;
  return (
    <div className={`panel border ${m.soft}`}>
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`w-5 h-5 ${m.text}`} />
            <span className={`text-body-sm font-semibold ${m.text}`}>{m.label}</span>
          </div>
          {threat && threat !== 'WAITING' && (
            <span className={`mono text-data-sm px-2 py-0.5 rounded font-semibold text-[10px] ${
              threat === 'HUMAN_VISHING'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                : threat === 'AI_SYNTHETIC'
                ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
            }`}>
              {threat === 'HUMAN_VISHING' ? '⚠️ HUMAN VISHING' : threat === 'AI_SYNTHETIC' ? '🤖 AI CLONE' : '🛡️ LEGITIMATE HUMAN'}
            </span>
          )}
        </div>
        <div className="mt-3 flex items-end justify-between">
          <div>
            <p className="eyebrow">Synthetic probability</p>
            <p className={`mono text-metric ${m.text}`}>{vs.data.verdict === 'WAITING' ? '—' : `${vs.data.spoofProbability}%`}</p>
          </div>
          <div className="text-right">
            <p className="eyebrow">Fused risk</p>
            <p className={`mono text-metric ${m.text}`}>{vs.data.riskScore}</p>
          </div>
        </div>

        {/* 2-Column Tri-State Telemetry */}
        <div className="mt-3 pt-3 border-t border-line grid grid-cols-2 gap-2 text-data-sm mono">
          <div className="bg-surface/50 p-1.5 rounded border border-line">
            <span className="text-muted block text-[10px] uppercase">Voice Authenticity</span>
            <span className={vs.data.voiceClassification === 'HUMAN' ? 'text-emerald-400 font-semibold' : vs.data.voiceClassification === 'SYNTHETIC' ? 'text-red-400 font-semibold' : 'text-muted'}>
              {vs.data.voiceClassification === 'HUMAN' ? 'Biological Voice' : vs.data.voiceClassification === 'SYNTHETIC' ? 'Synthetic Vocoder' : '—'}
            </span>
          </div>
          <div className="bg-surface/50 p-1.5 rounded border border-line">
            <span className="text-muted block text-[10px] uppercase">Scam Intent Risk</span>
            <span className={vs.data.scamRiskLevel === 'HIGH' ? 'text-red-400 font-semibold' : vs.data.scamRiskLevel === 'MEDIUM' ? 'text-amber-400 font-semibold' : 'text-emerald-400 font-semibold'}>
              {vs.data.scamRiskLevel === 'HIGH' ? 'High Extortion/OTP' : vs.data.scamRiskLevel === 'MEDIUM' ? 'Suspicious Urgency' : 'Benign / Normal'}
            </span>
          </div>
        </div>

        {vs.data.reasons?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {vs.data.reasons.slice(0, 4).map((r: string, i: number) => (
              <span key={i} className="mono text-data-sm bg-surface border border-line text-muted px-1.5 py-0.5 rounded-sm">{r}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RiskTrajectory({ history, verdict }: { history: number[]; verdict: Verdict }) {
  const bars = history.slice(-16);
  const stroke = verdict === 'FRAUD' ? 'bg-risk-high' : verdict === 'SUSPICIOUS' ? 'bg-risk-med' : 'bg-brand';
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow text-navy">Risk Trajectory</span>
        <span className="mono text-data-sm text-muted">last {bars.length} windows</span>
      </div>
      <div className="mt-3 flex items-end gap-1 h-20">
        {bars.length === 0 ? (
          <span className="text-body-sm text-muted">Collecting…</span>
        ) : bars.map((v, i) => (
          <div key={i} className={`flex-1 rounded-sm ${v >= 70 ? 'bg-risk-high' : v >= 40 ? 'bg-risk-med' : stroke}`}
            style={{ height: `${Math.max(v, 3)}%` }} title={`${v}%`} />
        ))}
      </div>
    </div>
  );
}

function PreventionPanel({ hold, risk, verdict, threat }: any) {
  if (hold) {
    const isVishing = threat === 'HUMAN_VISHING';
    return (
      <div className="panel border border-high-line bg-high-soft p-4">
        <div className="flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-risk-high" />
          <span className="text-body-sm font-semibold text-risk-high">
            {isVishing ? 'Human Vishing Intercepted' : 'Prevention Action Enforced'}
          </span>
        </div>
        <p className="text-body-sm text-ink mt-1.5">
          {isVishing
            ? 'Real human caller attempting social engineering / credential theft. Outbound transaction held to prevent financial loss.'
            : 'High-confidence AI clone during high-value authorization — outbound transaction held pending verification.'}
        </p>
        <div className="mt-3 grid grid-cols-3 gap-2 mono text-data">
          <div><p className="eyebrow">Risk</p><p className="text-risk-high font-semibold">{risk}%</p></div>
          <div><p className="eyebrow">Status</p><p className="text-risk-high font-semibold">HELD</p></div>
          <div className="min-w-0"><p className="eyebrow">Ref</p><p className="text-navy truncate">{hold.reference}</p></div>
        </div>
      </div>
    );
  }
  return (
    <div className="panel p-4">
      <span className="eyebrow text-navy">Prevention Action</span>
      <p className="text-body-sm text-muted mt-1.5">
        {verdict === 'FRAUD' ? 'Threshold crossed — hold pending backend confirmation.' : 'Passive monitoring — no intervention triggered.'}
      </p>
    </div>
  );
}

function ConversationalIntelligencePanel({ vs }: any) {
  const isVishing = vs.data.threatCategory === 'HUMAN_VISHING';
  const isSynthetic = vs.data.threatCategory === 'AI_SYNTHETIC';
  const isLegit = vs.data.threatCategory === 'LEGITIMATE_HUMAN';

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow text-navy flex items-center gap-1.5">
          <MessageSquareQuote className="w-3.5 h-3.5 text-brand" /> Layer 2 · Conversational Intent & Social Engineering
        </span>
        <span className={`mono text-data-sm px-2 py-0.5 rounded font-semibold text-[10px] ${
          isVishing ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
          isSynthetic ? 'bg-red-500/20 text-red-400 border border-red-500/40' :
          isLegit ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
          'bg-surface-high text-muted'
        }`}>
          {isVishing ? '⚠️ HUMAN VISHING SCAM' :
           isSynthetic ? '🤖 AI DEEPFAKE CLONE' :
           isLegit ? '🛡️ LEGITIMATE CONVERSATION' :
           'LISTENING FOR SPEECH'}
        </span>
      </div>

      <div className="mt-3 p-3 rounded bg-surface-low border border-line min-h-[64px]">
        <p className="eyebrow text-muted text-[10px] mb-1">LIVE ASR TRANSCRIPTION (FASTER-WHISPER)</p>
        <p className="text-body-sm text-ink leading-relaxed">
          {vs.data.transcript ? (
            <span className="italic font-mono">"{vs.data.transcript}"</span>
          ) : (
            <span className="text-muted italic">Awaiting spoken words from caller stream…</span>
          )}
        </p>
      </div>

      {vs.data.reasons?.length > 0 && (
        <div className="mt-3">
          <p className="eyebrow text-muted text-[10px] mb-1.5">DETECTED SCAM TACTICS & SOCIAL ENGINEERING SIGNALS</p>
          <div className="flex flex-wrap gap-1.5">
            {vs.data.reasons.map((r: string, idx: number) => (
              <span key={idx} className="mono text-data-sm bg-risk-high/10 text-risk-high border border-risk-high/30 px-2 py-0.5 rounded">
                🚨 {r}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EvidencePanel({ hasResults, held }: any) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow text-navy flex items-center gap-1.5"><Lock className="w-3.5 h-3.5 text-evidence" /> Evidence Record</span>
        <span className={`mono text-data-sm px-1.5 py-0.5 rounded-sm ${held ? 'bg-evidence text-white' : hasResults ? 'bg-brand-soft text-brand' : 'bg-surface-high text-muted'}`}>
          {held ? 'SEALED' : hasResults ? 'LOGGING' : 'PENDING'}
        </span>
      </div>
      <p className="text-body-sm text-muted mt-1.5">
        {hasResults ? 'Ed25519-signed SHA-256 chain — no raw audio stored.' : 'No records yet for this session.'}
      </p>
      <Link href="/evidence" className="inline-flex items-center gap-1 text-body-sm text-brand hover:text-brand-dark mt-2">
        Inspect Evidence Chain <ChevronRight className="w-4 h-4" />
      </Link>
    </div>
  );
}

function Field({ k, v, sub, vClass = 'text-navy' }: any) {
  return (
    <div className="bg-surface-low border border-line rounded p-3">
      <p className="eyebrow">{k}</p>
      <p className={`text-body-sm font-semibold mt-1 ${vClass}`}>{v}</p>
      <p className="mono text-data-sm text-muted mt-0.5">{sub}</p>
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
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}
