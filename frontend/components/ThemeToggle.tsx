'use client';
import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';

/** Toggles the `dark` class on <html> and persists the choice. Defaults to the
 *  OS preference (applied pre-paint by the inline script in layout.tsx). */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains('dark'));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    try { localStorage.setItem('vs-theme', next ? 'dark' : 'light'); } catch { /* ignore */ }
  };

  return (
    <button onClick={toggle} title="Toggle light / dark"
      className="p-2 text-muted hover:text-navy transition-colors" aria-label="Toggle theme">
      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
}
