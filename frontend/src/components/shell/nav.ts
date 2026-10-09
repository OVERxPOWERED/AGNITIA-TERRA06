import {
  LayoutDashboard,
  LineChart,
  Cpu,
  ShieldCheck,
  Bell,
  BatteryCharging,
  Sliders,
  ShieldAlert,
  Sparkles,
  BookOpen,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { href: "/", label: "Control Room", icon: LayoutDashboard },
      { href: "/forecast", label: "Forecast", icon: LineChart },
    ],
  },
  {
    title: "Performance",
    items: [
      { href: "/models", label: "Models & Accuracy", icon: Cpu },
      { href: "/trust", label: "Trust", icon: ShieldCheck },
    ],
  },
  {
    title: "Operations",
    items: [
      { href: "/alerts", label: "Alerts", icon: Bell },
      { href: "/dispatch", label: "Dispatch", icon: BatteryCharging },
      { href: "/whatif", label: "What-if", icon: Sliders },
    ],
  },
  {
    title: "Business",
    items: [
      { href: "/deviation", label: "Deviation Shield", icon: ShieldAlert },
      { href: "/impact", label: "Impact", icon: Sparkles },
    ],
  },
  {
    title: "Reference",
    items: [
      { href: "/assumptions", label: "Assumptions", icon: BookOpen },
    ],
  },
];

// Flat list for simple lookup
export const NAV = NAV_GROUPS.flatMap((g) => g.items);
