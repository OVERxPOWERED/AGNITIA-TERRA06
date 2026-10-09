export interface NavItem { href: string; label: string; slug: string }

/** Order matches the tab bar. `slug` is the readable page name in the breadcrumb. */
export const NAV: NavItem[] = [
  { href: "/", label: "Control Room", slug: "control-room" },
  { href: "/forecast", label: "Forecast", slug: "forecast" },
  { href: "/models", label: "Models & Accuracy", slug: "models" },
  { href: "/trust", label: "Trust", slug: "trust" },
  { href: "/alerts", label: "Alerts", slug: "alerts" },
  { href: "/dispatch", label: "Dispatch", slug: "dispatch" },
  { href: "/whatif", label: "What-if", slug: "what-if" },
  { href: "/deviation", label: "Deviation Shield", slug: "deviation-shield" },
  { href: "/impact", label: "Impact", slug: "impact" },
  { href: "/assumptions", label: "Assumptions", slug: "assumptions" },
];
