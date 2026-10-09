"use client";
/** Control Room: combined forecast with band, solar/wind P50s, demand, trust strip, next alerts, KPIs. */
import React, { useMemo } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Badge, Card, CardTitle, Kpi } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAlerts, useDispatch, useForecast } from "@/hooks/api";
import { mw, mwh, toIST } from "@/lib/format";
import { useTheme } from "@/lib/theme";

export default function ControlRoom() {
  const { resolvedTheme, colors } = useTheme();
  const hybrid = useForecast("hybrid");
  const solar = useForecast("solar");
  const wind = useForecast("wind");
  const dispatch = useDispatch("advisor");
  const alerts = useAlerts();

  const option = useMemo(() => {
    if (!hybrid.data || !solar.data || !wind.data) return null;
    const pts = hybrid.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    const demand = dispatch.data?.points.map((p) => [p.target_time_utc, p.demand_mw]) ?? [];
    return {
      ...timeAxisOption("MW", {}, resolvedTheme),
      series: [
        ...bandSeries("Hybrid", pts, colors.hybrid, "hyb"),
        {
          name: "Solar P50",
          type: "line",
          data: solar.data.points.map((p) => [p.target_time_utc, p.q50]),
          lineStyle: { color: colors.solar, type: "dashed", width: 1.8 },
          itemStyle: { color: colors.solar },
          symbol: "none",
        },
        {
          name: "Wind P50",
          type: "line",
          data: wind.data.points.map((p) => [p.target_time_utc, p.q50]),
          lineStyle: { color: colors.wind, type: "dashed", width: 1.8 },
          itemStyle: { color: colors.wind },
          symbol: "none",
        },
        {
          name: "Demand",
          type: "line",
          data: demand,
          lineStyle: { color: colors.demand, width: 1.8 },
          itemStyle: { color: colors.demand },
          symbol: "none",
        },
      ],
    } as const;
  }, [hybrid.data, solar.data, wind.data, dispatch.data, resolvedTheme, colors]);

  const h = hybrid.data?.points ?? [];
  const hasData = Boolean(hybrid.data && h.length > 0);
  const energy = hasData ? h.reduce((s, p) => s + p.q50, 0) : null;
  const minP = hasData ? Math.min(...h.map((p) => p.q10)) : null;
  const maxP = hasData ? Math.max(...h.map((p) => p.q90)) : null;
  const avgTrust = hasData ? h.reduce((s, p) => s + p.trust_score, 0) / h.length : null;
  const upcoming = (alerts.data ?? []).filter((a) => !a.acknowledged).slice(0, 4);

  const forecastQueries = [hybrid, solar, wind, dispatch];
  const retryingForecast = forecastQueries.filter((q) => q.failureCount > 0 && !q.isError);
  const isForecastRetrying = retryingForecast.length > 0;
  const forecastAttempt = isForecastRetrying ? Math.max(...retryingForecast.map((q) => q.failureCount)) : 1;

  const isAlertsRetrying = alerts.failureCount > 0 && !alerts.isError;
  const isForecastLoading = hybrid.isLoading || solar.isLoading || wind.isLoading || dispatch.isLoading;
  const forecastError = hybrid.error ?? solar.error ?? wind.error ?? dispatch.error;
  const refetchForecast = () => Promise.all([hybrid.refetch(), solar.refetch(), wind.refetch(), dispatch.refetch()]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 border-b border-border/60 pb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Control Room</h1>
          <p className="text-xs text-muted mt-0.5">
            Real-time hybrid dispatch overview, forecast bands & operational alerts
          </p>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi label="Next 48 h energy (P50)" value={energy !== null ? mwh(energy) : "—"} hint="Expected total output" />
        <Kpi label="Lowest likely (P10)" value={minP !== null ? mw(minP) : "—"} hint="Conservative floor" />
        <Kpi label="Highest likely (P90)" value={maxP !== null ? mw(maxP) : "—"} hint="Optimistic ceiling" />
        <Kpi label="Average trust" value={avgTrust !== null ? `${avgTrust.toFixed(0)} / 100` : "—"} hint="Model confidence score" />
        <Kpi label="Backup needed (plan)" value={dispatch.data ? mwh(dispatch.data.kpis.advisor.backup_mwh) : "—"} hint="Advisor dispatch strategy" />
      </div>

      {/* Combined Forecast Chart with Uncertainty Band & Trust Ribbon */}
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">Combined solar + wind forecast with 80% band</CardTitle>
          <span className="text-xs text-muted">Hourly resolution · P10 to P90 uncertainty interval</span>
        </div>
        <QueryState
          isLoading={isForecastLoading}
          error={forecastError}
          refetch={refetchForecast}
          isRetrying={isForecastRetrying}
          retryCount={forecastAttempt}
          height="h-[380px]"
        >
          {option && (
            <EChart
              option={option}
              height={360}
              ariaLabel="Hybrid forecast for the next 48 hours with P10–P90 band, solar and wind medians and demand"
            />
          )}
          <div className="pt-2 border-t border-border/50">
            <TrustRibbon points={h} />
          </div>
        </QueryState>
      </Card>

      {/* Next Alerts Card */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <CardTitle className="mb-0">Next alerts</CardTitle>
          <span className="text-xs text-muted">Unacknowledged active windows</span>
        </div>
        <QueryState
          isLoading={alerts.isLoading}
          error={alerts.error}
          refetch={alerts.refetch}
          empty={!upcoming.length}
          height="h-20"
          isRetrying={isAlertsRetrying}
          retryCount={alerts.failureCount}
        >
          <ul className="divide-y divide-border/60">
            {upcoming.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <Badge tone={a.severity === "critical" ? "bad" : a.severity === "warning" ? "warn" : "neutral"}>
                    {a.severity}
                  </Badge>
                  <span className="font-medium text-text">{a.message}</span>
                </div>
                <div className="text-xs text-muted tabular-nums">
                  {toIST(a.start_utc)} → {toIST(a.end_utc)}
                </div>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
    </div>
  );
}
