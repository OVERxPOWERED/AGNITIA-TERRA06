# Kaggle GPU Inference for Chronos-2 Zero-Shot

This folder contains the notebook and metadata to run zero-shot Chronos-2 (`amazon/chronos-2`) generation forecasting with weather covariates on Kaggle GPU (T4 x2).

## Prerequisites

1. **Kaggle Account Phone Verification**:
   - Go to Kaggle account settings: `https://www.kaggle.com/settings`
   - Under **Phone Verification**, verify your mobile number.
   - This unlocks GPU accelerators and Internet connectivity in notebook execution.

2. **Dataset Bundle**:
   - Exported bundle: `overxpowered/terra06-bundle-20261009` (Private, Open-Meteo CC BY 4.0).
   - Generated with `./.venv/bin/terra export-kaggle`.

## Execution

Push the notebook directly via the Kaggle CLI:

```bash
cd ml/kaggle
kaggle kernels push -p .
kaggle kernels status overxpowered/terra-chronos2-zs
```

Once complete, download the outputs into the repository:

```bash
kaggle kernels output overxpowered/terra-chronos2-zs -p ../../artifacts/chronos/
```

Outputs written:
- `solar_chronos2_zs.parquet` (and `chronos2_zs_solar.parquet`)
- `wind_chronos2_zs.parquet` (and `chronos2_zs_wind.parquet`)
- `meta.json` (model ID, package version, GPU device, wall-clock time, row counts)
