'use client';

import Link from 'next/link';
import { useState } from 'react';
import {
  FlaskConical, Play, Square, ShieldAlert, ShieldCheck, Activity, Lock, ChevronRight, AudioWaveform,
} from 'lucide-react';
import { AppShell } from '../../components/AppShell';
import { VoiceIntegrityRail } from '../../components/VoiceIntegrityRail';
import { useVoiceShield, type Verdict } from '../../hooks/useVoiceShield';

interface Vector {
  id: string; file: string; type: 'REAL' | 'CLONED'; lang: string; desc: string; codec: string;
}
const VECTORS: Vector[] = [
  { id: 'VS-A-8041', file: '/demo/real_en.wav', type: 'REAL', lang: 'English', desc: 'Inbound customer authentication — wire verification', codec: '8 kHz G.711u / PSTN' },
  { id: 'VS-B-9912', file: '/demo/cloned_en.wav', type: 'CLONED', lang: 'English', desc: 'Executive impersonation — wire fraud (XTTS clone)', codec: '8 kHz PCM / RTP' },
  { id: 'VS-C-3387', file: '/demo/real_hi.wav', type: 'REAL', lang: 'Hindi', desc: 'Customer support inquiry — regional gateway', codec: '8 kHz G.711a' },
  { id: 'VS-D-4490', file: '/demo/cloned_hi.wav', type: 'CLONED', lang: 'Hindi', desc: 'Synthetic voice — banking OTP extraction', codec: '8 kHz Opus' },
];

function riskMeta(v: Verdict) {
  switch (v) {
    case 'REAL': return { label: 'AUTHENTIC VOICE', text: 'text-risk-low', soft: 'bg-low-soft border-low-line' };
    case 'SUSPICIOUS': return { label: 'REVIEW REQUIRED', text: 'text-risk-med', soft: 'bg-med-soft border-med-line' };
    case 'FRAUD': return { label: 'SYNTHETIC VOICE DETECTED', text: 'text-risk-high', soft: 'bg-high-soft border-high-line' };
    default: return { label: 'AWAITING ANALYSIS', text: 'text-muted', soft: 'bg-surface-low border-line' };
  }
}

