'use client';
import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Download,
  Hash,
  Clock,
  Phone,
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
  payload: {
    call_id: string;
    detection_id: number;
    fused_risk_score: number;
    is_flagged: boolean;
    model_version: string;
    server_timestamp: string;
    spoof_probability: number;
    window_end_ms: number;
    window_start_ms: number;
  };
  entry_hash: string;
  prev_hash: string;
  created_at: string;
}

interface EvidenceResponse {
  call_id: string;
  chain_valid: boolean;
  entry_count: number;
  entries: EvidenceEntry[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const statusColor: Record<string, string> = {
  active: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  ended:  'text-slate-400  bg-slate-500/10  border-slate-500/30',
  held:   'text-amber-400  bg-amber-500/10  border-amber-500/30',
};

const verdictIcon = (score: number) => {
  if (score >= 0.70) return <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />;
  if (score >= 0.40) return <ShieldX className="w-3.5 h-3.5 text-amber-400" />;
  return <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />;
};

const riskClass = (score: number) => {
  if (score >= 0.70) return 'text-rose-400';
  if (score >= 0.40) return 'text-amber-400';
  return 'text-emerald-400';
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString('en-IN', { hour12: false });
}

function truncHash(h: string) {
  return `${h.slice(0, 8)}…${h.slice(-8)}`;
}

// ── Evidence Panel (per call) ─────────────────────────────────────────────────

function EvidencePanel({ callId, onClose }: { callId: string; onClose: () => void }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<EvidenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/calls/${callId}/evidence`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [callId]);

  useEffect(() => { load(); }, [load]);

  const exportJson = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `voiceshield-evidence-${callId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleRow = (id: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4 pt-12">
      <div className="w-full max-w-5xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <Hash className="w-5 h-5 text-indigo-400" />
            <div>
              <h2 className="text-slate-100 font-bold text-lg">Evidence Chain Audit</h2>
              <p className="text-slate-500 text-xs font-mono">{callId}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {data && (
              <>
                <span className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${
                  data.chain_valid
                    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                    : 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                }`}>
                  {data.chain_valid
                    ? <><CheckCircle2 className="w-3.5 h-3.5" /> CHAIN INTACT</>
                    : <><XCircle className="w-3.5 h-3.5" /> CHAIN TAMPERED</>
                  }
                </span>
                <span className="text-slate-500 text-xs">{data.entry_count} entries</span>
              </>
            )}
            <button
              onClick={load}
              className="p-2 text-slate-400 hover:text-slate-200 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={exportJson}
              disabled={!data}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 hover:bg-indigo-500/20 disabled:opacity-40 transition-colors"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON
            </button>
            <button
              onClick={onClose}
              className="ml-2 text-slate-500 hover:text-slate-200 text-xs font-bold px-3 py-1.5 border border-slate-700 rounded-md transition-colors"
            >
              ✕ Close
            </button>
          </div>
        </div>

        {/* BSA note */}
        <div className="bg-indigo-950/40 border-b border-indigo-800/30 px-6 py-2.5 flex items-center gap-2">
          <Shield className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <p className="text-indigo-300/80 text-xs">
            SHA-256 hash chain — legally admissible under <strong>Bharatiya Sakshya Adhiniyam (BSA) 2023, §63</strong>.
            Each entry&apos;s hash includes the previous entry&apos;s hash — any tampering breaks every subsequent link.
            No raw audio is stored (DPDP Act 2023 compliance).
          </p>
        </div>

        {/* Body */}
        <div className="p-4 max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-16 text-slate-500 gap-3">
              <RefreshCw className="w-5 h-5 animate-spin" />
              <span>Loading evidence chain…</span>
            </div>
          )}
          {error && (
            <div className="text-rose-400 text-sm text-center py-8">{error}</div>
          )}
          {data && data.entries.length === 0 && (
            <div className="text-slate-500 text-center py-8">
              No evidence entries yet — start monitoring to generate the chain.
            </div>
          )}
          {data && data.entries.length > 0 && (
            <div className="space-y-2">
              {data.entries.map((entry, idx) => {
                const isExpanded = expandedRows.has(entry.entry_id);
                const p = entry.payload;
                return (
                  <div
                    key={entry.entry_id}
                    className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/50"
                  >
                    {/* Row header */}
                    <button
                      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-800/40 transition-colors"
                      onClick={() => toggleRow(entry.entry_id)}
                    >
                      <span className="text-slate-500 text-xs font-mono w-6 shrink-0">#{idx + 1}</span>
                      {verdictIcon(p.fused_risk_score)}
                      <span className={`font-mono text-xs font-bold ${riskClass(p.fused_risk_score)}`}>
                        {(p.fused_risk_score * 100).toFixed(1)}%
                      </span>
                      <span className="text-slate-400 text-xs flex-1">
                        {p.window_start_ms}ms – {p.window_end_ms}ms
                      </span>
                      <span className="text-slate-500 text-xs font-mono hidden lg:block">
                        {truncHash(entry.entry_hash)}
                      </span>
                      <span className="text-slate-600 text-xs ml-2">
                        {new Date(entry.created_at).toLocaleTimeString('en-IN')}
                      </span>
                      {p.is_flagged && (
                        <span className="text-rose-400 text-xs font-bold px-1.5 py-0.5 rounded bg-rose-500/10 border border-rose-500/20">
                          FLAGGED
                        </span>
                      )}
                      {isExpanded
                        ? <ChevronDown className="w-4 h-4 text-slate-600 shrink-0" />
                        : <ChevronRight className="w-4 h-4 text-slate-600 shrink-0" />
                      }
                    </button>

                    {/* Expanded payload */}
                    {isExpanded && (
                      <div className="border-t border-slate-800 px-4 py-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                        {/* Hash chain */}
                        <div className="space-y-2">
                          <p className="text-slate-500 uppercase tracking-wider font-semibold text-[10px]">Hash Chain</p>
                          <div className="bg-slate-900 rounded-lg p-3 space-y-2 border border-slate-800">
                            <div>
                              <span className="text-slate-500">prev_hash</span>
                              <p className="font-mono text-[10px] text-slate-400 break-all mt-0.5">{entry.prev_hash}</p>
                            </div>
                            <div>
                              <span className="text-slate-500">entry_hash</span>
                              <p className="font-mono text-[10px] text-indigo-300 break-all mt-0.5">{entry.entry_hash}</p>
                            </div>
                          </div>
                        </div>
                        {/* Payload */}
                        <div className="space-y-2">
                          <p className="text-slate-500 uppercase tracking-wider font-semibold text-[10px]">Signed Payload</p>
                          <div className="bg-slate-900 rounded-lg p-3 border border-slate-800">
                            <table className="w-full">
                              <tbody className="space-y-1">
                                {Object.entries(p).map(([k, v]) => (
                                  <tr key={k}>
                                    <td className="text-slate-500 pr-3 py-0.5 align-top w-40">{k}</td>
                                    <td className={`font-mono break-all ${
                                      k === 'is_flagged' && v ? 'text-rose-400' :
                                      k === 'fused_risk_score' ? riskClass(Number(v)) :
                                      'text-slate-300'
                                    }`}>
                                      {String(v)}
                                    </td>
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
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function EvidencePage() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

  const loadCalls = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/calls?limit=20`);
      if (res.ok) setCalls(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCalls(); }, [loadCalls]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col">
      {/* Nav */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Shield className="w-7 h-7 text-indigo-500" />
          <div>
            <h1 className="font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
              VoiceShield
            </h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest">Evidence Audit Trail</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1.5 transition-colors"
          >
            <Phone className="w-4 h-4" /> Live Dashboard
          </Link>
          <button
            onClick={loadCalls}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full p-6">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-slate-100">Call Evidence Records</h2>
          <p className="text-slate-500 text-sm mt-1">
            Click any row to inspect the full SHA-256 hash-chain and verify forensic integrity.
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20 text-slate-500 gap-3">
            <RefreshCw className="w-5 h-5 animate-spin" /> Loading calls…
          </div>
        )}

        {!loading && calls.length === 0 && (
          <div className="text-center py-20 text-slate-500">
            <Hash className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p>No calls recorded yet. Start monitoring from the <Link href="/" className="text-indigo-400 underline">Live Dashboard</Link>.</p>
          </div>
        )}

        {calls.length > 0 && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/80 text-slate-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Call ID</th>
                  <th className="px-4 py-3 text-left">Started</th>
                  <th className="px-4 py-3 text-left">Duration</th>
                  <th className="px-4 py-3 text-left">Source</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {calls.map((call) => {
                  const duration = call.ended_at
                    ? `${Math.round((new Date(call.ended_at).getTime() - new Date(call.started_at).getTime()) / 1000)}s`
                    : '—';
                  return (
                    <tr
                      key={call.call_id}
                      className="hover:bg-slate-800/30 transition-colors cursor-pointer"
                      onClick={() => setSelectedCallId(call.call_id)}
                    >
                      <td className="px-4 py-3 font-mono text-indigo-400 text-xs">
                        {call.call_id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 shrink-0" />
                          {fmt(call.started_at)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs font-mono">{duration}</td>
                      <td className="px-4 py-3 text-slate-400 text-xs font-mono">{call.source}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${statusColor[call.status] ?? 'text-slate-400'}`}>
                          {call.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelectedCallId(call.call_id); }}
                          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/20 bg-indigo-500/5 hover:bg-indigo-500/10 px-2.5 py-1 rounded-md transition-colors"
                        >
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

      {/* Evidence Modal */}
      {selectedCallId && (
        <EvidencePanel
          callId={selectedCallId}
          onClose={() => setSelectedCallId(null)}
        />
      )}
    </div>
  );
}
