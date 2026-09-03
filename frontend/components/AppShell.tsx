'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Radar, FlaskConical, History, ShieldCheck, Terminal, ShieldHalf } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const NAV = [
  { href: '/', label: 'Live Protection', icon: Radar, badge: 'LIVE' },
  { href: '/replay', label: 'Replay Lab', icon: FlaskConical },
  { href: '/history', label: 'Call History', icon: History },
  { href: '/evidence', label: 'Evidence', icon: ShieldCheck },
];

/** Polls /health so every page shows real backend connectivity (no fake uptime). */
function useBackendStatus() {
  const [status, setStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [model, setModel] = useState<string>('—');
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
        if (!alive) return;
        if (r.ok) {
          const j = await r.json().catch(() => ({}));
          setStatus('online');
          setModel(j.model_version ?? j.classifier ?? 'ready');
        } else setStatus('offline');
      } catch {
        if (alive) setStatus('offline');
      }
    };
    ping();
    const t = setInterval(ping, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return { status, model };
}

function useUtcClock() {
  const [now, setNow] = useState<string>('--:--:--');
  useEffect(() => {
    const tick = () => setNow(new Date().toISOString().slice(11, 19));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { status, model } = useBackendStatus();
  const utc = useUtcClock();

  const posture =
    status === 'online' ? { label: 'System Nominal — Backend Connected', dot: 'bg-risk-low' }
    : status === 'offline' ? { label: 'Backend Offline — Detector Unreachable', dot: 'bg-risk-high' }
    : { label: 'Connecting…', dot: 'bg-muted' };

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-surface border-r border-line z-50 flex flex-col justify-between select-none">
        <div className="flex flex-col">
          <div className="p-4 border-b border-line flex items-center gap-3">
            <span className="w-9 h-9 rounded bg-navy text-surface flex items-center justify-center shrink-0">
              <ShieldHalf className="w-5 h-5" />
            </span>
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-semibold text-navy tracking-tight leading-none uppercase">VoiceShield</span>
              <span className="eyebrow mt-1 truncate">Real-Time Authenticity</span>
            </div>
          </div>

          <div className="px-4 pt-3 pb-1"><span className="eyebrow">Operational Modes</span></div>
          <nav className="flex flex-col px-2 gap-0.5">
            {NAV.map((n) => {
              const active = pathname === n.href;
              const Icon = n.icon;
              return (
                <Link key={n.href} href={n.href}
                  className={`flex items-center justify-between px-3 py-2 rounded transition-colors ${
                    active ? 'bg-surface-high text-navy border-l-2 border-brand font-semibold'
                           : 'text-muted hover:bg-surface-low hover:text-navy border-l-2 border-transparent'
                  }`}>
                  <span className="flex items-center gap-2.5">
                    <Icon className="w-[18px] h-[18px]" />
                    <span className="text-body-sm">{n.label}</span>
                  </span>
                  {n.badge && (
                    <span className="mono text-data-sm px-1.5 py-0.5 rounded-sm bg-surface-high text-navy tracking-wider">{n.badge}</span>
                  )}
                </Link>
              );
            })}
          </nav>

          <div className="px-4 pt-6 pb-1"><span className="eyebrow">System Telemetry</span></div>
          <div className="mx-4 p-2.5 bg-surface-low border border-line rounded flex flex-col gap-1.5 mono text-data-sm">
            <Telem k="Backend" v={status === 'online' ? 'Connected' : status === 'offline' ? 'Offline' : '…'}
                   vClass={status === 'online' ? 'text-risk-low' : status === 'offline' ? 'text-risk-high' : 'text-muted'} />
            <Telem k="Detector" v={status === 'online' ? String(model) : '—'} vClass="text-brand" />
            <Telem k="VAD Engine" v="8 kHz · Silero" />
            <Telem k="Pipeline" v="2s · 500ms hop" />
          </div>
        </div>

        <div className="p-4 border-t border-line">
          <div className="p-2.5 bg-surface-low border border-line rounded text-center">
            <span className="block eyebrow text-navy">Team Red Flags</span>
            <span className="block mono text-data-sm text-muted mt-0.5 uppercase">Smart India Hackathon 2026</span>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="pl-64">
        <header className="fixed top-0 left-64 right-0 h-14 bg-surface border-b border-line z-40 flex items-center justify-between px-6 select-none">
          <div className="flex items-center gap-4 min-w-0">
            <div className="flex items-center gap-2 mono text-data text-muted">
              <Terminal className="w-4 h-4 text-navy" />
              <span className="text-navy font-semibold">FRAUD OPERATIONS</span>
              <span className="text-line">//</span>
              <span className="hidden sm:inline">WORKSTATION</span>
            </div>
            <div className="h-4 w-px bg-line hidden sm:block" />
            <span className="hidden md:inline-flex items-center gap-2 px-2 py-0.5 rounded border border-line bg-surface-low">
              <span className={`w-2 h-2 rounded-full ${posture.dot} ${status === 'online' ? 'animate-pulse' : ''}`} />
              <span className="eyebrow">{posture.label}</span>
            </span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 mono text-data text-navy border-r border-line pr-4">
              <span className="eyebrow">UTC</span>
              <span>{utc}</span>
            </div>
            <ThemeToggle />
          </div>
        </header>

        <main className="pt-14 min-h-screen">{children}</main>
      </div>
    </div>
  );
}

function Telem({ k, v, vClass = 'text-navy' }: { k: string; v: string; vClass?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted uppercase">{k}</span>
      <span className={`font-semibold ${vClass}`}>{v}</span>
    </div>
  );
}
