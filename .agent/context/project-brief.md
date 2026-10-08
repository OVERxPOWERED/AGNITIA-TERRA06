# Project brief

**Hackathon problem:** Renewable Energy Generation Forecasting Platform — predict solar or wind power for the next hours/days. Required: hourly forecast 24–48 h; ≥ 2 models (simple baseline + ML); MAE/RMSE + uncertainty band; dashboard actual vs predicted; low/high generation alerts; one site with public or synthetic data. Deliverables: platform on a sample site, accuracy comparison vs baseline, dashboard + data assumptions, architecture diagram, repo, short report.

**Our product — TERRA:** hybrid solar + wind for a virtual co-located plant at the Dewas wind belt near Indore (MP). Judges likely value **social impact** and **revenue potential**.

**Hero features**
- H1 Hybrid Control Room — combined forecast, complementarity, supply–demand gap
- H2 Battery Dispatch Advisor — LP plan; backup MWh and CO₂ avoided
- H3 Forecast Trust Layer — per-hour reliability score, calibrated bands
- H4 What-if Simulator — scenario sliders → re-forecast & re-dispatch
- H5 Deviation Shield — DSM deviation-charge estimate + 96-block schedule export

**Models:** M0 persistence / smart persistence · M1 physics on forecast · M2 LightGBM quantile · M3 Chronos-2 zero-shot · M3-FT Chronos-2 LoRA (Kaggle) · M4 ensemble + CQR.

**Data:** Open-Meteo Previous Runs (forecast inputs at true 24/48 h leads, from Jan 2024) + Archive (actual weather) → pvlib/windpowerlib digital twin + realism layer, calibrated on real data (Kaggle Indian solar plants, wind SCADA, CEA MP monthly stats); real-generation benchmark on all-India hourly data.

**Team:** 4 people, 2 developers (Dev A data/ML, Dev B backend/frontend). 10 days. GPU: Kaggle 2× T4, Colab.

**Constraints:** training ≤ 12 h per job; deployment on hold until user says; Open-Meteo free tier non-commercial + CC BY 4.0 attribution.
