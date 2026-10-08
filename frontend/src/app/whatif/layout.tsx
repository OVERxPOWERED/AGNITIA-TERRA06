import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "What-if Simulator",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
