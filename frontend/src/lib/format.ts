/** All API times are UTC ISO strings; the UI always shows IST with an explicit label. */
const istFmt = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
});
const istHour = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", hour12: false });

export const toIST = (iso: string) => `${istFmt.format(new Date(iso))} IST`;
export const hourIST = (iso: string) => istHour.format(new Date(iso));
export const mw = (v: number, d = 1) => `${v.toFixed(d)} MW`;
export const mwh = (v: number, d = 0) => `${v.toLocaleString("en-IN", { maximumFractionDigits: d })} MWh`;
export const inr = (v: number) => `₹${Math.round(v).toLocaleString("en-IN")}`;
export const pct = (v: number, d = 1) => `${v.toFixed(d)}%`;

/** Read a CSS variable (series colours) so charts follow the theme. */
export function cssVar(name: string, fallback = "#888"): string {
  if (typeof window === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}
