'use client';

import { GitBranch } from 'lucide-react';

export interface RailState {
  monitoring: boolean;
  hasResults: boolean;
  vadActive: boolean;
  verdict: 'REAL' | 'SUSPICIOUS' | 'FRAUD' | 'WAITING';
  spoofProbability: number; // 0..100
  sourceLabel: string;
  held: boolean;
  holdReference?: string | null;
}

type Tone = 'neutral' | 'blue' | 'green' | 'amber' | 'red' | 'indigo';

const toneClass: Record<Tone, string> = {
  neutral: 'bg-surface-high text-muted',
  blue: 'bg-brand-soft text-brand',
  green: 'bg-low-soft text-risk-low border border-low-line',
  amber: 'bg-med-soft text-risk-med border border-med-line',
  red: 'bg-risk-high text-white',
  indigo: 'bg-evidence text-white',
};

function verdictTone(v: RailState['verdict']): Tone {
  return v === 'FRAUD' ? 'red' : v === 'SUSPICIOUS' ? 'amber' : v === 'REAL' ? 'green' : 'neutral';
}

export function VoiceIntegrityRail(s: RailState) {
  const analysisBadge =
    s.verdict === 'FRAUD' ? 'HIGH RISK' : s.verdict === 'SUSPICIOUS' ? 'REVIEW' :
    s.verdict === 'REAL' ? 'CLEAR' : 'PENDING';

  const stages: { no: string; title: string; badge: string; tone: Tone; l1: string; l2: string }[] = [
    {
      no: '01', title: 'CALL', badge: s.monitoring ? 'LIVE' : s.hasResults ? 'ENDED' : 'IDLE',
      tone: s.monitoring ? 'blue' : 'neutral',
      l1: 'Active Stream', l2: s.sourceLabel,
    },
    {
      no: '02', title: 'AUDIO', badge: s.vadActive ? 'SPEECH' : s.monitoring ? 'LISTEN' : '—',
      tone: s.vadActive ? 'blue' : 'neutral',
      l1: '8 kHz Telephony', l2: s.vadActive ? 'VAD active' : 'Silero VAD',
    },
    {
      no: '03', title: 'ANALYSIS', badge: analysisBadge, tone: verdictTone(s.verdict),
      l1: s.verdict === 'FRAUD' ? 'Synthetic profile' : s.verdict === 'REAL' ? 'Natural vocal tract' : 'Dual-branch',
      l2: s.verdict === 'WAITING' ? 'awaiting speech' : 'Vocoder match',
    },
    {
      no: '04', title: 'RISK ENGINE', badge: s.verdict === 'WAITING' ? '—' : `${s.spoofProbability}%`,
      tone: verdictTone(s.verdict),
      l1: 'Synthetic prob.', l2: s.verdict === 'FRAUD' ? 'CLASS synthetic' : s.verdict === 'REAL' ? 'CLASS authentic' : '—',
    },
    {
      no: '05', title: 'ACTION', badge: s.held ? 'HELD' : s.verdict === 'FRAUD' ? 'INTERCEPT' : 'MONITOR',
      tone: s.held || s.verdict === 'FRAUD' ? 'red' : 'neutral',
      l1: s.held ? 'Transaction hold' : 'Enforcement', l2: s.holdReference ?? (s.held ? 'hold active' : 'passive'),
    },
    {
      no: '06', title: 'EVIDENCE', badge: s.held ? 'SEALED' : s.hasResults ? 'LOGGING' : 'PENDING',
      tone: s.held ? 'indigo' : s.hasResults ? 'blue' : 'neutral',
      l1: 'SHA-256 ledger', l2: s.hasResults ? 'signed chain' : 'no records',
    },
  ];

  return (
    <div className="panel p-2.5">
      <div className="flex items-center justify-between px-1 pb-1.5">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-brand" />
          <span className="eyebrow text-navy">Voice Integrity Pipeline</span>
          <span className="mono text-data-sm text-muted">// dual-branch deterministic engine</span>
        </div>
        <span className="mono text-data-sm text-muted hidden lg:inline">DETECT · PREVENT · PROVE</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-1.5">
        {stages.map((st) => (
          <div key={st.no} className="relative bg-surface-low border border-line p-2.5 rounded flex flex-col justify-between min-h-[88px]">
            <div className="flex items-start justify-between gap-1">
              <span className="mono text-data-sm text-muted">{st.no} <span className="text-navy font-semibold">// {st.title}</span></span>
              <span className={`shrink-0 mono text-data-sm px-1.5 py-0.5 rounded-sm font-semibold tracking-wide ${toneClass[st.tone]}`}>{st.badge}</span>
            </div>
            <div className="mt-2">
              <p className="text-body-sm text-navy font-semibold leading-tight">{st.l1}</p>
              <p className="mono text-data-sm text-muted leading-tight">{st.l2}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
