---
trigger: glob
globs: frontend/**
description: Next.js frontend conventions (App Router, data fetching, charts, design).
---

# Frontend rules

- Next.js App Router + TypeScript strict. Server components for layout/static; client components for charts and interactive state.
- API types are generated (`src/lib/api/schema.d.ts` via `make types`) — never hand-write response types.
- Data fetching through TanStack Query hooks in `src/hooks/` (`useForecast`, `useAlerts`, …). No fetch calls inside chart components.
- Charts: ECharts via a shared wrapper in `src/components/charts/`. Reuse primitives: `LineWithBand`, `StackedArea`, `Bars`, `Heatmap`, `TrustRibbon`.
- Colour tokens (CSS variables in `globals.css`): solar = amber, wind = teal, demand = slate, battery = violet, backup/fossil = grey-brown, uncertainty band = series colour at ~20% opacity. Trust and severity always use icon/label + colour (never colour alone).
- Show times in IST with explicit "IST" label; show units on every axis and KPI.
- Every page: loading skeleton, error state with retry, empty state, and the attribution footer ("Weather data by Open-Meteo.com (CC BY 4.0) · Plant: TERRA virtual twin").
- Mode badge LIVE / REPLAY always visible in the header.
- Accessibility: chart `aria-label` summaries, keyboard-reachable controls, contrast AA.
- Components: shadcn/ui in `src/components/ui/`; feature components in `src/components/<feature>/`.
- `npm run lint && npm run build` must pass before commit.
