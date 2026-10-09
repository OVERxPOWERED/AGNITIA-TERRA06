# TERRA Pitch Deck

1. Title Slide: TERRA Hybrid Forecaster (Virtual 90 MW Plant, Dewas, MP)
2. The Problem: Tightening CERC DSM Tolerance Bands (±5% solar / ±10% wind) & Costly Fossil Backup
3. The Solution: Calibrated Digital Twin + LightGBM Quantile Ensemble & CQR Uncertainty Bands
4. Control Room Demo: Replay Mode (2026-04-10T00), Live Trust Ribbon & Deficit Alerts
5. Models & Accuracy: Six models compared (incl. Chronos-2 zero-shot benchmark); Ensemble beats persistence by 27.8% (solar) and 35.8% (wind); tuned LightGBM achieves 38.3% skill on wind and 27.8% on solar; Chronos-2 achieves 37.4% skill on wind with lowest RMSE (5.94 MW); calibrated uncertainty bands (daylight solar 84.8% PICP80; wind 72.6% PICP80 / tuned LightGBM 76.8%, reflecting monsoon shift)
6. Hero Features: Trust Score (Spearman -0.665 solar / -0.518 wind), Data-Driven Alerts & What-if Simulator
7. Dispatch & Impact: 214.8 tCO2 avoided, 304.7 MWh fossil backup avoided (950.7 MWh vs no battery), ₹29.91 Lakhs backup cost saved (₹29,90,857), ₹1.11 Cr illustrative DSM savings (₹1,11,45,303)
8. Architecture Diagram: Strict leak-free lead mapping (24 h / 48 h), FastAPI backend, 10-page Next.js UI
9. Go-to-Market & Business Case: QCA & IPP partnerships (illustrative pricing & market size; verify before external use)
10. Team, Honesty & Vision: Real weather data (Open-Meteo CC BY 4.0), virtual twin calibrated on real Indian plant data
