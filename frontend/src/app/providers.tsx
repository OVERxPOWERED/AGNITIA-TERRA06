"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { retryDelay, shouldRetry } from "@/hooks/api";
import { AuthProvider } from "@/lib/auth";
import { ActivePlantProvider } from "@/lib/plant";
import { ThemeProvider } from "@/lib/theme";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: shouldRetry,
            retryDelay,
          },
        },
      }),
  );
  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <ActivePlantProvider>{children}</ActivePlantProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
