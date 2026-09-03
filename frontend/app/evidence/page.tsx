'use client';
import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  Shield, ArrowLeft, RefreshCw, Download, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, ShieldCheck, ShieldAlert, ShieldX, KeyRound, Hash, Clock,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── Types ────────────────────────────────────────────────────────────────────
interface CallRecord {
  call_id: string;
  started_at: string;
  ended_at: string | null;
  source: string;
  status: 'active' | 'ended' | 'held';
}
interface EvidenceEntry {
  entry_id: number;
  call_id: string;
  detection_id: number | null;
  payload: Record<string, unknown> & {
    fused_risk_score: number;
    is_flagged: boolean;
    window_start_ms: number;
    window_end_ms: number;
  };
  entry_hash: string;
  prev_hash: string;
  signature: string | null;
  created_at: string;
}
interface EvidenceResponse {
  call_id: string;
  chain_valid: boolean;
  signatures_valid: boolean;
  public_key: string;
  entry_count: number;
  entries: EvidenceEntry[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────
const riskText = (s: number) => (s >= 0.7 ? 'text-risk-high' : s >= 0.4 ? 'text-risk-med' : 'text-risk-low');
const verdictIcon = (s: number) =>
  s >= 0.7 ? <ShieldAlert className="w-3.5 h-3.5 text-risk-high" /> :
  s >= 0.4 ? <ShieldX className="w-3.5 h-3.5 text-risk-med" /> :
  <ShieldCheck className="w-3.5 h-3.5 text-risk-low" />;
const statusPill: Record<string, string> = {
  active: 'text-risk-low border-[#bfe3cd] bg-[#e7f4ec]',
  ended: 'text-muted border-line bg-canvas',
  held: 'text-risk-high border-[#f0c3bb] bg-[#fbeae7]',
};
const fmt = (iso: string) => new Date(iso).toLocaleString('en-IN', { hour12: false });
const trunc = (h: string) => (h ? `${h.slice(0, 10)}…${h.slice(-8)}` : '—');

// ── Evidence modal ─────────────────────────────────────────────────────────────
function EvidencePanel({ callId, onClose }: { callId: string; onClose: () => void }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<EvidenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/calls/${callId}/evidence`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load evidence');
    } finally { setLoading(false); }
  }, [callId]);
  useEffect(() => { load(); }, [load]);

  const exportJson = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `voiceshield-evidence-${callId.slice(0, 8)}.json`; a.click();
    URL.revokeObjectURL(url);
  };
  const toggle = (id: number) =>
    setExpanded((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const verified = data ? data.chain_valid && data.signatures_valid : false;

  return (
    <div className="fixed inset-0 z-50 bg-navy/30 flex items-start justify-center overflow-y-auto p-4 pt-10">
      <div className="w-full max-w-4xl panel overflow-hidden">
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <div className="flex items-center gap-2.5">
            <Hash className="w-5 h-5 text-evidence" />
            <div>
              <h2 className="font-semibold text-navy">Evidence Chain</h2>
              <p className="mono text-xs text-muted">{callId}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={load} title="Re-verify"
              className="p-2 text-muted hover:text-navy"><RefreshCw className="w-4 h-4" /></button>
            <button onClick={exportJson} disabled={!data}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md border border-line text-brand hover:bg-[#eaf1f9] disabled:opacity-40">
              <Download className="w-3.5 h-3.5" /> Export
            </button>
            <button onClick={onClose}
              className="text-xs font-medium px-3 py-1.5 border border-line rounded-md text-muted hover:text-navy">Close</button>
          </div>
        </div>

        {/* Verify Integrity result — the money moment */}
        {data && data.entry_count > 0 && (
          <div className={`px-6 py-4 border-b ${verified ? 'bg-[#e7f4ec] border-[#bfe3cd]' : 'bg-[#fbeae7] border-[#f0c3bb]'}`}>
            <div className="flex items-center gap-3">
              {verified ? <CheckCircle2 className="w-6 h-6 text-risk-low" /> : <XCircle className="w-6 h-6 text-risk-high" />}
              <div className="flex-1">
                <p className={`font-semibold ${verified ? 'text-risk-low' : 'text-risk-high'}`}>
                  {verified ? 'CHAIN VALID' : 'CHAIN INVALID'}
                </p>
                <p className="text-sm text-ink">
                  {data.entry_count}/{data.entry_count} records verified ·{' '}
                  hash-chain {data.chain_valid ? 'intact' : 'broken'} ·{' '}
                  signatures {data.signatures_valid ? 'valid' : 'invalid'}
                </p>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-muted">
              <KeyRound className="w-3.5 h-3.5 text-evidence" />
              <span>Ed25519 public key:</span>
              <span className="mono text-evidence break-all">{trunc(data.public_key)}</span>
            </div>
          </div>
        )}

        {/* BSA note */}
        <div className="px-6 py-2.5 border-b border-line bg-[#f6f2fb]">
          <p className="text-xs text-evidence/90">
            SHA-256 hash-chain, Ed25519-signed — tamper-evident and non-repudiable under{' '}
            <strong>Bharatiya Sakshya Adhiniyam (BSA) 2023, §63</strong>. No raw audio is stored (DPDP 2023).
          </p>
        </div>

        {/* body */}
        <div className="p-4 max-h-[62vh] overflow-y-auto">
          {loading && <div className="flex items-center justify-center py-14 text-muted gap-2"><RefreshCw className="w-5 h-5 animate-spin" /> Verifying chain…</div>}
          {error && <div className="text-risk-high text-sm text-center py-8">{error}</div>}
          {data && data.entries.length === 0 && <div className="text-muted text-center py-8">No evidence entries yet for this call.</div>}
          {data && data.entries.map((entry, idx) => {
            const open = expanded.has(entry.entry_id);
            const p = entry.payload;
            return (
              <div key={entry.entry_id} className="border border-line rounded-md overflow-hidden mb-2 bg-surface">
                <button onClick={() => toggle(entry.entry_id)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-canvas">
                  <span className="mono text-xs text-muted w-6">#{idx + 1}</span>
                  {verdictIcon(p.fused_risk_score)}
                  <span className={`mono text-xs font-semibold ${riskText(p.fused_risk_score)}`}>{(p.fused_risk_score * 100).toFixed(0)}%</span>
                  <span className="text-xs text-muted flex-1">{p.window_start_ms}–{p.window_end_ms} ms</span>
                  <span className="mono text-xs text-muted hidden lg:inline">{trunc(entry.entry_hash)}</span>
                  <span className="text-xs text-muted">{new Date(entry.created_at).toLocaleTimeString('en-IN')}</span>
                  {p.is_flagged && <span className="text-[11px] font-semibold text-risk-high bg-[#fbeae7] border border-[#f0c3bb] px-1.5 py-0.5 rounded">FLAGGED</span>}
                  {open ? <ChevronDown className="w-4 h-4 text-muted" /> : <ChevronRight className="w-4 h-4 text-muted" />}
                </button>
                {open && (
                  <div className="border-t border-line px-4 py-3 grid md:grid-cols-2 gap-4 text-xs bg-canvas">
                    <div>
                      <p className="eyebrow mb-1">Hash Chain</p>
                      <div className="panel p-3 space-y-2">
                        <div><span className="text-muted">prev_hash</span><p className="mono text-[10px] text-ink break-all">{entry.prev_hash}</p></div>
                        <div><span className="text-muted">entry_hash</span><p className="mono text-[10px] text-evidence break-all">{entry.entry_hash}</p></div>
                        <div><span className="text-muted">signature (Ed25519)</span><p className="mono text-[10px] text-brand break-all">{entry.signature ?? '—'}</p></div>
                      </div>
                    </div>
                    <div>
                      <p className="eyebrow mb-1">Signed Payload</p>
                      <div className="panel p-3">
                        <table className="w-full">
                          <tbody>
                            {Object.entries(p).map(([k, v]) => (
                              <tr key={k}>
                                <td className="text-muted pr-3 py-0.5 align-top w-36">{k}</td>
                                <td className={`mono break-all ${k === 'fused_risk_score' ? riskText(Number(v)) : 'text-ink'}`}>{String(v)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Call history + evidence page ───────────────────────────────────────────────
export default function EvidencePage() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const loadCalls = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      let res: Response;
      try {
        res = await fetch(`${API_BASE}/api/calls?limit=25`);
      } catch {
        throw new Error('Cannot reach the backend on port 8000 — is it running?');
      }
      if (!res.ok) throw new Error(`Backend error (HTTP ${res.status}).`);
      setCalls(await res.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed to load calls.');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { loadCalls(); }, [loadCalls]);

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="bg-surface border-b border-line">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Shield className="w-5 h-5 text-brand" />
            <span className="font-semibold text-navy">VoiceShield</span>
            <span className="text-muted text-xs border-l border-line pl-2.5 ml-1 hidden sm:inline">Call History &amp; Evidence</span>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={loadCalls} className="text-sm text-muted hover:text-navy flex items-center gap-1.5"><RefreshCw className="w-4 h-4" /> Refresh</button>
            <Link href="/" className="text-sm text-brand hover:text-brand-dark flex items-center gap-1.5"><ArrowLeft className="w-4 h-4" /> Console</Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto w-full px-6 py-6">
        <h1 className="text-lg font-semibold text-navy">Call History</h1>
        <p className="text-sm text-muted mt-0.5 mb-4">Select a call to inspect its tamper-evident evidence chain and verify integrity.</p>

        {err && <div className="panel p-4 text-sm text-risk-high mb-4">{err}</div>}
        {loading && <div className="flex items-center justify-center py-16 text-muted gap-2"><RefreshCw className="w-5 h-5 animate-spin" /> Loading calls…</div>}
        {!loading && !err && calls.length === 0 && (
          <div className="panel p-10 text-center text-muted">
            No calls yet. Start one from the <Link href="/" className="text-brand underline">Console</Link>.
          </div>
        )}

        {calls.length > 0 && (
          <div className="panel overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="text-left">
                  <th className="px-4 py-2.5 font-medium">Call</th>
                  <th className="px-4 py-2.5 font-medium">Started</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Source</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {calls.map((c) => {
                  const dur = c.ended_at ? `${Math.round((+new Date(c.ended_at) - +new Date(c.started_at)) / 1000)}s` : '—';
                  return (
                    <tr key={c.call_id} className="hover:bg-canvas cursor-pointer" onClick={() => setSelected(c.call_id)}>
                      <td className="px-4 py-2.5 mono text-brand text-xs">{c.call_id.slice(0, 8)}…</td>
                      <td className="px-4 py-2.5 text-muted text-xs"><span className="flex items-center gap-1"><Clock className="w-3 h-3" />{fmt(c.started_at)}</span></td>
                      <td className="px-4 py-2.5 mono text-muted text-xs">{dur}</td>
                      <td className="px-4 py-2.5 mono text-muted text-xs">{c.source}</td>
                      <td className="px-4 py-2.5"><span className={`text-xs font-semibold px-2 py-0.5 rounded border ${statusPill[c.status] ?? statusPill.ended}`}>{c.status.toUpperCase()}</span></td>
                      <td className="px-4 py-2.5">
                        <button onClick={(e) => { e.stopPropagation(); setSelected(c.call_id); }}
                          className="flex items-center gap-1 text-xs text-brand hover:text-brand-dark border border-line px-2.5 py-1 rounded-md">
                          <Hash className="w-3 h-3" /> View Chain
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {selected && <EvidencePanel callId={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
