---
description: Final pre-submission checklist for the hackathon (run on Day 10).
---

# Release checklist

- [ ] Fresh clone → `make setup data train backtest` works (or documented artifact download)
- [ ] `make api` + `make web` run; every page loads in REPLAY mode with no console errors
- [ ] All hackathon requirement boxes in `COMPLETION.md` ticked
- [ ] `docs/accuracy-report.md`, `docs/data-assumptions.md`, `docs/architecture.md`, `docs/business-case.md`, report PDF present
- [ ] Numbers in README/report/pitch match `docs/accuracy-report.md`
- [ ] Attribution and "virtual twin" provenance visible in UI
- [ ] No secrets/data in git (`git ls-files | grep -Ei "env|kaggle|parquet"` is clean)
- [ ] Demo script rehearsed; backup recording saved
- [ ] Tag `v1.0`
