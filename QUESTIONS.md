# QUESTIONS.md — Jury Q&A prep (TERRA)

Short answers first. Numbers come from `docs/accuracy-report.md` and `docs/engine-results.md` (test split) — never quote a number that is not there.
Status tags: ✅ answer is final · 🟡 draft, needs team confirmation.

## 0. 30-second pitch
> TERRA forecasts hourly solar + wind generation for the next 48 h for a hybrid plant in Dewas, MP. It beats a naive baseline by 28 % (solar) and 38 % (wind), shows a calibrated uncertainty band, raises low/high/ramp alerts, plans battery/backup dispatch and estimates deviation (DSM) charges. Every number comes from a leak-free backtest.

## 1. Problem & fit

**Q1. What problem do you solve?** ✅
Solar and wind output swings with weather. Operators must commit a schedule a day ahead; errors cost deviation charges and backup fuel. We give a forecast, how much to trust it, and what to do about it.

**Q2. Who is the user?** 🟡
Small and medium renewable plants (1–25 MW) that cannot afford an enterprise forecasting service, and the QCAs that serve them.

**Q3. How does this meet the problem statement?** ✅
Hourly 24–48 h forecast ✔ · 6 models compared (baseline + ML) ✔ · MAE/RMSE + uncertainty band ✔ · actual-vs-predicted dashboard ✔ · low/high alerts ✔ · architecture, repo, report ✔.

## 2. Data (expect hard questions here)

**Q4. Is the plant real?** ✅
No. It is a *virtual digital twin at a real location* (Dewas). Weather is real (Open-Meteo, ECMWF IFS). Generation is simulated with pvlib/windpowerlib, then given realistic behaviour (outages, soiling, curtailment, noise) calibrated on real Indian plant data. We say this on the dashboard and in the docs.

**Q5. Why synthetic data?** ✅
No public multi-year hybrid plant data exists near Indore. The problem statement allows "public or synthetic data". A twin gives a clean ground truth for fair model comparison.

**Q6. Then how do we know it works on a real plant?** ✅ (honest)
We don't claim that yet. Next step is a pilot: run TERRA beside a real plant's SCADA/meter data and compare with their current forecast. The pipeline accepts real generation as a drop-in.

**Q7. Does the model only learn your simulator?** 🟡
Partly, yes, for the physics part. That is why we calibrated the twin on real data, and why the ML models are judged against a persistence baseline and not against the twin's formula alone.

## 3. Models & accuracy

**Q8. Which models did you compare?** ✅
Persistence (baseline), week-mean, physics model, LightGBM quantile, Chronos-2 (zero-shot, no fine-tuning), and an ensemble.

**Q9. How accurate is it?** ✅ (test split, normalised by plant capacity)

| | Persistence | Best ML | Improvement |
|---|---|---|---|
| Solar nMAE | 5.43 % | 3.92 % (GBM / ensemble) | ~28 % |
| Wind nMAE | 12.94 % | 7.98 % (GBM) | ~38 % |

Solar MAE is 1.57 MW on a 40 MW plant; wind MAE is 3.99 MW on 50 MW.

**Q10. Solar nMAE looks low. Is it inflated by night hours?** ✅
Yes, night is zero and easy. We report daylight-only too: GBM 7.26 % vs persistence 10.06 %. The improvement holds.

**Q11. Why is the improvement not larger?** 🟡
Forecast weather already carries most of the signal and we use *strict* lead mapping (24 h / 48 h-old forecasts only). Looser mapping would show better numbers but would leak future information. We chose honesty.

**Q12. In wind the ensemble is worse than plain LightGBM. Why ship an ensemble?** 🟡
Ensemble is best/equal on solar and has better band coverage; on wind GBM alone is slightly better (7.98 % vs 8.31 %). We report both and let the dashboard model selector show it.

**Q13. Why not deep learning only?** ✅
We did try one: Chronos-2 zero-shot. It is competitive on wind but not better than LightGBM, and needs a GPU. LightGBM is fast, cheap, explainable.

## 4. No data leakage

**Q14. How do you prevent leakage?** ✅
Features are only: forecast weather, calendar/sun-geometry, and generation observed at or before issue time. Actual weather is never a feature. Splits are by time, never shuffled. Forecasts used for lead L must have been issued before the issue time (ADR-009).

