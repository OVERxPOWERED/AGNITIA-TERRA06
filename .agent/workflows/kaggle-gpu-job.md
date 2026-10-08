---
description: Run a GPU job (Chronos-2 inference or LoRA fine-tune) on Kaggle within the time budget.
---

# Kaggle GPU job

1. Export inputs: `make export-kaggle` → `data/kaggle_upload/` (train+val only for fine-tuning; never test).
2. Create/update a **private** Kaggle dataset with those files (`kaggle datasets version -p data/kaggle_upload -m "<msg>"`).
3. Open `ml/kaggle/chronos2_finetune.ipynb` on Kaggle; Accelerator = GPU T4 ×2; Internet on (for pip/HF download).
4. Pin versions in the first cell; print `torch.cuda.device_count()`; verify `Chronos2Pipeline.fit` signature.
5. Time box: stop at 2 h; hard cap 12 h. Log start/end wall-clock time.
6. Save checkpoint + `meta.json` to `/kaggle/working/`; download; place in `artifacts/chronos2_ft/<version>/`.
7. Evaluate locally with `make backtest MODEL=chronos2_ft`; record results and train time in `COMPLETION.md` log.
