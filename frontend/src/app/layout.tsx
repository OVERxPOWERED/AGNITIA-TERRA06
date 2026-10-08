import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/shell/AppShell";
import Providers from "./providers";

export const metadata: Metadata = {
  title: {
    template: "%s — TERRA",
    default: "Control Room — TERRA",
  },
  description: "Solar + wind forecasts with calibrated uncertainty, alerts, dispatch and deviation estimates.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
