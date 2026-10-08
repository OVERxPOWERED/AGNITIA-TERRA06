---
description: Add a new dashboard page in the Next.js app following the shared layout and data patterns.
---

# Add a frontend page

1. Create `frontend/src/app/<route>/page.tsx`; add it to the sidebar nav config.
2. Data: use or create a hook in `src/hooks/` built on generated API types. Never call `fetch` directly in a component.
3. Layout: page header (title, IST time window, LIVE/REPLAY badge) → KPI strip → main chart → secondary panels.
4. Charts: reuse primitives in `src/components/charts/`; units on axes; IST time labels; band at ~20% opacity.
5. States: skeleton, error with retry, empty.
6. Footer attribution component.
7. Check: `npm run lint && npm run build`; open the page in both themes and at mobile width.