## 5. Uncertainty band

**Q15. How do you produce the band?** ✅
Quantile LightGBM (P10–P90) then conformal calibration so the band's coverage matches its label.

**Q16. Is the band reliable?** ✅ (honest)
Solar 80 % band covers 92 % (slightly wide, safe). Wind 80 % band covers only 73 % because test-period weather shifted from training. Hybrid band 72.6 %. We disclose this.

**Q17. What is the Trust score?** 🟡
A 0–100 score per hour, built from band width and model disagreement. It correlates with actual error (Spearman −0.67 solar, −0.52 wind), so low-trust hours really are the bad ones.

## 6. Alerts

**Q18. How are alert thresholds chosen?** ✅
From the training split only: P10 of generation = "low", P90 = "high", P95 of hourly change = "ramp" (ADR-010). Fixed thresholds were tried first and either never fired or fired every day.

**Q19. Do the alerts actually work?** 🟡
Precision/recall are evaluated on the test split and listed in `docs/engine-results.md`. Wind low-alert fires rarely because its P10 is almost zero; we widened it to P25 from training data.

## 7. Business value

**Q20. Does a better forecast save money?** ✅ (honest)
Deviation Shield (illustrative rates): wind charges drop from ₹1.28 cr to ₹0.43 cr (−66 %), solar from ₹0.54 cr to ₹0.27 cr (−49 %) versus persistence. Dispatch cost gain is small (~0.7 % total cost) because backup demand dominates. Rates are marked *illustrative* until verified.

**Q21. What is a QCA and are you replacing it?** ✅
A Qualified Coordinating Agency handles forecasting, scheduling and settlement for small RE generators. TERRA is *not* a QCA. We are the software/intelligence layer that a plant or QCA uses.

**Q22. Why would a small plant pay for this?** 🟡
Per-plant fixed costs of a full QCA service are heavy for small plants. A shared, automated platform lowers the cost per plant. Any price is a hypothesis to test in customer interviews, not a measured fact.

**Q23. Is the weather data free for commercial use?** ✅
Free Open-Meteo tier is non-commercial (CC BY 4.0, we show attribution). A commercial product needs the paid plan, or NOAA GFS / ECMWF open data. The code isolates the weather provider so it can be swapped.

## 8. Engineering

**Q24. Architecture?** ✅
`Open-Meteo → feature pipeline → models (GBM/Chronos/physics) → ensemble + conformal band → engines (alerts, trust, dispatch, DSM) → FastAPI → Next.js dashboard`. See `docs/architecture.md`.

**Q25. How is it tested?** ✅
`make test` runs offline unit tests, including a leakage test for Chronos covariates. All figures are generated by `terra report`, not typed by hand.

**Q26. Is it deployed?** ✅
Docker Compose locally; cloud config prepared (Render + Vercel + Neon) but deliberately on hold.

## 9. What we did not do (say it before they ask)
- No real plant telemetry yet.
- Chronos-2 was zero-shot only; LoRA fine-tuning was not done.
- Wind uncertainty under-covers under seasonal shift.
- DSM / cost numbers are illustrative.
- Not a regulated QCA.

---

# How to impress the jury in conversation

1. **Lead with honesty.** Say "virtual twin, real weather" in the first minute. Judges punish discovered gaps, reward disclosed ones.
2. **Answer in three beats:** claim → one number → one limit. ("28 % better than persistence on solar; the wind band under-covers at 73 %.")
3. **Know your 5 numbers by heart:** 3.9 % / 8.0 % nMAE, 28 % / 38 % over baseline, 73 % wind coverage.
4. **Say "I don't know, here is how we'd find out"** rather than bluffing. Then name the pilot.
5. **Show, don't tell:** open the dashboard; click a low-trust hour and show it was the bad one.
6. **Turn weaknesses into design choices:** strict lead mapping lowers our score on purpose, which is why you can trust it.
7. **Split the team:** one person owns ML/data, one owns product/business. Hand off by name; don't both answer everything.
8. **Don't say:** "95 % accurate", "replaces QCAs", "real plant data".

---

# Question log (grows as we practise)
<!-- Add: Q#, jury asked, our answer, my correction -->
