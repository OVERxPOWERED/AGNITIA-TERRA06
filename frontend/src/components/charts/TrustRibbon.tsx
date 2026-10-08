import { toIST } from "@/lib/format";

/** Per-hour trust strip; colour + text label so it never relies on colour alone. */
export default function TrustRibbon({ points }: { points: { target_time_utc: string; trust_score: number; trust_reason: string }[] }) {
  const color = (s: number) => (s >= 70 ? "var(--good)" : s >= 40 ? "var(--warn)" : "var(--bad)");
  const low = points.filter((p) => p.trust_score < 40).length;
  return (
    <div>
      <div className="flex h-4 w-full overflow-hidden rounded" aria-label={`Trust per hour: ${low} low-confidence hours`}>
        {points.map((p) => (
          <div key={p.target_time_utc} className="flex-1" style={{ background: color(p.trust_score) }}
            title={`${toIST(p.target_time_utc)} · trust ${p.trust_score} · ${p.trust_reason}`} />
        ))}
      </div>
      <div className="mt-1 flex gap-4 text-xs text-muted">
        <span>■ <span style={{ color: "var(--good)" }}>high ≥70</span></span>
        <span>■ <span style={{ color: "var(--warn)" }}>medium 40–69</span></span>
        <span>■ <span style={{ color: "var(--bad)" }}>low &lt;40</span></span>
      </div>
    </div>
  );
}
