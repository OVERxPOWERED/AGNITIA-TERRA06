/** Vidyut mark: a V whose right stroke is a bolt. Reads at 16px; colours follow the theme tokens. */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <path d="M8 8.5 L15.2 24" stroke="var(--on-accent)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M24.5 8 L17.2 15.2 H21.4 L15.2 24" stroke="var(--on-accent)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark />
      <span className="text-[17px] font-semibold tracking-[-0.02em] text-ink">Vidyut</span>
    </span>
  );
}
