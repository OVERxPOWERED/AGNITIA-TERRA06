# Vidyut — Design System Specification

## 1. Aesthetic Direction & POV
Vidyut is an operational control room for hybrid solar + wind renewable energy dispatch and forecasting. 
The visual language is refined, modern, restrained, and premium. It avoids generic SaaS dashboard tropes (no neon gradients, no glassmorphism, no chunky cards with thick drop shadows). It uses calm neutral surfaces with high-density data clarity, generous negative space around high-level KPIs and charts, and crisp tabular typography.

Two carefully balanced themes:
- **Light Theme**: Warm off-white canvas (`#F8F8F6`), pure white panels (`#FFFFFF`), hairline borders (`#E2E2DC`), crisp charcoal text (`#18181B`).
- **Dark Theme**: Soft slate-blue/charcoal surfaces (`#14181F` canvas, `#1C2230` panels, `#242B3D` elevated), avoiding harsh near-black, with slate borders (`#2A344A`) and luminous off-white text (`#F1F5F9`).

---

## 2. Color Tokens & Contrast Audit (WCAG AA Compliance)

### 2.1 Tokens Definition
```css
/* Light Theme */
--bg: #F8F8F6;          /* Warm off-white page background */
--panel: #FFFFFF;       /* Crisp white surface for cards and panels */
--panel-muted: #F1F1ED; /* Subtle inset background */
--border: #E2E2DC;      /* Soft hairline border */
--text: #18181B;        /* Primary high-contrast text */
--muted: #64645E;       /* Secondary text and metadata */
--accent: #4338CA;      /* Signal color: Deep Electric Indigo (matches Hybrid) */
--accent-subtle: #EEF2FF; /* Tinted accent surface */
--solar: #B45309;       /* Solar series: Amber */
--wind: #0F766E;        /* Wind series: Deep Teal */
--hybrid: #4338CA;      /* Hybrid forecast: Signal color */
--demand: #475569;      /* Grid Demand: Slate */
--battery: #6D28D9;     /* Battery storage: Violet */
--backup: #78716C;      /* Backup diesel/grid: Warm Stone */
--good: #15803D;        /* Positive/Live: Forest Emerald */
--warn: #B45309;        /* Warning: Amber */
--bad: #B91C1C;         /* Critical error/deviation: Crimson */

/* Dark Theme (soft slate-blue/charcoal range) */
--bg: #14181F;          /* Slate-charcoal canvas */
--panel: #1C2230;       /* Soft slate-blue panel */
--panel-muted: #242B3D; /* Elevated inset panel */
--border: #2A344A;      /* Slate border */
--text: #F1F5F9;        /* High-contrast crisp text */
--muted: #94A0B8;       /* Slate muted text */
--accent: #818CF8;      /* Signal color: Luminous Indigo */
--accent-subtle: #252D47; /* Tinted accent surface */
--solar: #F59E0B;       /* Solar series: Amber */
--wind: #2DD4BF;        /* Wind series: Teal */
--hybrid: #818CF8;      /* Hybrid forecast: Signal color */
--demand: #94A0B8;      /* Grid Demand: Slate */
--battery: #A78BFA;     /* Battery storage: Soft Violet */
--backup: #A8A29E;      /* Backup diesel/grid: Stone */
--good: #34D399;        /* Positive/Live: Emerald */
--warn: #FBBF24;        /* Warning: Amber */
--bad: #F87171;         /* Critical error/deviation: Coral Red */
```

### 2.2 Contrast Verification (WCAG AA Requirement: >= 4.5:1 text, >= 3:1 UI components)
All values verified via relative luminance calculation against card panel surface:

