import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import AppShell from "@/components/shell/AppShell";
import Providers from "./providers";

export const metadata: Metadata = {
  title: { template: "%s — Vidyut", default: "Control Room — Vidyut" },
  description: "Day-ahead solar and wind forecasts with calibrated uncertainty, alerts, battery dispatch and deviation estimates.",
  icons: { icon: "/icon.svg", apple: "/apple-icon" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#edf0e8" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1512" },
  ],
};

/* Runs before first paint so the page never flashes the wrong theme.
   `?theme=dark|light` overrides once (handy for screenshots) and is remembered. */
const themeScript = `(function(){try{
var q=new URLSearchParams(location.search).get('theme');
if(q==='dark'||q==='light'||q==='system'){localStorage.setItem('vidyut_theme',q);}
var m=localStorage.getItem('vidyut_theme')||'system';
var d=m==='dark'||(m==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);
var e=document.documentElement;e.classList.toggle('dark',d);e.dataset.theme=d?'dark':'light';
}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen font-sans">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
