# Vidyut interface design

A day-ahead desk for a hybrid solar, wind and battery plant. The page answers "what does the next 48 hours look like?" in a sentence first, then shows the evidence.

## Principles
- **Say it, then show it.** Each page opens with plain language; figures and charts back it up.
- **One memorable element.** The forecast chart: demand gap shaded, solar peak labelled, and the hourly confidence strip lined up under the same time axis.
- **Quiet everywhere else.** One radius family (10 px panels, 8 px controls), hairline borders, no gradients, no card-per-fact repetition. Dividers and whitespace set the rhythm.
- **Honest data.** Every number comes from the API. Missing data shows "—". Nothing is invented; derived text is computed in `src/lib/analysis.ts`.

## Colour (tokens in `globals.css`, literal copies for canvas charts in `lib/theme.tsx`)
| Role | Light | Dark |
|---|---|---|
| Page (`paper`) | `#edf0e8` | `#0f1512` |
| Panel (`surface`) | `#fafbf7` | `#161e1a` |
| Text (`ink`) / secondary (`muted`) | `#17251e` / `#586a60` | `#e7efe9` / `#93a39a` |
| Hairline (`line`) | `#d5dcce` | `#25312b` |
| Accent and hybrid | `#1e5a43` | `#5fc49a` |
| Solar | `#b0700f` | `#f0b13c` |
| Wind | `#1f8a7d` | `#4ccfc0` |
| Demand | `#5a6b8a` | `#9cabc8` |
| Battery | `#6d5fb8` | `#a99bf0` |
| Alert (`bad`) / caution (`warn`) / ok (`good`) | `#b5472e` / `#a2690a` / `#2b7a4f` | `#ee8d74` / `#e9b24a` / `#5fc49a` |

Series colours have fixed meanings on every page. Red is only for real problems; "low confidence" uses a soft tint.

## Type
Geist Sans for headings, labels and text (sentence case). Geist Mono only for numerals, times and identifiers, always tabular. Page title 26 px, briefing headline 30 px, panel title 15 px, body 14 px, labels 12 to 13 px. Lines of prose stay under 70 characters.

## Layout
Top bar (brand, route, plant capacity, IST clock, mode, appearance), a 48-hour outline strip, the tab bar with the open-alert count, then the page. Content width 1360 px. Panels hold one idea; key figures sit in a divided strip, not in boxes.

## Motion
Only feedback and loading: 120 ms colour transitions, a slow breathing skeleton, charts drawing in once. No count-ups, no page transitions. Everything is off under `prefers-reduced-motion`.

## Accessibility
Text and controls meet WCAG AA in both themes. Visible focus rings. Segmented controls are radio groups with arrow-key support; the day plan is a disclosure list with `aria-expanded`; the appearance menu closes on Escape. Charts carry text alternatives and the confidence strip has a written summary.

## Time
The API speaks UTC. Charts shift timestamps by +5 h 30 min and run with `useUTC`, so ticks fall on real IST hours in any browser.