export default function ReplayLab() {
  const vs = useVoiceShield();
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const hasResults = vs.logs.length > 0 || vs.hold !== null;

  const analyze = (v: Vector) => {
    setActiveFile(v.file);
    vs.startReplay(v.file, `${v.type === 'CLONED' ? 'Cloned' : 'Real'} · ${v.lang}`);
  };

  return (
    <AppShell>
      <div className="bg-surface border-b border-line px-6 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-body-sm font-semibold text-navy uppercase tracking-tight flex items-center gap-1.5">
            <FlaskConical className="w-4 h-4 text-brand" /> Replay Lab
          </span>
          <span className="mono text-data-sm px-1.5 py-0.5 rounded-sm bg-surface-high text-muted">SANDBOX ISOLATED</span>
          <span className="hidden md:inline text-body-sm text-muted">Run recorded calls through the real dual-branch pipeline.</span>
        </div>
        {vs.isMonitoring && (
          <button onClick={() => { vs.stop(); setActiveFile(null); }}
            className="inline-flex items-center gap-2 px-3 h-8 rounded bg-high-soft text-risk-high border border-high-line hover:bg-risk-high hover:text-white transition-colors text-body-sm font-semibold">
            <Square className="w-3.5 h-3.5" /> Stop
          </button>
        )}
      </div>
      {vs.error && <div className="bg-med-soft border-b border-med-line text-risk-med text-body-sm px-6 py-2">{vs.error}</div>}

      <div className="px-6 py-3 space-y-3">
        {/* Source selection console */}
        <div className="panel overflow-hidden">
          <div className="panel-head px-4 h-9 flex items-center justify-between">
            <span className="eyebrow text-navy">Controlled Source Selection Console</span>
            <span className="mono text-data-sm text-muted">4 benchmark vectors</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-body-sm min-w-[720px]">
              <thead className="text-muted">
                <tr className="text-left">
                  <th className="px-4 py-2 font-medium eyebrow">Vector</th>
                  <th className="px-4 py-2 font-medium eyebrow">Sample (ground truth)</th>
                  <th className="px-4 py-2 font-medium eyebrow">Scenario</th>
                  <th className="px-4 py-2 font-medium eyebrow">Codec</th>
                  <th className="px-4 py-2 font-medium eyebrow">Engine</th>
                  <th className="px-4 py-2 font-medium eyebrow text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {VECTORS.map((v) => {
                  const active = vs.isMonitoring && activeFile === v.file;
                  const clone = v.type === 'CLONED';
                  return (
                    <tr key={v.id} className={active ? 'bg-brand-soft/40' : 'hover:bg-surface-low'}
                      style={active ? { boxShadow: 'inset 2px 0 0 rgb(var(--c-brand))' } : undefined}>
                      <td className="px-4 py-2.5 mono text-data text-brand whitespace-nowrap">{v.id}</td>
                      <td className="px-4 py-2.5">
                        <span className={`mono text-data-sm px-1.5 py-0.5 rounded-sm ${clone ? 'bg-high-soft text-risk-high border border-high-line' : 'bg-low-soft text-risk-low border border-low-line'}`}>
                          {clone ? 'CLONED' : 'REAL'} — {v.lang.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-ink">{v.desc}</td>
                      <td className="px-4 py-2.5 mono text-data-sm text-muted whitespace-nowrap">{v.codec}</td>
                      <td className="px-4 py-2.5">
                        <span className={`mono text-data-sm px-1.5 py-0.5 rounded-sm ${active ? 'bg-brand text-white' : 'bg-surface-high text-muted'}`}>
                          {active ? 'ACTIVE IN LAB' : 'STANDBY'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button onClick={() => analyze(v)} disabled={vs.isMonitoring}
                          className="inline-flex items-center gap-1.5 px-2.5 h-7 rounded bg-navy text-surface hover:bg-brand disabled:opacity-40 transition-colors text-data font-semibold">
                          <Play className="w-3 h-3" /> Analyze
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <VoiceIntegrityRail
          monitoring={vs.isMonitoring}
          hasResults={hasResults}
          vadActive={vs.data.vadActive}
          verdict={vs.data.verdict}
          spoofProbability={vs.data.spoofProbability}
          sourceLabel={vs.replaySample ?? '—'}
          held={vs.hold !== null}
          holdReference={vs.hold?.reference}
        />

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          {/* Acoustic inspection */}
          <div className="xl:col-span-2 panel overflow-hidden">
            <div className="panel-head px-4 h-9 flex items-center justify-between">
              <span className="eyebrow text-navy flex items-center gap-1.5"><AudioWaveform className="w-3.5 h-3.5 text-brand" /> Acoustic Inspection Station</span>
              <span className="mono text-data-sm text-muted">{vs.replaySample ?? 'no source mounted'}</span>
            </div>
            <div className="bg-[#0b1420] p-4">
              <div className="flex items-center gap-[3px] h-32">
                {vs.waveform.map((b: number, i: number) => (
                  <div key={i} className="flex-1 rounded-sm"
                    style={{
                      height: `${Math.max(b * 100, 2)}%`,
                      background: vs.data.verdict === 'FRAUD' && b > 0.25 ? '#ef5350' : vs.isMonitoring ? '#4f8fe0' : '#334155',
                      transition: 'height 110ms linear',
                    }} />
                ))}
              </div>
              <div className="mt-3 h-1.5 bg-[#1c2836] rounded-sm overflow-hidden">
                <div className="h-full bg-brand transition-all" style={{ width: `${Math.round(vs.replayProgress * 100)}%` }} />
              </div>
              <div className="flex items-center justify-between mono text-data-sm mt-2 text-[#7f93ad]">
                <span>{vs.isMonitoring ? 'Streaming 500 ms PCM chunks…' : hasResults ? 'Analysis complete' : 'Select a vector to analyze'}</span>
                <span>{Math.round(vs.replayProgress * 100)}%</span>
              </div>
            </div>
          </div>

          {/* Verdict report */}
          <div className="space-y-3">
            <VerdictReport vs={vs} />
            <ForensicBreakdown vs={vs} />
            {vs.hold && <HoldSeal hold={vs.hold} risk={vs.data.riskScore} />}
            <EvidenceSeal hasResults={hasResults} held={vs.hold !== null} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function VerdictReport({ vs }: any) {
  const m = riskMeta(vs.data.verdict);
  const Icon = vs.data.verdict === 'FRAUD' ? ShieldAlert : vs.data.verdict === 'REAL' ? ShieldCheck : Activity;
  return (
    <div className={`panel border ${m.soft} p-4`}>
      <div className="flex items-center gap-2"><Icon className={`w-5 h-5 ${m.text}`} />
        <span className={`text-body-sm font-semibold ${m.text}`}>{m.label}</span></div>
      <div className="mt-3 flex items-end justify-between">
        <div><p className="eyebrow">Model confidence</p>
          <p className={`mono text-metric ${m.text}`}>{vs.data.verdict === 'WAITING' ? '—' : `${vs.data.spoofProbability}%`}</p></div>
        <div className="text-right"><p className="eyebrow">Fused risk</p>
          <p className={`mono text-metric ${m.text}`}>{vs.data.riskScore}</p></div>
      </div>
    </div>
  );
}

function ForensicBreakdown({ vs }: any) {
  return (
    <div className="panel p-4">
      <span className="eyebrow text-navy">Forensic Breakdown</span>
      <dl className="mt-2 space-y-2 mono text-data">
        <Row k="Synthetic prob." v={vs.data.verdict === 'WAITING' ? '—' : `${vs.data.spoofProbability}%`} vClass={vs.data.verdict === 'FRAUD' ? 'text-risk-high' : 'text-navy'} />
        <Row k="Fused risk" v={`${vs.data.riskScore}%`} />
        <Row k="Verdict" v={vs.data.verdict} vClass={vs.data.verdict === 'FRAUD' ? 'text-risk-high' : vs.data.verdict === 'REAL' ? 'text-risk-low' : 'text-muted'} />
        <Row k="Windows analysed" v={String(vs.logs.length)} />
      </dl>
      {vs.data.reasons?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {vs.data.reasons.slice(0, 4).map((r: string, i: number) => (
            <span key={i} className="mono text-data-sm bg-surface-low border border-line text-muted px-1.5 py-0.5 rounded-sm">{r}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function HoldSeal({ hold, risk }: any) {
  return (
    <div className="panel border border-high-line bg-high-soft p-4">
      <div className="flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-risk-high" />
        <span className="text-body-sm font-semibold text-risk-high">Transaction Hold Active</span></div>
      <div className="mt-2 grid grid-cols-3 gap-2 mono text-data">
        <div><p className="eyebrow">Risk</p><p className="text-risk-high font-semibold">{risk}%</p></div>
        <div><p className="eyebrow">Status</p><p className="text-risk-high font-semibold">HELD</p></div>
        <div className="min-w-0"><p className="eyebrow">Ref</p><p className="text-navy truncate">{hold.reference}</p></div>
      </div>
    </div>
  );
}

function EvidenceSeal({ hasResults, held }: any) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow text-navy flex items-center gap-1.5"><Lock className="w-3.5 h-3.5 text-evidence" /> Cryptographic Seal</span>
        <span className={`mono text-data-sm px-1.5 py-0.5 rounded-sm ${held ? 'bg-evidence text-white' : hasResults ? 'bg-brand-soft text-brand' : 'bg-surface-high text-muted'}`}>
          {held ? 'SEALED' : hasResults ? 'LOGGED' : 'PENDING'}
        </span>
      </div>
      <p className="text-body-sm text-muted mt-1.5">Ed25519-signed SHA-256 chain · non-repudiable audit stamp.</p>
      <Link href="/evidence" className="inline-flex items-center gap-1 text-body-sm text-brand hover:text-brand-dark mt-2">
        Inspect Evidence Chain <ChevronRight className="w-4 h-4" />
      </Link>
    </div>
  );
}

function Row({ k, v, vClass = 'text-navy' }: { k: string; v: string; vClass?: string }) {
  return <div className="flex items-center justify-between"><dt className="text-muted uppercase">{k}</dt><dd className={`font-semibold ${vClass}`}>{v}</dd></div>;
}
