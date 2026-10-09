#!/usr/bin/env python3
"""Create a deployment bundle of model and forecast artifacts needed at runtime.

Outputs:
  dist/terra-artifacts-<UTC timestamp>.zip
  dist/terra-artifacts-<UTC timestamp>.zip.sha256

Only runtime-required files are included:
  - Active run in runs/ (referenced by runs/LATEST)
  - Evaluation results in evaluation/results.json
  - Day-ahead predictions in backtests/*/predictions.parquet
  - Active model bundles in models/*/ (referenced by LATEST)

Strictly refuses to include secrets, .env files, or kaggle credentials.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sys
import zipfile

FORBIDDEN_SUBSTRINGS = ("secret", ".env", "kaggle", ".key", ".pem", "credential", "token")


def check_forbidden(path: Path) -> None:
    path_str = str(path).lower()
    for forbidden in FORBIDDEN_SUBSTRINGS:
        if forbidden in path_str:
            raise ValueError(f"Security check failed: candidate file '{path}' contains forbidden substring '{forbidden}'")


def collect_runtime_files(artifacts_dir: Path) -> list[tuple[Path, str]]:
    """Determine runtime files from artifacts directory. Returns list of (absolute_path, arcname)."""
    if not artifacts_dir.exists():
        raise FileNotFoundError(f"Artifacts directory '{artifacts_dir}' does not exist")

    files_to_bundle: list[tuple[Path, str]] = []

    # 1. Runs: LATEST and files in latest run folder
    latest_file = artifacts_dir / "runs" / "LATEST"
    if not latest_file.is_file():
        raise FileNotFoundError(f"Missing runs pointer: {latest_file}")
    latest_run_name = latest_file.read_text().strip()
    files_to_bundle.append((latest_file, "runs/LATEST"))

    latest_run_dir = artifacts_dir / "runs" / latest_run_name
    if not latest_run_dir.is_dir():
        raise FileNotFoundError(f"Missing latest run directory: {latest_run_dir}")
    for item in sorted(latest_run_dir.rglob("*")):
        if item.is_file():
            arcname = str(item.relative_to(artifacts_dir))
            files_to_bundle.append((item, arcname))

    # 2. Evaluation: results.json
    eval_file = artifacts_dir / "evaluation" / "results.json"
    if eval_file.is_file():
        files_to_bundle.append((eval_file, "evaluation/results.json"))

    # 3. Backtests: predictions.parquet for solar & wind
    for source in ("solar", "wind"):
        pred_file = artifacts_dir / "backtests" / source / "predictions.parquet"
        if not pred_file.is_file():
            raise FileNotFoundError(f"Missing backtest predictions: {pred_file}")
        files_to_bundle.append((pred_file, f"backtests/{source}/predictions.parquet"))

    # 4. Models: active bundles referenced by LATEST
    model_targets = [
        ("solar", "bundle", True),
        ("wind", "bundle", True),
        ("hybrid", "engines", True),
        ("solar", "bundle_multisite", False),     # optional: trained by `terra train-multisite`
        ("wind", "bundle_multisite", False),
    ]
    for source, subkind, required in model_targets:
        model_latest = artifacts_dir / "models" / source / subkind / "LATEST"
        if not model_latest.is_file():
            if not required:
                continue
            raise FileNotFoundError(f"Missing model LATEST pointer: {model_latest}")
        latest_ver = model_latest.read_text().strip()
        files_to_bundle.append((model_latest, f"models/{source}/{subkind}/LATEST"))

        ver_dir = artifacts_dir / "models" / source / subkind / latest_ver
        if not ver_dir.is_dir():
            raise FileNotFoundError(f"Missing model version directory: {ver_dir}")
        for item in sorted(ver_dir.rglob("*")):
            if item.is_file():
                arcname = str(item.relative_to(artifacts_dir))
                files_to_bundle.append((item, arcname))

    # 5. Multi-site extras: per-site alert thresholds and the leave-one-site-out evidence
    for name in ("alert_thresholds.json", "loso_metrics.csv", "pooled_test_by_site.csv", "meta.json"):
        f = artifacts_dir / "multisite" / name
        if f.is_file():
            files_to_bundle.append((f, f"multisite/{name}"))

    # Validate against forbidden tokens
    for file_path, arcname in files_to_bundle:
        check_forbidden(file_path)
        check_forbidden(Path(arcname))

    return files_to_bundle


def create_bundle(artifacts_dir: Path, dist_dir: Path, custom_zip_name: str | None = None) -> tuple[Path, Path, str]:
    files = collect_runtime_files(artifacts_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_name = custom_zip_name or f"terra-artifacts-{timestamp}.zip"
    zip_path = dist_dir / zip_name
    sha_path = dist_dir / f"{zip_name}.sha256"

    total_uncompressed = 0
    print(f"Creating deploy bundle from: {artifacts_dir}")
    print("Files to include:")
    for path, arcname in sorted(files, key=lambda x: x[1]):
        size = path.stat().st_size
        total_uncompressed += size
        print(f"  {arcname:48s} ({size:>10,d} bytes)")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path, arcname in files:
            zf.write(path, arcname)

    # Compute sha256
    hasher = hashlib.sha256()
    with zip_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    digest = hasher.hexdigest()

    sha_content = f"{digest}  {zip_path.name}\n"
    sha_path.write_text(sha_content, encoding="utf-8")

    zip_size = zip_path.stat().st_size
    print("\nDeploy bundle created successfully:")
    print(f"  Zip file:         {zip_path}")
    print(f"  SHA256 file:      {sha_path}")
    print(f"  Total files:      {len(files)}")
    print(f"  Uncompressed:     {total_uncompressed:,d} bytes ({total_uncompressed / (1024*1024):.2f} MB)")
    print(f"  Compressed zip:   {zip_size:,d} bytes ({zip_size / (1024*1024):.2f} MB)")
    print(f"  SHA256:           {digest}")

    return zip_path, sha_path, digest


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deployment bundle for TERRA runtime artifacts.")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Path to artifacts directory (defaults to TERRA_ARTIFACTS_DIR env var or ./artifacts)",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Output directory for bundle (default: dist)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Custom zip filename",
    )
    args = parser.parse_args()

    artifacts_dir = args.artifacts_dir
    if artifacts_dir is None:
        env_val = os.environ.get("TERRA_ARTIFACTS_DIR")
        artifacts_dir = Path(env_val) if env_val else Path("artifacts")

    try:
        create_bundle(artifacts_dir, args.dist_dir, args.name)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
