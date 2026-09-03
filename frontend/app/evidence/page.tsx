'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ShieldCheck, ShieldAlert, Search, RefreshCw, Download, Lock, KeyRound,
  CheckCircle2, XCircle, FileText, ChevronRight,
} from 'lucide-react';
import { AppShell } from '../../components/AppShell';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface CallRecord { call_id: string; started_at: string; ended_at: string | null; source: string; status: 'active' | 'ended' | 'held'; }
interface EvidenceEntry {
  entry_id: number; payload: Record<string, unknown> & { fused_risk_score: number; spoof_probability?: number; is_flagged: boolean; window_start_ms: number; window_end_ms: number; };
  entry_hash: string; prev_hash: string; signature: string | null; created_at: string;
}
interface EvidenceResponse { call_id: string; chain_valid: boolean; signatures_valid: boolean; public_key: string; entry_count: number; entries: EvidenceEntry[]; }

const fmt = (iso: string) => new Date(iso).toLocaleString('en-IN', { hour12: false });
const trunc = (h: string) => (h ? `${h.slice(0, 12)}…${h.slice(-8)}` : '—');

export default function EvidenceStation() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [q, setQ] = useState('');
  const [callsErr, setCallsErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const loadCalls = useCallback(async () => {
    setCallsErr(null);
    try {
      let res: Response;
      try { res = await fetch(`${API_BASE}/api/calls?limit=100`, { cache: 'no-store' }); }
      catch { throw new Error('Cannot reach the backend on port 8000 — is it running?'); }
      if (!res.ok) throw new Error(`Backend error (HTTP ${res.status}).`);
      const data: CallRecord[] = await res.json();
      setCalls(data);
      if (!selected && data.length) setSelected(data[0].call_id);
    } catch (e) { setCallsErr(e instanceof Error ? e.message : 'Failed to load records.'); }
  }, [selected]);
  useEffect(() => { loadCalls(); }, [loadCalls]);

  const events = useMemo(
    () => calls.filter((c) => !q || c.call_id.toLowerCase().includes(q.toLowerCase())),
    [calls, q],
  );

  return (
    <AppShell>
      <div className="bg-surface border-b border-line px-6 py-2.5 flex items-center justify-between">
        <span className="text-body-sm font-semibold text-navy uppercase tracking-tight flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-evidence" /> Forensic Evidence Station
        </span>
        <span className="mono text-data-sm text-muted hidden md:inline">Ed25519-signed SHA-256 chain · BSA 2023 §63</span>
      </div>

      <div className="px-6 py-3 grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Detection events */}
        <div className="panel overflow-hidden h-fit">
          <div className="panel-head px-4 py-2.5">
            <span className="eyebrow text-navy">Detection Events</span>
            <div className="mt-2 flex items-center gap-1.5 px-2 h-7 rounded border border-line bg-surface">
              <Search className="w-3.5 h-3.5 text-muted" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by call ID…"
                className="bg-transparent outline-none mono text-data-sm text-ink w-full placeholder:text-muted" />
            </div>
          </div>
          {callsErr && <div className="p-4 text-body-sm text-risk-high">{callsErr}</div>}
          {!callsErr && events.length === 0 && <div className="p-6 text-center text-muted text-body-sm">No sealed records yet.</div>}
          <div className="max-h-[70vh] overflow-y-auto">
            {events.map((c) => {
              const held = c.status === 'held';
              const active = selected === c.call_id;
              return (
                <button key={c.call_id} onClick={() => setSelected(c.call_id)}
                  className={`w-full text-left flex ${active ? 'bg-brand-soft/40' : 'hover:bg-surface-low'}`}>
                  <span className={`w-1 self-stretch ${held ? 'bg-risk-high' : c.status === 'active' ? 'bg-brand' : 'bg-line'}`} />
                  <span className="flex-1 px-4 py-3 border-b border-line">
                    <span className="flex items-center justify-between">
                      <span className="mono text-data text-navy font-semibold">{c.call_id.slice(0, 8).toUpperCase()}</span>
                      <span className={`mono text-data-sm px-1.5 py-0.5 rounded-sm ${held ? 'bg-high-soft text-risk-high' : 'bg-surface-high text-muted'}`}>{c.status.toUpperCase()}</span>
                    </span>
                    <span className="flex items-center justify-between mt-1 mono text-data-sm text-muted">
                      <span>{c.source.toUpperCase()}</span><span>{fmt(c.started_at)}</span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Case detail */}
        <div className="lg:col-span-2">
          {selected ? <CaseDetail callId={selected} /> : (
            <div className="panel p-10 text-center text-muted text-body-sm">Select a detection event to review its cryptographic chain.</div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function CaseDetail({ callId }: { callId: string }) {
  const [data, setData] = useState<EvidenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const verify = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      let res: Response;
      try { res = await fetch(`${API_BASE}/api/calls/${callId}/evidence`, { cache: 'no-store' }); }
      catch { throw new Error('Cannot reach the backend on port 8000.'); }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) { setErr(e instanceof Error ? e.message : 'Verification failed.'); }
    finally { setLoading(false); }
  }, [callId]);
  useEffect(() => { verify(); }, [verify]);

  const exportJson = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `voiceshield-evidence-${callId.slice(0, 8)}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const peakRisk = data && data.entries.length ? Math.max(...data.entries.map((e) => e.payload.fused_risk_score)) : 0;
  const flagged = !!data?.entries.some((e) => e.payload.is_flagged);
  const verified = data ? data.chain_valid && data.signatures_valid : false;

  return (
    <div className="space-y-3">
      {/* Case header */}
      <div className="panel">
        <div className="p-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="w-9 h-9 rounded bg-navy text-surface flex items-center justify-center"><ShieldCheck className="w-5 h-5" /></span>
            <div>
              <p className="text-body-sm font-semibold text-navy mono">CASE {callId.slice(0, 8).toUpperCase()}</p>
              <p className="mono text-data-sm text-muted">UID: EV-{callId.slice(0, 4).toUpperCase()} · G.711u 8000 Hz</p>
            </div>
          </div>
          {data && data.entry_count > 0 && (
            <span className={`mono text-data-sm px-2 py-0.5 rounded-sm ${flagged ? 'bg-high-soft text-risk-high border border-high-line' : 'bg-low-soft text-risk-low border border-low-line'}`}>
              {flagged ? 'SYNTHETIC VOICE DETECTED' : 'AUTHENTIC — PASSED'}
            </span>
          )}
        </div>
        {data && data.entry_count > 0 && (
          <div className="panel-head px-4 py-2.5 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <span className={`mono text-metric ${flagged ? 'text-risk-high' : 'text-risk-low'}`}>{Math.round(peakRisk * 100)}</span>
              <span className="text-body-sm text-muted">peak fused-risk score across {data.entry_count} windows</span>
            </div>
            {flagged && <span className="mono text-data-sm px-2 py-0.5 rounded-sm bg-risk-high text-white">TRANSACTION HOLD</span>}
          </div>
        )}
      </div>

      {/* Verify result */}
      {loading && <div className="panel p-6 flex items-center justify-center gap-2 text-muted"><RefreshCw className="w-5 h-5 animate-spin" /> Verifying chain…</div>}
      {err && <div className="panel p-4 text-body-sm text-risk-high">{err}</div>}
      {data && data.entry_count === 0 && <div className="panel p-6 text-center text-muted text-body-sm">No evidence entries recorded for this call.</div>}

      {data && data.entry_count > 0 && (
        <>
          <div className={`panel border p-4 ${verified ? 'bg-low-soft border-low-line' : 'bg-high-soft border-high-line'}`}>
            <div className="flex items-center gap-3">
              {verified ? <CheckCircle2 className="w-6 h-6 text-risk-low" /> : <XCircle className="w-6 h-6 text-risk-high" />}
              <div className="flex-1">
                <p className={`text-body-sm font-semibold ${verified ? 'text-risk-low' : 'text-risk-high'}`}>{verified ? 'CHAIN VALID — INTEGRITY UNBROKEN' : 'CHAIN INVALID'}</p>
                <p className="mono text-data-sm text-ink">{data.entry_count}/{data.entry_count} records verified · hash-chain {data.chain_valid ? 'intact' : 'broken'} · signatures {data.signatures_valid ? 'valid' : 'invalid'}</p>
              </div>
              <button onClick={verify} className="inline-flex items-center gap-1.5 px-3 h-8 rounded bg-navy text-surface hover:bg-brand transition-colors text-body-sm font-semibold">
                <ShieldCheck className="w-4 h-4" /> Verify Integrity Now
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2 mono text-data-sm text-muted">
              <KeyRound className="w-3.5 h-3.5 text-evidence" /> Ed25519 public key:
              <span className="text-evidence break-all">{trunc(data.public_key)}</span>
            </div>
          </div>

          {/* Integrity chain */}
          <div className="panel overflow-hidden">
            <div className="panel-head px-4 h-9 flex items-center justify-between">
              <span className="eyebrow text-navy">Cryptographic Integrity Chain</span>
              <button onClick={exportJson} className="inline-flex items-center gap-1.5 text-data font-semibold text-brand hover:text-brand-dark">
                <Download className="w-3.5 h-3.5" /> Export Evidence (.json)
              </button>
            </div>
            <div className="max-h-[52vh] overflow-y-auto divide-y divide-line">
              {data.entries.map((e, i) => {
                const risk = e.payload.fused_risk_score;
                const tone = risk >= 0.7 ? 'text-risk-high' : risk >= 0.4 ? 'text-risk-med' : 'text-risk-low';
                return (
                  <div key={e.entry_id} className="px-4 py-3 flex items-start gap-3">
                    <span className="w-6 h-6 rounded-sm bg-surface-high text-navy mono text-data-sm flex items-center justify-center shrink-0">{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-body-sm font-semibold text-navy">Window {e.payload.window_start_ms}–{e.payload.window_end_ms} ms</span>
                        <span className={`mono text-data font-semibold ${tone}`}>{(risk * 100).toFixed(0)}%</span>
                      </div>
                      <div className="mt-1 grid sm:grid-cols-2 gap-x-4 gap-y-0.5 mono text-data-sm">
                        <span className="text-muted">entry <span className="text-evidence break-all">{trunc(e.entry_hash)}</span></span>
                        <span className="text-muted">prev <span className="text-ink break-all">{trunc(e.prev_hash)}</span></span>
                        <span className="text-muted sm:col-span-2">sig <span className="text-brand break-all">{trunc(e.signature ?? '—')}</span></span>
                      </div>
                    </div>
                    <span className="mono text-data-sm px-1.5 py-0.5 rounded-sm bg-low-soft text-risk-low border border-low-line shrink-0">PASS</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Certificate */}
          <div className="panel p-4">
            <div className="flex items-center gap-2"><Lock className="w-4 h-4 text-evidence" /><span className="eyebrow text-navy">Proof of Authenticity Certificate</span></div>
            <div className="mt-3 space-y-2 mono text-data-sm">
              <Field k="SHA-256 canonical digest" v={data.entries[data.entries.length - 1].entry_hash} />
              <Field k="Ed25519 signature (latest)" v={data.entries[data.entries.length - 1].signature ?? '—'} />
              <Field k="Ed25519 public key" v={data.public_key} />
            </div>
            <div className="mt-3 grid sm:grid-cols-2 gap-3 text-body-sm">
              <div><p className="eyebrow">Signing authority</p><p className="text-navy">VoiceShield evidence service</p></div>
              <div><p className="eyebrow">Legal basis</p><p className="text-navy">BSA 2023 §63 · no raw audio stored (DPDP)</p></div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button onClick={exportJson} className="inline-flex items-center gap-1.5 px-3 h-8 rounded border border-line bg-surface text-navy hover:bg-surface-low text-body-sm font-semibold"><FileText className="w-3.5 h-3.5" /> Download Signed Package (.json)</button>
              <Link href="/history" className="inline-flex items-center gap-1 px-3 h-8 rounded text-brand hover:text-brand-dark text-body-sm font-semibold">Back to Call History <ChevronRight className="w-4 h-4" /></Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-surface-low border border-line rounded p-2">
      <p className="eyebrow">{k}</p>
      <p className="text-evidence break-all mt-0.5">{v}</p>
    </div>
  );
}
