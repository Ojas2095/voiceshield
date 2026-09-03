import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VoiceShield | Voice Authenticity Console",
  description: "Real-time detection & prevention of AI voice-cloning fraud.",
};

// Apply the saved / system theme before first paint to avoid a flash.
const themeInit = `(function(){try{var t=localStorage.getItem('vs-theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;if(d)document.documentElement.classList.add('dark');}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head><script dangerouslySetInnerHTML={{ __html: themeInit }} /></head>
      <body className="antialiased min-h-screen bg-canvas text-ink">{children}</body>
    </html>
  );
}