| Token | Light Hex | Light Ratio (vs #FFF) | Light AA | Dark Hex | Dark Ratio (vs #1C2230) | Dark AA |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **text** | `#18181B` | **17.72 : 1** | PASS (AAA) | `#F1F5F9` | **14.51 : 1** | PASS (AAA) |
| **muted** | `#64645E` | **5.96 : 1** | PASS (AA) | `#94A0B8` | **6.20 : 1** | PASS (AA) |
| **accent (signal)** | `#4338CA` | **7.90 : 1** | PASS (AAA) | `#818CF8` | **5.33 : 1** | PASS (AA) |
| **solar** | `#B45309` | **5.02 : 1** | PASS (AA) | `#F59E0B` | **7.40 : 1** | PASS (AAA) |
| **wind** | `#0F766E` | **5.47 : 1** | PASS (AA) | `#2DD4BF` | **8.54 : 1** | PASS (AAA) |
| **demand** | `#475569` | **7.58 : 1** | PASS (AAA) | `#94A0B8` | **6.20 : 1** | PASS (AA) |
| **battery** | `#6D28D9` | **7.10 : 1** | PASS (AAA) | `#A78BFA` | **5.84 : 1** | PASS (AA) |
| **good** | `#15803D` | **5.02 : 1** | PASS (AA) | `#34D399` | **8.27 : 1** | PASS (AAA) |
| **warn** | `#B45309` | **5.02 : 1** | PASS (AA) | `#FBBF24` | **9.52 : 1** | PASS (AAA) |
| **bad** | `#B91C1C` | **6.47 : 1** | PASS (AA) | `#F87171` | **5.75 : 1** | PASS (AA) |

---

## 3. Typography Scale & Guidelines

Using `Geist Sans` (`geist/font/sans`) with explicit tabular figures (`tabular-nums`) for all numeric displays.

- **Display / H1**: 24px (`text-2xl`), font-weight 600, line-height 1.25, tracking -0.02em.
- **Section / Card Header**: 15px (`text-sm`), font-weight 600, tracking -0.01em.
- **Card Eyebrow / Label**: 11px (`text-[11px]`), font-weight 600, uppercase, tracking 0.05em, text-muted.
- **KPI Value**: 24px (`text-2xl`), font-weight 600, tabular-nums, tracking -0.02em.
- **Body Regular**: 14px (`text-sm`), font-weight 400, line-height 1.5.
- **Caption / Metadata**: 12px (`text-xs`), font-weight 400, line-height 1.4.
- **Micro / Subtitle**: 11px (`text-[11px]`), font-weight 500.

Rules:
1. Always apply `font-variant-numeric: tabular-nums` (`tabular-nums`) to KPI values, timestamps, table cells, and numeric metrics.
2. Maintain active readability; no gray-on-gray low-contrast text.

---

## 4. Spacing, Radii & Depth Scale

- **Spacing Scale**: 4px, 8px, 12px, 16px, 20px, 24px, 32px.
- **Radii**:
  - `rounded-md` (6px): Segmented buttons, small badges, action chips.
  - `rounded-lg` (8px): Inputs, sliders, tooltips, standard buttons.
  - `rounded-xl` (12px): Cards, modals, drawers, panels.
  - `rounded-full` (9999px): Status dot indicators, pill badges.
- **Shadows**:
  - Light: `0 1px 2px 0 rgba(0, 0, 0, 0.04), 0 1px 3px 0 rgba(0, 0, 0, 0.02)`.
  - Dark: `0 1px 2px 0 rgba(0, 0, 0, 0.35), 0 4px 12px 0 rgba(0, 0, 0, 0.25)`.
- **Borders**: 1px thin soft border (`var(--border)`). No heavy outlines.

---

## 5. Motion Rules (Emil Kowalski Philosophy)

Motion is restrained, instantaneous, and purposeful:
- **Hover / Focus Transitions**: `transition-colors duration-150 ease-out` (<= 150ms).
- **Press / Active Feedback**: `transform: scale(0.98)` for 100ms.
- **Theme Switch**: Smooth `150ms ease` color crossfade.
- **Chart Animation**: Smooth entry on initial render only; no loop animations.
- **Prohibited**: NO KPI count-up animations, NO page entrance slides, NO scroll-jacked transitions, NO parallax.
- **Accessibility**: Under `@media (prefers-reduced-motion: reduce)`, all transitions and animations are strictly disabled (`transition: none !important; animation: none !important;`).

---

## 6. ECharts Theme Architecture

- **Theme Sync**: ECharts reacts dynamically to theme toggle. Chart instance is rebuilt or updated with active palette without page reload.
- **Grid & Axes**:
  - Split lines / Grids: Subtle 1px dashed or solid border (`#E2E2DC` light, `#2A344A` dark).
  - Axis text: Readable muted tone (`#64645E` light, `#94A0B8` dark), tabular numbers.
- **Tooltips**:
  - Styled with theme-aware panel background, hairline border, soft shadow, clean typography.
  - Retains standard `P50 (P10 – P90)` structure with bold values.
- **Uncertainty Bands**: Stacked area opacity 0.18–0.22, subtle and non-distracting.
- **Legends**: Horizontal scrollable layout with wrap handling on mobile viewports.

---

## 7. Sidebar & Shell Behaviour

- **Collapsible Desktop Mode (>= 768px)**:
  - Expanded: 240px (`w-60`), displaying icon + label + group category headers.
  - Collapsed: 68px (`w-[68px]`), displaying centered icons with tooltip labels.
  - Persistence: Stored in `localStorage` key `vidyut_sidebar_collapsed` inside `try/catch`.
  - Groupings:
    1. **Overview**: Control Room (`/`), Forecast (`/forecast`)
    2. **Performance**: Models & Accuracy (`/models`), Trust (`/trust`)
    3. **Operations**: Alerts (`/alerts`), Dispatch (`/dispatch`), What-if (`/whatif`)
    4. **Business**: Deviation Shield (`/deviation`), Impact (`/impact`)
    5. **Reference**: Assumptions (`/assumptions`)
- **Mobile Drawer Mode (< 768px)**:
  - Clean top navigation bar with brand logo, mode badge, and accessible hamburger toggle.
  - Off-canvas drawer sliding from the left with backdrop overlay.
  - Escape key support, outside click dismiss, and automatic close on route navigation.
  - Touch target size: Minimum 40px × 40px for all interactive targets.
- **Footer & Status**:
  - Live/Replay mode badge.
  - Real-time API connection status (online / waking up / unreachable).
  - Three-state theme selector: Light / Dark / System.
