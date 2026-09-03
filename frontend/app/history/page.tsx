'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { History, RefreshCw, Search, ChevronRight, ShieldCheck, ShieldAlert, Clock } from 'lucide-react';
import { AppShell } from '../../components/AppShell';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface CallRecord {
  call_id: string; started_at: string; ended_at: string | null; source: string;
  status: 'active' | 'ended' | 'held';
}

const statusPill: Record<string, string> = {
  active: 'bg-brand-soft text-brand',
  ended: 'bg-surface-high text-muted',
  held: 'bg-high-soft text-risk-high border border-high-line',
};
const railColor: Record<string, string> = { active: 'bg-brand', ended: 'bg-line', held: 'bg-risk-high' };

const fmt = (iso: string) => new Date(iso).toLocaleString('en-IN', { hour12: false });
const dur = (c: CallRecord) => {
  if (!c.ended_at || !c.started_at) return '—';
  const diff = Math.round((+new Date(c.ended_at) - +new Date(c.started_at)) / 1000);
  return isNaN(diff) || diff < 0 ? '—' : `${diff}s`;
};

type Filter = 'ALL' | 'HELD' | 'ACTIVE' | 'ENDED';

export default function CallHistory() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('ALL');
  const [q, setQ] = useState('');
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      let res: Response;
      try { res = await fetch(`${API_BASE}/api/calls?limit=100`, { cache: 'no-store' }); }
      catch { throw new Error('Cannot reach the backend on port 8000 — is it running?'); }
      if (!res.ok) throw new Error(`Backend error (HTTP ${res.status}).`);
      setCalls(await res.json());
    } catch (e) { setErr(e instanceof Error ? e.message : 'Failed to load calls.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const kpi = useMemo(() => ({
    total: calls.length,
    held: calls.filter((c) => c.status === 'held').length,
    active: calls.filter((c) => c.status === 'active').length,
    ended: calls.filter((c) => c.status === 'ended').length,
  }), [calls]);

  const rows = useMemo(() => calls.filter((c) => {
    if (filter === 'HELD' && c.status !== 'held') return false;
    if (filter === 'ACTIVE' && c.status !== 'active') return false;
    if (filter === 'ENDED' && c.status !== 'ended') return false;
    if (q && !c.call_id.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [calls, filter, q]);

  const sel = calls.find((c) => c.call_id === selected) ?? null;

  return (
    <AppShell>
      <div className="bg-surface border-b border-line px-6 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <span className="text-body-sm font-semibold text-navy uppercase tracking-tight flex items-center gap-1.5">
          <History className="w-4 h-4 text-brand" /> Call History
        </span>
        <button onClick={load} className="inline-flex items-center gap-1.5 text-body-sm text-muted hover:text-navy">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="px-6 py-3 space-y-3">
        {/* KPIs from REAL data */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi label="Total Calls" value={kpi.total} />
          <Kpi label="Interventions (Held)" value={kpi.held} tone="high" />
          <Kpi label="Active" value={kpi.active} tone="brand" />
          <Kpi label="Ended" value={kpi.ended} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          {/* Table */}
          <div className="xl:col-span-2 panel overflow-hidden">
            <div className="panel-head px-3 py-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1">
                {(['ALL', 'HELD', 'ACTIVE', 'ENDED'] as Filter[]).map((f) => (
                  <button key={f} onClick={() => setFilter(f)}
                    className={`px-2.5 h-7 rounded text-data font-semibold ${filter === f ? 'bg-navy text-surface' : 'text-muted hover:bg-surface-high'}`}>
                    {f}{f === 'ALL' ? ` (${kpi.total})` : f === 'HELD' ? ` (${kpi.held})` : ''}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1.5 px-2 h-7 rounded border border-line bg-surface">
                <Search className="w-3.5 h-3.5 text-muted" />
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by call ID…"
                  className="bg-transparent outline-none mono text-data-sm text-ink w-40 placeholder:text-muted" />
              </div>
            </div>

            {err && <div className="p-4 text-body-sm text-risk-high">{err}</div>}
            {loading && <div className="p-8 flex items-center justify-center gap-2 text-muted"><RefreshCw className="w-5 h-5 animate-spin" /> Loading…</div>}
            {!loading && !err && rows.length === 0 && (
              <div className="p-10 text-center text-muted text-body-sm">
                No call records. Start one from <Link href="/" className="text-brand underline">Live Protection</Link> or <Link href="/replay" className="text-brand underline">Replay Lab</Link>.
              </div>
            )}
            {rows.length > 0 && (
              <table className="w-full text-body-sm">
                <thead className="text-muted"><tr className="text-left">
                  <th className="px-4 py-2 eyebrow font-medium">Time</th>
                  <th className="px-4 py-2 eyebrow font-medium">Call Identifier</th>
                  <th className="px-4 py-2 eyebrow font-medium">Source</th>
                  <th className="px-4 py-2 eyebrow font-medium">Duration</th>
                  <th className="px-4 py-2 eyebrow font-medium">Disposition</th>
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {rows.map((c) => (
                    <tr key={c.call_id} onClick={() => setSelected(c.call_id)}
                      className={`cursor-pointer ${selected === c.call_id ? 'bg-brand-soft/40' : 'hover:bg-surface-low'}`}>
                      <td className="px-0 py-0">
                        <div className="flex">
                          <span className={`w-1 self-stretch ${railColor[c.status]}`} />
                          <span className="px-4 py-2.5 mono text-data text-muted">{fmt(c.started_at)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 mono text-data text-brand">{c.call_id.slice(0, 8).toUpperCase()}</td>
                      <td className="px-4 py-2.5 mono text-data-sm text-muted uppercase">{c.source}</td>
                      <td className="px-4 py-2.5 mono text-data text-muted">{dur(c)}</td>
                      <td className="px-4 py-2.5"><span className={`mono text-data-sm px-1.5 py-0.5 rounded-sm ${statusPill[c.status]}`}>{c.status.toUpperCase()}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Inspector dock */}
          <div className="panel p-4 h-fit">
            <span className="eyebrow text-navy">Forensic Inspection Dock</span>
            {!sel ? (
              <p className="text-body-sm text-muted mt-2">Select a call to inspect its record and evidence chain.</p>
            ) : (
              <div className="mt-3 space-y-3">
                <div className="flex items-center gap-2">
                  {sel.status === 'held' ? <ShieldAlert className="w-4 h-4 text-risk-high" /> : <ShieldCheck className="w-4 h-4 text-risk-low" />}
                  <span className="mono text-data text-navy">{sel.call_id.slice(0, 12).toUpperCase()}</span>
                </div>
                <dl className="space-y-2 mono text-data">
                  <Row k="Started" v={fmt(sel.started_at)} />
                  <Row k="Ended" v={sel.ended_at ? fmt(sel.ended_at) : '—'} />
                  <Row k="Source" v={sel.source.toUpperCase()} />
                  <Row k="Duration" v={dur(sel)} />
                  <Row k="Disposition" v={sel.status.toUpperCase()} vClass={sel.status === 'held' ? 'text-risk-high' : 'text-navy'} />
                </dl>
                {sel.status === 'held' && (
                  <div className="flex items-center gap-2 p-2 rounded bg-high-soft border border-high-line">
                    <ShieldAlert className="w-3.5 h-3.5 text-risk-high" />
                    <span className="text-body-sm text-risk-high">Transaction hold enforced on this call.</span>
                  </div>
                )}
                <Link href={`/evidence?call_id=${sel.call_id}`} className="inline-flex items-center gap-1 text-body-sm text-brand hover:text-brand-dark">
                  <Clock className="w-3.5 h-3.5" /> Open Evidence Chain <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function Kpi({ label, value, tone }: { label: string; value: number; tone?: 'high' | 'brand' }) {
  const tc = tone === 'high' ? 'text-risk-high' : tone === 'brand' ? 'text-brand' : 'text-navy';
  return (
    <div className="panel p-4">
      <p className="eyebrow">{label}</p>
      <p className={`mono text-metric mt-1 ${tc}`}>{value}</p>
    </div>
  );
}
function Row({ k, v, vClass = 'text-navy' }: { k: string; v: string; vClass?: string }) {
  return <div className="flex items-center justify-between"><dt className="text-muted uppercase">{k}</dt><dd className={`font-semibold ${vClass}`}>{v}</dd></div>;
}
