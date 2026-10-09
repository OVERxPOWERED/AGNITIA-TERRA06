import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plant settings",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
