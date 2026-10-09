import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Forecast explorer",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
