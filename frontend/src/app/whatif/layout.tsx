import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "What-if simulator",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
