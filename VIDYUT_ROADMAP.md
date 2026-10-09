# VIDYUT_ROADMAP.md — Phases 10–17: Vidyut rename, plant types and operator features

> **Read this first.** Phases 0–9 (`IMPLEMENTATION_ROADMAP.md`) are finished and deployed. This document is the
> build guide for everything after them. It continues the same numbering (Phase 10 onward) and the same task
> format, and has its own tracker: **`VIDYUT_COMPLETION.md`** (one checkbox per task ID below).
>
> It was written against the repository at commit `004062e` (`main`, 9 Oct 2026) and **every code file in it was
> run** in a copy of that commit: the rename script, ML tests (65 pass), backend tests (35 pass), `ruff`, frontend
> `tsc` + `eslint` + `next build`, and a browser walk-through of the new pages with a solar-only plant. If your
> `main` moved after `004062e`, see §F "If your code differs".

---

## A. What this phase set delivers

| # | Feature | What the operator sees | Phase |
|---|---|---|---|
| 1 | **Rename to Vidyut** | product, package (`vidyut`), CLI (`vidyut …`), env vars (`VIDYUT_*`), UI all say Vidyut | 10 |
| 2 | **Plant types** — solar-only, wind-only, hybrid | every page shows only the sources the plant has; "Plant total" replaces "Hybrid" where needed | 11 |
| 3 | **State rule profiles** (CERC 2026, Gujarat GERC 2019, MP MPERC 2018 template) | the deviation rules of *their* state; badge says verified / unverified | 12 |
| 4 | **Charge explanation** | any 15-min block's charge explained step by step (formula → bands → ₹) | 12, 14 |
| 5 | **Penalty simulator** | change rules (profile, PPA rate, tolerance, harshness) *and* schedule (P-level, manual block edits) and see ₹ | 12, 14 |
| 6 | **Revision Advisor + explainability log** (penalty-aware alerts that recommend a revision) | "Revision recommended" card with highlighted triggers, Accept / Reject, revision counter, event-log window | 12–14 |
| 7 | **Daily accuracy & deviation report** | on-screen report + PDF download for any finished day | 12–14 |
| 8 | **Plant setup wizard** (first open) | 5-step wizard: plant & type → state & rules → equipment → WhatsApp contacts → review | 13, 14 |
| 9 | **WhatsApp notifications** | alerts and revision requests on WhatsApp; reply `YES <code>` / `NO <code>` to decide | 13, 15 |
| 10 | **Production plumbing** | hourly refresh on the free tier (GitHub Actions → `/jobs/tick`), state kept in Neon, one-click retrain (stretch) | 16 |

Already existed before this guide (not rebuilt here): trust score, conformal calibration (CQR), high/low/ramp alerts.

## B. Three design decisions you must understand before coding

**B1. Reference plant vs your plant (Phase 11).** The models were trained on one *reference* plant (the Dewas
virtual twin, `config/site.yaml`). An operator's plant is described by an overlay file `config/plant.yaml`
(written by the setup wizard). Forecasting always runs the trained models on the reference plant and then maps
every source to the operator's plant by **capacity scaling** (`plant MW = reference MW × plant capacity ÷ reference
capacity`). This is instant, so the wizard works on the free tier. Anything scaling cannot capture (far location,
different turbine model, different DC/AC ratio, tilt) is listed as a note and the UI shows "Approximate forecast —
retrain recommended". Retraining for the exact plant is a separate button (local thread in development, GitHub
Actions in production). A plant *type* change is just "which sources exist" — no retraining needed as long as the
reference has those sources.

**B2. Everything the operator does lives in the database (Phases 13–16).** Render's free tier wipes the disk on
every deploy and restart. So schedules, recommendations, decisions, the event log, WhatsApp contacts, the plant
setup (as YAML text) and the replay clock are stored in Postgres (Neon) — and the plant YAML is re-written to
`config/plant.yaml` at API start-up. Forecast numbers stay in Parquet run folders as before; the Rev-0 forecast
quantiles a report needs are copied into the database when the day-ahead schedule is accepted.

**B3. Refreshes come from outside on the free tier (Phase 16).** A sleeping Render instance never runs its
in-process scheduler. A GitHub Actions cron calls `POST /jobs/tick` every hour (with a secret header); that wakes
the API and produces one forecast run → day-ahead proposal → revision check → WhatsApp. Locally the APScheduler
job calls the *same* function (`app/services/jobs.py::produce_run`).

## C. The operator workflow (what the code implements)

```
forecast run (tick) ──► day-ahead proposal (next IST day, penalty-aware P-level) ──► operator Accept ─► Rev 0
        │                                                                                          │
        └──► every later run: compare the refreshed forecast with the ACTIVE schedule of "today" ◄──┘
                 triggers: BAND_BREACH_RISK · FORECAST_SHIFT · ALERT · LOW_TRUST · BLOCKED (rule limits)
                 recommend only if a strong trigger fires AND expected saving ≥ ₹500 AND rules allow it
                       │
                       ▼
              Recommendation (pending) ──► WhatsApp "YES abc123 / NO abc123" or dashboard Accept/Reject
                       │                                   │
                       ▼                                   ▼
              superseded by a newer one          Rev n (effective from block k+3)  ──► CSV for the QCA
Every step is written to the event log (the explainability window). Vidyut NEVER submits to the grid: the
operator sends the schedule to the SLDC through the QCA.
```

## D. New API (contract for the frontend developer)

| Method & path | Phase | Purpose |
|---|---|---|
| `GET /site` (extended) | 11 | + `plant_type`, `sources`, `output_sources`, `total_source`, `approximate`, `mapping_notes`, `distance_km` |
| `GET /forecast?source=` | 11 | `source` optional (default = plant total); a source the plant lacks → 404 |
| `GET /dsm/profiles` | 13 | active rule profile + reason + all profiles |
| `POST /dsm/explain` | 13 | `{schedule_mw, actual_mw, source?, profile_id?, contract_rate_inr_per_kwh?, label?}` → steps, bands, ₹ |
| `POST /dsm/simulate` | 13 | `SimInput` → expected (`day:"next"`) or realised (`day:"YYYY-MM-DD"`) charges per block |
| `GET /schedule/today?date=` | 13 | active schedule, all versions, revisions used / allowed |
| `GET /schedule/active.csv?date=` | 13 | the accepted version as the 96-block CSV |
| `GET /recommendations?status=` | 13 | day-ahead proposals and revision recommendations |
| `POST /recommendations/{id}/decision` | 13 | `{accept, user, note}` → 200, 404, or 409 if already decided |
| `GET /events?kind=` | 13 | event log (newest first) |
| `GET /reports/days`, `GET /reports/daily?date=`, `GET /reports/daily.pdf?date=` | 13 | daily report (409 if not ready) |
| `GET /setup/status`, `GET /setup/options`, `POST /setup`, `POST /setup/retrain`, `GET /setup/job` | 13 | wizard |
| `GET /notify/status`, `GET /notify/contacts`, `POST /notify/test` | 13 | WhatsApp settings page |
| `POST /webhooks/twilio`, `GET/POST /webhooks/meta` | 13/15 | WhatsApp replies (signature-checked) |
| `POST /jobs/tick` (header `X-Job-Token`) | 13/16 | produce one run (cron) |
| SSE event `workflow` | 13 | after each run: refetch recommendations / schedule / events |

## E. Plan for the remaining days (2 developers)

| Day | Dev A (ML + backend + deploy) | Dev B (frontend + docs + demo) |
|---|---|---|
| 1 | Phase 10 rename (both pair on it for 1 h, then A finishes migrate/deploy notes); Phase 11 ML + backend | Phase 10 frontend check; Phase 11 frontend (needs `make types` after A's 11.4) |
| 2 | Phase 12 engines (rules, DSM v2, simulator, revision, report, single-source training) | Phase 14.1 shared UI (types, hooks), 14.2 Deviation page with mocked JSON from §D |
| 3 | Phase 13 backend (DB, services, routes, tests) | Phase 14.3–14.4 Revisions & Log, Daily Report |
| 4 | Phase 13 finish + Phase 15 WhatsApp (Twilio sandbox live) | Phase 14.5–14.7 Setup wizard, Settings, App shell |
| 5 | Phase 16 deploy (lock, bundle with replay data, tick cron, env) | Phase 17 demo script, EXPLAIN/README updates, screenshots |
| 6 | Phase 17 integration + bug fixes; stretch 16.5 retrain workflow | Phase 17 rehearsal; buffer |

Keep `main` runnable: one branch per subphase (`feat/11.2-plant-mapping`), merge when its *Check* passes.

## F. How to use this guide (for you and your AI model)

1. Work top to bottom. A task's **FILE** block is the complete file content — create or overwrite the file with it
   exactly. Small edits are given as "replace X with Y" with the exact text.
2. Status labels: **✅ Tested** = this exact file ran and passed in the reference copy; **📝 Do** = commands or
   console steps to perform; **🧩 Spec** = written carefully but not executable in the planning sandbox
   (needs external accounts: Twilio, Meta, Render, GitHub secrets).
3. After each task run its **Check**. Tick the task in `VIDYUT_COMPLETION.md` and add a log line.
4. Commit per subphase: `<area>(<subphase>): <summary>`, e.g. `ml(11.2): plant mapping by capacity scaling`.
5. **If your code differs from `004062e`** (you changed files after that commit): for each FILE block, diff it
   against your file first (`git diff --no-index yourfile guidefile`) and keep your extra changes. The places most
   likely to conflict are listed in each subphase under "Touches".
6. Paths: Python commands run inside your virtualenv from the repo root unless a `cd` is shown. Windows users: use
   WSL or Git Bash for the shell snippets.

---

## PHASE 10 — Rename TERRA → Vidyut (Day 1)

Goal: the product, the Python package, the CLI, environment variables, UI and docs say **Vidyut**, while the
deployed site, the trained artifacts and old environment variables keep working.

What changes and what must NOT change:

| Changes | Stays as is (external identifiers) |
|---|---|
| `ml/terra/` → `ml/vidyut/`, `import terra` → `import vidyut` | GitHub repo `OVERxPOWERED/AGNITIA-TERRA06` (and every URL containing it) |
| CLI `terra …` → `vidyut …` | the published release asset `terra-artifacts-20261009T024331Z.zip` |
| `TERRA_*` env vars → `VIDYUT_*` (old names still accepted) | Render service name `terra-api` (renaming it changes the public URL) |
| UI text, page titles, docs, AGENTS.md, `.agent/` | Kaggle dataset / kernel slugs and the archived notebook in `ml/kaggle/` |
| strategy labels `terra_p50` / `terra_optimized` → `vidyut_*` | `IMPLEMENTATION_ROADMAP.md` / `IMPLEMENTATION_COMPLETION.md` (history) |

Why it needs care: trained models are **pickles**. A pickle stores the full class path, e.g.
`terra.pipelines.bundle.ForecastBundle`; after the rename that module no longer exists and loading fails with
`ModuleNotFoundError: No module named 'terra'`. Task 10.2 adds a small compatibility layer and a one-off
migration so the old artifacts (and the live deployment) keep working.

---

### 10.1 Run the rename  ·  Owner: Dev A + Dev B together (1 h)  ·  Depends on: Phase 9 finished

Touches: almost every file. Do it first, on a clean tree, before anyone starts Phase 11 work — otherwise
every open branch conflicts.

#### T10.1.1 — Prepare a clean branch  📝
```bash
git checkout main && git pull
git status                       # must print "nothing to commit, working tree clean"
git checkout -b feat/10.1-rename-vidyut
cp -r artifacts ../artifacts-backup-before-rename     # artifacts are gitignored: keep a copy
```
Tell your teammate: no pushes to `main` until 10.3 is merged.

#### T10.1.2 — Add the rename script  ✅ Tested
**FILE: `scripts/rename_to_vidyut.py`** — ✅ Tested

````python
#!/usr/bin/env python3
"""One-shot rename of the project from TERRA to Vidyut (Phase 10, task T10.1.2).

What it does (idempotent — running it twice changes nothing the second time):
  1. git mv ml/terra -> ml/vidyut
  2. rewrites text in every tracked file (except the KEEP list below):
       TERRA_xxx  -> VIDYUT_xxx      (environment variables)
       TerraConfig-> VidyutConfig    (class names that start with Terra)
       TERRA      -> Vidyut          (brand in prose/UI)
       Terra      -> Vidyut
       terra      -> vidyut          (package, CLI command, file names like terra_schedule_*.csv)
     Words that merely contain the letters (terrain, Mediterranean, terraform) are NOT touched.
  3. leaves external identifiers alone (PROTECT list): the GitHub repo name, the already-published
     release asset, the Render service name, Kaggle slugs.

Usage (from the repo root, on a clean working tree):
    python scripts/rename_to_vidyut.py --dry-run     # list files that would change
    python scripts/rename_to_vidyut.py               # do it
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# files / folders never rewritten (history, generated, external ids, binary)
KEEP = (
    "IMPLEMENTATION_ROADMAP.md", "IMPLEMENTATION_COMPLETION.md",   # the finished v1 plan stays as written
    "VIDYUT_ROADMAP.md", "VIDYUT_COMPLETION.md",                   # already use the new name
    "scripts/rename_to_vidyut.py",
    "ml/kaggle/",                        # Kaggle kernel + dataset slugs are external ids (Chronos is comparison-only)
    "frontend/package-lock.json",
    "frontend/src/lib/api/schema.d.ts",  # regenerated by `make types`
    "data/", "notebooks/", "scratch/",   # history / binary samples
)
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".parquet", ".zip", ".pdf", ".joblib", ".pkl", ".woff", ".woff2"}

# external identifiers that must survive the rename byte-for-byte
PROTECT = (
    "AGNITIA-TERRA06", "agnitia-terra06", "AGNITIA TERRA06",        # GitHub repo / hackathon team id
    "terra-artifacts-20261009T024331Z",                             # published release asset (Dockerfile default)
    "name: terra-api",                                              # Render service name -> keeps the same URL
    "terra-api.onrender.com",
    "terra06-bundle", "terra-chronos2-zs",                          # Kaggle slugs
)

RULES = [
    (re.compile(r"(?<![A-Za-z])TERRA_"), "VIDYUT_"),
    (re.compile(r"(?<![A-Za-z])Terra(?=[A-Z])"), "Vidyut"),        # TerraConfig -> VidyutConfig
    (re.compile(r"(?<![A-Za-z])TERRA(?![A-Za-z])"), "Vidyut"),
    (re.compile(r"(?<![A-Za-z])Terra(?![a-z])"), "Vidyut"),
    (re.compile(r"(?<![A-Za-z])terra(?![a-z])"), "vidyut"),
]


def tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [f for f in out.splitlines() if f]


def kept(path: str) -> bool:
    return any(path == k or (k.endswith("/") and path.startswith(k)) for k in KEEP) or Path(path).suffix in BINARY


def rewrite(text: str) -> str:
    placeholders = {}
    for i, p in enumerate(PROTECT):
        key = f"\x00P{i}\x00"
        placeholders[key] = p
        text = text.replace(p, key)
    for rx, new in RULES:
        text = rx.sub(new, text)
    for key, p in placeholders.items():
        text = text.replace(key, p)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if (ROOT / "ml" / "terra").exists() and not a.dry_run:
        subprocess.check_call(["git", "mv", "ml/terra", "ml/vidyut"], cwd=ROOT)
        print("moved ml/terra -> ml/vidyut")

    changed = []
    for f in tracked_files():
        if kept(f):
            continue
        p = ROOT / f
        if not p.is_file():
            continue
        try:
            old = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = rewrite(old)
        if new != old:
            changed.append(f)
            if not a.dry_run:
                p.write_text(new, encoding="utf-8")

    # files whose NAME contains terra (none expected after the folder move, but be safe)
    for f in tracked_files():
        if not kept(f) and re.search(r"(?<![A-Za-z])terra(?![a-z])", Path(f).name):
            target = str(Path(f).with_name(rewrite(Path(f).name)))
            print(f"rename {f} -> {target}")
            if not a.dry_run:
                subprocess.check_call(["git", "mv", f, target], cwd=ROOT)

    print(f"{'would change' if a.dry_run else 'changed'} {len(changed)} files")
    for f in changed:
        print("  ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

#### T10.1.3 — Dry run, then run  📝
```bash
python scripts/rename_to_vidyut.py --dry-run     # lists ~120 files, changes nothing
python scripts/rename_to_vidyut.py               # moves ml/terra -> ml/vidyut and rewrites the files
git status | head -40                            # renamed: ml/terra/... -> ml/vidyut/... and many "modified"
```
Check: `git grep -n -i "terra" -- . ':!IMPLEMENTATION_*' ':!ml/kaggle/*' ':!frontend/package-lock.json' ':!frontend/src/lib/api/schema.d.ts' ':!data/*' ':!notebooks/*' ':!scratch/*' ':!scripts/rename_to_vidyut.py' | grep -v -i "AGNITIA.TERRA06"`
prints only these allowed leftovers: the Kaggle slugs in `.agent/context/decisions.md` (`terra06-bundle…`,
`terra-chronos2-zs`), the Render service name `terra-api` (render.yaml and `terra-api.onrender.com` examples in
docs/AppShell), and the release-asset file name in `backend/Dockerfile`.

---

### 10.2 Compatibility layer  ·  Depends on: 10.1

#### T10.2.1 — `ml/vidyut/compat.py`  ✅ Tested
Two jobs: let old pickles load, and let old `TERRA_*` environment variables keep working (Render still has them).
**FILE: `ml/vidyut/compat.py`** — ✅ Tested

````python
"""Backward compatibility after the TERRA -> Vidyut rename (Phase 10).

1. Old trained artifacts (joblib pickles) store class paths like `terra.pipelines.bundle.ForecastBundle`.
   `install_legacy_aliases()` registers every `vidyut.*` module also under its old `terra.*` name so those
   files still load. `vidyut migrate-artifacts` then re-saves them with the new names (run once).
2. Old environment variables (TERRA_MODE, TERRA_DB_URL, ...) still work: `alias_legacy_env()` copies each
   TERRA_x to VIDYUT_x when VIDYUT_x is not set, so a running deployment keeps working until its
   variables are renamed.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import sys

LEGACY = "terra"
NEW = "vidyut"


def alias_legacy_env(environ: dict | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    copied = []
    for k in list(env):
        if k.startswith("TERRA_"):
            new = "VIDYUT_" + k[len("TERRA_"):]
            if new not in env:
                env[new] = env[k]
                copied.append(new)
    return copied


def install_legacy_aliases() -> int:
    """Import all vidyut submodules (skipping optional heavy ones that fail) and alias them as terra.*."""
    import vidyut
    n = 0
    for m in pkgutil.walk_packages(vidyut.__path__, prefix=f"{NEW}."):
        try:
            importlib.import_module(m.name)
        except Exception:  # noqa: BLE001  (optional deps such as torch/chronos)
            continue
    for name, mod in list(sys.modules.items()):
        if name == NEW or name.startswith(NEW + "."):
            legacy = LEGACY + name[len(NEW):]
            if legacy not in sys.modules:
                sys.modules[legacy] = mod
                n += 1
    return n
````

#### T10.2.2 — `ml/vidyut/__init__.py`  ✅ Tested
Copying `TERRA_x` → `VIDYUT_x` must happen before `vidyut.paths` reads `VIDYUT_ARTIFACTS_DIR` etc.; the package
`__init__` runs first on any `import vidyut.*`, so that is the place.
**FILE: `ml/vidyut/__init__.py`** — ✅ Tested

````python
"""Vidyut forecasting engine (formerly TERRA; see VIDYUT_ROADMAP.md)."""
from vidyut.compat import alias_legacy_env

__version__ = "0.2.0"
alias_legacy_env()          # TERRA_* environment variables keep working after the rename
````

#### T10.2.3 — `ml/vidyut/models/registry.py` (fallback load + migration)  ✅ Tested
`load_object` retries with the legacy aliases only when the error is about the `terra` module, so normal loads
stay fast. `migrate_legacy_artifacts` re-saves every model file with the new names and renames the strategy
labels in evaluation outputs.
**FILE: `ml/vidyut/models/registry.py`** — ✅ Tested

````python
"""Artifact registry: artifacts/models/<source>/<name>/<version>/{model.joblib, meta.json}."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib

from vidyut.paths import ARTIFACTS


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def save_object(obj, source: str, name: str, meta: dict, version: str | None = None) -> Path:
    version = version or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    d = ARTIFACTS / "models" / source / name / version
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, d / "model.joblib")
    (d / "meta.json").write_text(json.dumps({"name": name, "source": source, "version": version,
                                             "git_sha": git_sha(), **meta}, indent=2, default=str))
    latest = d.parent / "LATEST"
    latest.write_text(version)
    return d


def load_object(source: str, ref: str):
    """ref = 'gbm@latest' or 'gbm@20261012T101500'."""
    name, _, version = ref.partition("@")
    base = ARTIFACTS / "models" / source / name
    if version in ("", "latest"):
        version = (base / "LATEST").read_text().strip()
    try:
        return joblib.load(base / version / "model.joblib")
    except ModuleNotFoundError as e:          # artifact saved before the TERRA -> Vidyut rename
        if e.name != "terra" and not str(e.name).startswith("terra."):
            raise
        from vidyut.compat import install_legacy_aliases
        install_legacy_aliases()
        return joblib.load(base / version / "model.joblib")


def migrate_legacy_artifacts() -> list[str]:
    """Re-save every model.joblib so it references `vidyut.*`, and rename strategy labels in evaluation
    outputs (terra_p50 -> vidyut_p50, terra_optimized -> vidyut_optimized). Safe to run twice."""
    from vidyut.compat import install_legacy_aliases
    install_legacy_aliases()
    done = []
    for f in sorted((ARTIFACTS / "models").glob("*/*/*/model.joblib")):
        joblib.dump(joblib.load(f), f)
        done.append(str(f.relative_to(ARTIFACTS)))
    for f in [ARTIFACTS / "evaluation" / "results.json", ARTIFACTS / "evaluation" / "dsm.csv",
              *ARTIFACTS.glob("runs/*/run.json")]:
        if f.exists():
            t = f.read_text()
            new = t.replace("terra_p50", "vidyut_p50").replace("terra_optimized", "vidyut_optimized") \
                   .replace("TERRA virtual twin", "Vidyut virtual twin")
            if new != t:
                f.write_text(new)
                done.append(str(f.relative_to(ARTIFACTS)))
    return done


def load_meta(source: str, ref: str) -> dict:
    name, _, version = ref.partition("@")
    base = ARTIFACTS / "models" / source / name
    if version in ("", "latest"):
        version = (base / "LATEST").read_text().strip()
    return json.loads((base / version / "meta.json").read_text())
````

#### T10.2.4 — CLI command `vidyut migrate-artifacts`  ✅ Tested
Where: `ml/vidyut/pipelines/cli.py`, directly **above** `@app.command()` / `def calibrate()`. Insert:
```python
@app.command("migrate-artifacts")
def migrate_artifacts() -> None:
    """One-off after the TERRA -> Vidyut rename: re-save old artifacts with the new module names."""
    from vidyut.models.registry import migrate_legacy_artifacts
    for f in migrate_legacy_artifacts():
        typer.echo(f"migrated {f}")
```
(The complete final `cli.py` is embedded in T12.5.4; you may also use that version now.)

#### T10.2.5 — Backend accepts old variable names  ✅ Tested
Where: `backend/app/settings.py`. The rename already changed `env_prefix="TERRA_"` to `"VIDYUT_"`. Replace the
`get_settings` function with:
```python
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    from vidyut.compat import alias_legacy_env
    alias_legacy_env()                         # old TERRA_* variables still work after the rename
    return Settings()
```
Note: this covers real environment variables (Render, docker-compose). Values inside `backend/.env` are read by
pydantic directly, so rename the keys in your local `backend/.env` by hand (`sed -i 's/^TERRA_/VIDYUT_/' backend/.env`).

#### T10.2.6 — Ruff knows both package names  ✅ Tested
Where: `ruff.toml`, `[lint.isort]` section. Replace the `known-first-party` line with:
```toml
known-first-party = ["vidyut", "terra", "app"]   # "terra" = old name, still used by the archived Kaggle notebook
```
Without `"terra"` ruff reports an import-order error inside `ml/kaggle/chronos2_infer.ipynb`.

#### T10.2.7 — Re-install the packages  📝
The distribution names changed (`terra` → `vidyut`, `terra-backend` → `vidyut-backend`), so uninstall first:
```bash
pip uninstall -y terra terra-backend
pip install -e "ml[dev,tune,real]" -e "backend[dev]"
vidyut --help                    # the CLI now exists under the new name
```

---

### 10.3 Verify and migrate the artifacts  ·  Depends on: 10.2

#### T10.3.1 — Tests, lint, build  📝
```bash
make lint
cd ml && pytest -q && cd ..                      # all pass (44 before Phase 11 adds more)
cd backend && VIDYUT_SCHEDULER_ENABLED=false pytest -q && cd ..   # 26 pass — loads OLD artifacts through the shim
cd frontend && npm run build && cd ..
```
Check: everything green. `test_whatif` passing proves the old pickles load through the compatibility layer.

#### T10.3.2 — Migrate local artifacts once  📝
```bash
vidyut migrate-artifacts         # prints "migrated models/solar/bundle/<ver>/model.joblib" etc.
python -c "import joblib,glob,sys; [joblib.load(f) for f in glob.glob('artifacts/models/*/*/*/model.joblib')]; print('terra' in sys.modules)"
```
Check: the last command prints `False` (files load without any `terra` module).

#### T10.3.3 — Merge  📝
Commit `chore(10): rename TERRA to Vidyut (package, CLI, env, UI, docs)`, open a PR, wait for CI, merge.

---

### 10.4 Deployment after the rename  ·  Depends on: 10.3

#### T10.4.1 — Nothing breaks on deploy  📝
Push to `main` → Render rebuilds. The Dockerfile still downloads the **old** artifact zip (its URL was protected
by the script); the shim loads it; the old `TERRA_*` variables on Render are copied to `VIDYUT_*`.
Check: `curl https://<your-api>.onrender.com/health` → `"status":"ok"`; the Vercel site shows "Vidyut".

#### T10.4.2 — Rename the Render variables (tidy-up, any time)  📝
Render dashboard → service → Environment: add `VIDYUT_MODE`, `VIDYUT_SCHEDULER_ENABLED`, `VIDYUT_CORS_ORIGINS`,
`VIDYUT_DB_URL` with the same values, save, then delete the `TERRA_*` ones. A new artifact bundle with migrated
pickles is published in Phase 16 (T16.1.x); until then the shim does the work.

#### T10.4.3 — Do NOT rename the GitHub repo or the Render service during the hackathon  📝
Both would change URLs that the Dockerfile, Vercel and judges' links depend on. If you rename the repo later,
GitHub redirects old URLs, but update `deploy/artifacts.lock` (Phase 16) and `VIDYUT_GITHUB_REPO` anyway.

#### T10.4.4 — Record the decision  📝
Append to `.agent/context/decisions.md`:
```markdown
## ADR-017 — Product renamed from TERRA to Vidyut (Phase 10)
- Package `vidyut`, CLI `vidyut`, env prefix `VIDYUT_` (old `TERRA_*` still accepted via `vidyut.compat`).
- External ids unchanged: repo AGNITIA-TERRA06, Render service terra-api, Kaggle slugs, release asset names before 2026-10-09.
- Old pickles load through `vidyut.compat.install_legacy_aliases`; `vidyut migrate-artifacts` re-saves them.
```

---

## PHASE 11 — Plant types: solar-only, wind-only, hybrid (Day 1–2)

Goal: one config switch (`plant.type`) decides which sources exist everywhere — forecast, alerts, dispatch,
schedule CSV, what-if, API and every page — and the operator's plant (capacities, location) is served by scaling
the reference models (decision B1).

Vocabulary used in code from now on:

| Name | Meaning | Values for solar / wind / hybrid plant |
|---|---|---|
| `cfg.sources` | generation sources at the plant | `["solar"]` / `["wind"]` / `["solar","wind"]` |
| `cfg.total_source` | the plant-total series (dispatch, DSM, demand alerts, schedules) | `"solar"` / `"wind"` / `"hybrid"` |
| `cfg.output_sources` | every series the API serves | `["solar"]` / `["wind"]` / `["solar","wind","hybrid"]` |
| reference config | what the artifacts were trained on (`reference_config()`) | normally the Dewas hybrid in `site.yaml` |
| plant config | what the operator has (`load_config()` = `site.yaml` + `plant.yaml`) | anything the wizard saved |

Data flow after this phase:
```
reference_config() ──► dataset + features + bundles (unchanged models)
                          │  q05..q95 in REFERENCE MW
                          ▼
plant_mapping(plant, ref).factors[s] = plant cap / ref cap ──► × factor ──► plant MW per source
                          ▼
hybrid copula only if plant.type == "hybrid"; plant total ──► alerts, dispatch, 15-min blocks, DSM schedule
run.json records: plant_type, sources, output_sources, total_source, mapping (factors, notes, approximate)
```

---

### 11.1 Two-layer configuration  ·  Owner: Dev A  ·  Depends on: Phase 10

Touches: `ml/vidyut/config.py` (whole file), `.gitignore`.

#### T11.1.1 — `ml/vidyut/config.py`  ✅ Tested
Adds `PlantCfg` (with `type`), `MarketCfg`, `RevisionCfg`, `NotificationsCfg` (the last three are used in
Phases 12–15 — adding them now avoids touching this file again), the `sources` / `total_source` /
`output_sources` / `has()` helpers, the `plant.yaml` deep-merge overlay, and `reference_config()` /
`write_reference_snapshot()`. Every new section has defaults, so the existing `site.yaml` needs no change.
**FILE: `ml/vidyut/config.py`** — ✅ Tested

````python
"""Typed configuration.

Two layers (Phase 11):
  config/site.yaml   REFERENCE plant: the plant the models were trained on (committed, never edited by the UI)
  config/plant.yaml  YOUR plant: written by the setup wizard (gitignored; in production it is also stored in
                     the database and re-written at API start-up). Deep-merged on top of site.yaml.

Usage:
    from vidyut.config import load_config, reference_config
    cfg = load_config()            # site.yaml + plant.yaml  -> the operator's plant
    ref = reference_config()       # what the trained artifacts were built for
    cfg.sources                    # ["solar"], ["wind"] or ["solar", "wind"]
    cfg.total_source               # "solar", "wind" or "hybrid": the plant total used by dispatch/DSM/alerts
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from vidyut.paths import ARTIFACTS, CONFIG_DIR

PlantType = Literal["solar", "wind", "hybrid"]
PLANT_FILE = CONFIG_DIR / "plant.yaml"
REFERENCE_SNAPSHOT = ARTIFACTS / "models" / "reference_config.yaml"   # written by `vidyut train`


class PlantCfg(BaseModel):
    """Who/what the plant is. `type` decides which sources exist everywhere in the product."""
    name: str = "Vidyut Dewas Hybrid (virtual plant)"
    type: PlantType = "hybrid"
    owner: str = ""
    qca_name: str = ""                 # Qualified Coordinating Agency that submits schedules to the SLDC
    district: str = "Dewas"


class MarketCfg(BaseModel):
    """Which deviation rules apply (Phase 12)."""
    state: str = "Madhya Pradesh"
    interstate: bool = False           # connected to the inter-state grid -> CERC rules
    rule_profile: str = "auto"         # "auto" = pick from state; else a file name in config/rules/
    contract_rate_inr_per_kwh: float = Field(2.70, gt=0, le=20)


class RevisionCfg(BaseModel):
    """Revision Advisor thresholds (Phase 14)."""
    min_saving_inr: float = Field(500.0, ge=0)        # do not bother the operator for less
    p_breach_trigger: float = Field(0.60, gt=0, lt=1)  # P(outside tolerance) that counts as a risk
    shift_trigger_pct: float = Field(5.0, gt=0)        # mean |P50 - schedule| as % of capacity
    expected_level: float = Field(0.5, gt=0, lt=1)     # fallback schedule quantile if none is tuned


class NotificationsCfg(BaseModel):
    """WhatsApp notification policy (Phase 17)."""
    enabled: bool = True
    min_severity: Literal["info", "warning", "critical"] = "warning"
    quiet_hours_ist: tuple[int, int] = (22, 6)          # no non-critical messages 22:00-06:00 IST
    send_revisions: bool = True
    send_daily_report: bool = True


class SiteCfg(BaseModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_m: float = 0.0
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def _tz_valid(cls, v: str) -> str:
        pd.Timestamp("2025-01-01", tz=v)  # raises if unknown
        return v


class SolarCfg(BaseModel):
    dc_capacity_mw: float = Field(gt=0)
    ac_capacity_mw: float = Field(gt=0)
    tilt_deg: float = Field(ge=0, le=90)
    azimuth_deg: float = Field(ge=0, lt=360)
    albedo: float = Field(default=0.2, ge=0, le=1)
    gamma_pdc: float = Field(default=-0.0037, lt=0)
    system_loss_frac: float = Field(default=0.14, ge=0, lt=1)
    eta_inv_nom: float = Field(default=0.96, gt=0, le=1)


class WindCfg(BaseModel):
    turbine_type: str
    n_turbines: int = Field(gt=0)
    rated_mw: float = Field(gt=0)
    hub_height_m: float = Field(gt=10)
    wake_loss_frac: float = Field(default=0.07, ge=0, lt=1)
    electrical_loss_frac: float = Field(default=0.02, ge=0, lt=1)
    cut_out_ms: float = 25.0

    @property
    def capacity_mw(self) -> float:
        return self.n_turbines * self.rated_mw


class BatteryCfg(BaseModel):
    power_mw: float = Field(ge=0)
    energy_mwh: float = Field(ge=0)
    round_trip_eff: float = Field(default=0.9, gt=0, le=1)
    soc_min_frac: float = Field(default=0.1, ge=0, le=1)
    soc_max_frac: float = Field(default=0.9, ge=0, le=1)
    soc_init_frac: float = Field(default=0.5, ge=0, le=1)
    degradation_inr_per_mwh: float = 300.0
    reserve_factor: float = 1.0

    @model_validator(mode="after")
    def _soc_order(self) -> "BatteryCfg":
        if not self.soc_min_frac <= self.soc_init_frac <= self.soc_max_frac:
            raise ValueError("require soc_min_frac <= soc_init_frac <= soc_max_frac")
        return self


class DemandCfg(BaseModel):
    peak_mw: float = Field(gt=0)
    temp_coeff_per_c: float = 0.01
    noise_std_frac: float = 0.02
    shape_source: Literal["parametric", "india_hourly"] = "parametric"


class SolarRealismCfg(BaseModel):
    ar1_phi: float = 0.7
    ar1_sigma: float = 0.06
    soiling_rate_per_day: float = 0.002
    soiling_reset_rain_mm: float = 5.0
    outage_rate_per_day: float = 0.02
    outage_mean_hours: float = 6.0
    outage_capacity_frac: float = 0.10


class WindRealismCfg(BaseModel):
    ar1_phi: float = 0.6
    ar1_sigma: float = 0.08
    outage_rate_per_day: float = 0.03
    outage_mean_hours: float = 12.0
    outage_capacity_frac: float = 0.12
    curtail_rate_per_day: float = 0.02
    curtail_mean_hours: float = 4.0
    curtail_level_frac: float = 0.6


class RealismCfg(BaseModel):
    seed: int = 42
    solar: SolarRealismCfg = SolarRealismCfg()
    wind: WindRealismCfg = WindRealismCfg()


class CostsCfg(BaseModel):
    backup_inr_per_mwh: float
    curtail_penalty_inr_per_mwh: float
    emission_factor_t_per_mwh: float
    emission_factor_source: str = ""


class AlertsCfg(BaseModel):
    low_quantile: float | dict[str, float] = 0.10
    high_quantile: float = 0.90
    ramp_quantile: float = 0.95
    quantile_basis: str = "train"
    low_generation_frac: float = 0.10
    high_generation_frac: float = 0.85
    ramp_mw_per_h: float = 20.0
    low_trust_score: float = 40
    min_probability: float = 0.6

    def get_low_quantile(self, source: str) -> float:
        if isinstance(self.low_quantile, dict):
            return float(self.low_quantile.get(source, 0.10))
        return float(self.low_quantile)


class WeatherCfg(BaseModel):
    forecast_model: Optional[str] = "ecmwf_ifs025"
    actual_model: Optional[str] = None
    start_date: str
    end_date: str


class SplitsCfg(BaseModel):
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str

    def bounds(self) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
        """UTC [start, end] (inclusive end-of-day) for each split."""
        def ts(d: str, end: bool) -> pd.Timestamp:
            t = pd.Timestamp(d, tz="UTC")
            return t + pd.Timedelta(hours=23) if end else t
        return {
            "train": (ts(self.train_start, False), ts(self.train_end, True)),
            "val": (ts(self.val_start, False), ts(self.val_end, True)),
            "test": (ts(self.test_start, False), ts(self.test_end, True)),
        }

    @model_validator(mode="after")
    def _ordered(self) -> "SplitsCfg":
        b = self.bounds()
        if not (b["train"][1] < b["val"][0] - pd.Timedelta(hours=47)
                and b["val"][1] < b["test"][0] - pd.Timedelta(hours=47)):
            raise ValueError("splits must be chronological with >= 48 h gaps")
        return self


class ForecastCfg(BaseModel):
    horizon_h: int = 48
    quantiles: list[float] = [0.05, 0.10, 0.50, 0.90, 0.95]
    train_issue_hours_utc: list[int] = [0, 6, 12, 18]
    dayahead_issue_hour_utc: int = 0


class VidyutConfig(BaseModel):
    plant: PlantCfg = PlantCfg()
    market: MarketCfg = MarketCfg()
    revision: RevisionCfg = RevisionCfg()
    notifications: NotificationsCfg = NotificationsCfg()
    site: SiteCfg
    solar: SolarCfg
    wind: WindCfg
    battery: BatteryCfg
    demand: DemandCfg
    realism: RealismCfg = RealismCfg()
    costs: CostsCfg
    alerts: AlertsCfg = AlertsCfg()
    weather: WeatherCfg
    splits: SplitsCfg
    forecast: ForecastCfg = ForecastCfg()

    @property
    def sources(self) -> list[str]:
        """Generation sources that exist at this plant, in a fixed order."""
        return {"solar": ["solar"], "wind": ["wind"], "hybrid": ["solar", "wind"]}[self.plant.type]

    @property
    def total_source(self) -> str:
        """Name of the plant-total series: 'hybrid' for a hybrid plant, else the single source."""
        return "hybrid" if self.plant.type == "hybrid" else self.sources[0]

    @property
    def output_sources(self) -> list[str]:
        """Every series the API serves for this plant (sources + 'hybrid' when there are two)."""
        return self.sources + (["hybrid"] if self.plant.type == "hybrid" else [])

    def has(self, source: str) -> bool:
        return source in self.output_sources

    def capacity_mw(self, source: str) -> float:
        if source == "solar":
            return self.solar.ac_capacity_mw
        if source == "wind":
            return self.wind.capacity_mw
        if source == "hybrid":
            return self.solar.ac_capacity_mw + self.wind.capacity_mw
        raise ValueError(f"unknown source {source!r}")

    def hash(self) -> str:
        """Stable short hash, stored in every artifact's meta.json."""
        blob = json.dumps(self.model_dump(), sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


def deep_merge(base: dict, over: dict) -> dict:
    """Recursively merge `over` into a copy of `base` (dicts merge, everything else replaces)."""
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(path: str | Path | None = None, with_plant: bool = True) -> VidyutConfig:
    """site.yaml (or `path`) + config/plant.yaml overlay when it exists and with_plant=True."""
    path = Path(path) if path else CONFIG_DIR / "site.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if with_plant and PLANT_FILE.exists():
        raw = deep_merge(raw, yaml.safe_load(PLANT_FILE.read_text(encoding="utf-8")) or {})
    return VidyutConfig.model_validate(raw)


def reference_config() -> VidyutConfig:
    """Configuration the current artifacts were trained with (snapshot written by `vidyut train`).
    Falls back to config/site.yaml for artifacts trained before the snapshot existed."""
    if REFERENCE_SNAPSHOT.exists():
        return VidyutConfig.model_validate(yaml.safe_load(REFERENCE_SNAPSHOT.read_text(encoding="utf-8")))
    return load_config(with_plant=False)


def write_reference_snapshot(cfg: VidyutConfig) -> Path:
    REFERENCE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_SNAPSHOT.write_text(yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
    return REFERENCE_SNAPSHOT


@lru_cache(maxsize=1)
def default_config() -> VidyutConfig:
    return load_config()


def load_yaml(name: str) -> dict:
    """Load any other YAML from config/ (e.g. 'calibration/solar.yaml'); rule profiles: vidyut.rules."""
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
````

#### T11.1.2 — Ignore the operator overlay  ✅ Tested
Append to `.gitignore` (the file holds a customer's plant data and is per-installation):
```gitignore
# Operator plant overlay written by the setup wizard (Phase 11/16)
config/plant.yaml
```
Check: `python -c "from vidyut.config import load_config as L; c=L(); print(c.plant.type, c.sources, c.total_source)"`
→ `hybrid ['solar', 'wind'] hybrid`.

---

### 11.2 Reference → plant mapping  ·  Owner: Dev A  ·  Depends on: 11.1

#### T11.2.1 — `ml/vidyut/plant.py`  ✅ Tested
Thresholds: closer than 25 km = same weather regime; > 150 km = "strongly recommend retraining". Solar notes for
DC/AC ratio (> 10 % different), tilt (> 5°) or azimuth (> 15°); wind notes for another turbine model or hub height
(> 5 m). A source the reference never trained (`missing`) blocks forecasting until a retrain.
**FILE: `ml/vidyut/plant.py`** — ✅ Tested

````python
"""Map forecasts made for the REFERENCE plant (what the models were trained on) to the OPERATOR's plant.

Why: retraining for every plant takes minutes to hours, but most changes (fewer turbines, a bigger solar
farm, a solar-only plant) are well approximated by scaling each source by its capacity ratio:

    plant_mw = reference_mw x (plant capacity / reference capacity)      (per source)

Things scaling cannot fix are reported in `notes` and set `approximate=True`, so the UI can say
"approximate — retrain for this plant" (Phase 16 offers the retrain button):
  * the plant is far from the reference site (local weather-error patterns differ)
  * different solar layout (DC/AC ratio, tilt, azimuth) or turbine model / hub height
A source the plant has but the reference models do not (e.g. a wind plant on solar-only artifacts) cannot
be scaled at all: it is listed in `missing` and forecasting refuses to run until a retrain.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from vidyut.config import VidyutConfig, load_config, reference_config

NEAR_KM = 25.0          # closer than this: same weather regime, no note
FAR_KM = 150.0          # further than this: strongly recommend retraining


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass
class PlantMapping:
    plant_type: str
    sources: list[str]
    total_source: str
    factors: dict[str, float]                 # per source: plant capacity / reference capacity
    distance_km: float
    approximate: bool
    notes: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing

    def to_dict(self) -> dict:
        return asdict(self)


def plant_mapping(plant: VidyutConfig | None = None, reference: VidyutConfig | None = None) -> PlantMapping:
    plant = plant or load_config()
    ref = reference or reference_config()
    notes: list[str] = []
    missing = [s for s in plant.sources if s not in ref.sources]
    factors = {s: plant.capacity_mw(s) / ref.capacity_mw(s) for s in plant.sources if s not in missing}

    d = haversine_km(plant.site.latitude, plant.site.longitude, ref.site.latitude, ref.site.longitude)
    if d > FAR_KM:
        notes.append(f"Plant is {d:.0f} km from the reference site — retraining for this location is strongly "
                     "recommended.")
    elif d > NEAR_KM:
        notes.append(f"Plant is {d:.0f} km from the reference site; local weather-error patterns may differ.")
    if "solar" in factors:
        ps, rs = plant.solar, ref.solar
        if abs(ps.dc_capacity_mw / ps.ac_capacity_mw - rs.dc_capacity_mw / rs.ac_capacity_mw) > 0.1 * (
                rs.dc_capacity_mw / rs.ac_capacity_mw):
            notes.append("Solar DC/AC ratio differs from the reference plant (midday clipping will differ).")
        if abs(ps.tilt_deg - rs.tilt_deg) > 5 or abs(ps.azimuth_deg - rs.azimuth_deg) > 15:
            notes.append("Solar tilt/azimuth differs from the reference plant (daily shape will differ).")
    if "wind" in factors:
        pw, rw = plant.wind, ref.wind
        if pw.turbine_type != rw.turbine_type or abs(pw.hub_height_m - rw.hub_height_m) > 5:
            notes.append(f"Turbine {pw.turbine_type} at {pw.hub_height_m:.0f} m differs from the reference "
                         f"{rw.turbine_type} at {rw.hub_height_m:.0f} m (power curve differs).")
    for s in missing:
        notes.append(f"The trained models have no {s} model — retrain before forecasting {s}.")
    return PlantMapping(plant_type=plant.plant.type, sources=plant.sources, total_source=plant.total_source,
                        factors={k: round(v, 6) for k, v in factors.items()}, distance_km=round(d, 1),
                        approximate=bool(notes), notes=notes, missing=missing)


def scale_thresholds(th: dict | None, factor: float) -> dict | None:
    """Alert thresholds learned in reference MW -> plant MW."""
    if not th:
        return th
    return {k: (v * factor if k.endswith(("_mw", "_mw_per_h")) else v) for k, v in th.items()}
````

#### T11.2.2 — Tests for plant types, overlay, mapping and the rename shim  ✅ Tested
**FILE: `ml/tests/test_plant.py`** — ✅ Tested

````python
"""Plant types, the plant.yaml overlay and reference->plant mapping (Phase 11) + rename compat (Phase 10)."""
import pytest
import yaml
from pydantic import ValidationError

from vidyut import config as C
from vidyut.compat import alias_legacy_env
from vidyut.plant import plant_mapping, scale_thresholds


@pytest.fixture
def plant_file(tmp_path, monkeypatch):
    f = tmp_path / "plant.yaml"
    monkeypatch.setattr(C, "PLANT_FILE", f)
    return f


def test_default_is_hybrid(plant_file):
    c = C.load_config()
    assert c.plant.type == "hybrid" and c.sources == ["solar", "wind"] and c.total_source == "hybrid"
    assert c.output_sources == ["solar", "wind", "hybrid"]


@pytest.mark.parametrize("kind,sources,total", [("solar", ["solar"], "solar"), ("wind", ["wind"], "wind")])
def test_single_source_plants(plant_file, kind, sources, total):
    plant_file.write_text(yaml.safe_dump({"plant": {"type": kind}}))
    c = C.load_config()
    assert c.sources == sources and c.total_source == total and c.output_sources == sources
    assert not c.has("hybrid")


def test_overlay_deep_merges(plant_file):
    plant_file.write_text(yaml.safe_dump({"solar": {"ac_capacity_mw": 20}}))
    c = C.load_config()
    ref = C.load_config(with_plant=False)
    assert c.solar.ac_capacity_mw == 20 and c.solar.tilt_deg == ref.solar.tilt_deg   # other keys kept


def test_bad_plant_type_rejected(plant_file):
    plant_file.write_text(yaml.safe_dump({"plant": {"type": "nuclear"}}))
    with pytest.raises(ValidationError):
        C.load_config()


def test_mapping_scales_and_flags():
    ref = C.load_config(with_plant=False)
    same = plant_mapping(ref, ref)
    assert same.factors == {"solar": 1.0, "wind": 1.0} and not same.approximate and same.ok
    p = ref.model_copy(update={"plant": ref.plant.model_copy(update={"type": "wind"}),
                               "wind": ref.wind.model_copy(update={"n_turbines": ref.wind.n_turbines // 2,
                                                                   "turbine_type": "E-82/2000"})})
    m = plant_mapping(p, ref)
    assert m.sources == ["wind"] and abs(m.factors["wind"] - 0.48) < 0.01
    assert m.approximate and any("Turbine" in n for n in m.notes)


def test_mapping_missing_source():
    ref = C.load_config(with_plant=False)
    solar_ref = ref.model_copy(update={"plant": ref.plant.model_copy(update={"type": "solar"})})
    m = plant_mapping(ref, solar_ref)                 # hybrid plant on solar-only artifacts
    assert not m.ok and m.missing == ["wind"]


def test_scale_thresholds():
    assert scale_thresholds({"low_mw": 2.0, "high_mw": 10.0, "ramp_mw_per_h": 4.0}, 0.5) == \
        {"low_mw": 1.0, "high_mw": 5.0, "ramp_mw_per_h": 2.0}


def test_legacy_env_alias():
    env = {"TERRA_MODE": "live", "VIDYUT_DB_URL": "x", "TERRA_DB_URL": "old"}
    alias_legacy_env(env)
    assert env["VIDYUT_MODE"] == "live" and env["VIDYUT_DB_URL"] == "x"   # never overrides a new variable
````

Check: `cd ml && pytest -q tests/test_plant.py` → `9 passed`.

---

### 11.3 Forecast pipeline per plant type  ·  Owner: Dev A  ·  Depends on: 11.2

Touches: `ml/vidyut/pipelines/forecast.py` (whole file). Two more changes ride along because the next phases need
them and this file is open anyway:
1. `blocks.parquet` — 15-minute q05..q95 for every output source over the whole 48 h horizon (the Revision Advisor
   and the simulator work on 15-min blocks).
2. The day-ahead `dsm_schedule.parquet` is clipped to **exactly the 96 blocks of the next IST day**. Before, it
   started at 23:45 IST of the previous day: IST is UTC+5:30, so hour-ending UTC timestamps straddle IST midnight.

#### T11.3.1 — `ml/vidyut/pipelines/forecast.py`  ✅ Tested
Key rules inside: models run on `reference_config()`; in **live** mode the weather and sun position come from the
plant's own coordinates (the plant's `site`), in **replay** mode from the reference history; trust features are
computed in reference units (they are capacity-normalised) before scaling; alert thresholds learned in reference MW
are scaled with `scale_thresholds`; demand is scaled by `plant.demand.peak_mw / ref.demand.peak_mw`; single-source
plants still get the supply-vs-demand alert on their total.
**FILE: `ml/vidyut/pipelines/forecast.py`** — ✅ Tested

````python
"""Produce one forecast run (live or replay) and write it to artifacts/runs/<issue>/.

live   : weather from the Open-Meteo Forecast API (past 10 days + next 3 days). The virtual plant's
         "measured" history = twin + realism on the latest-run weather for past hours (documented proxy).
replay : uses data/processed/dataset.parquet; targets after the virtual "now" are hidden.

Run directory contents (read by the backend):
  run.json             issue time, mode, models, attribution, created_at
  forecast.parquet     long: source(solar|wind|hybrid), target_time_utc, lead_h, q05..q95, trust_*, member q50s
  rows_solar.parquet, rows_wind.parquet   framed feature rows (used by what-if)
  alerts.json          list of alert dicts
  dispatch.parquet     strategy(advisor|rule|none) x hour schedule;  dispatch_kpis.json
  dsm_schedule.parquet next IST day, 96 blocks, schedule_mw per source (+ hybrid for hybrid plants)
  blocks.parquet       15-min q05..q95 per output source over the whole horizon (Revision Advisor, Phase 14)

Plant types (Phase 11): models run on the REFERENCE plant (reference_config()), then every source the
operator's plant has is scaled to the plant's capacity (vidyut.plant). Sources the plant does not have are
not forecast at all; "hybrid" exists only for hybrid plants. run.json records the mapping.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from vidyut.config import VidyutConfig, load_config, reference_config
from vidyut.data.build_dataset import build_dataset, load_dataset
from vidyut.data.openmeteo import ATTRIBUTION, OpenMeteoClient
from vidyut.data.weather_tables import add_derived
from vidyut.engines.alerts import generate_alerts
from vidyut.engines.dispatch import no_battery, plan, rule_based
from vidyut.engines.dsm import schedule_at_level
from vidyut.engines.hybrid import hybrid_forecast
from vidyut.engines.trust import hybrid_trust_score, level, trust_features
from vidyut.features.framing import frame_source
from vidyut.logs import get_logger
from vidyut.models.downscale import downscale_solar, downscale_wind
from vidyut.models.registry import load_object
from vidyut.paths import ARTIFACTS
from vidyut.plant import plant_mapping, scale_thresholds
from vidyut.schema import FORECAST_VARS, QCOLS

log = get_logger(__name__)
RUNS = ARTIFACTS / "runs"


def live_dataset(cfg: VidyutConfig, client: OpenMeteoClient | None = None) -> tuple[pd.DataFrame, pd.Timestamp]:
    client = client or OpenMeteoClient()
    fx = client.fetch_live_forecast(cfg.site.latitude, cfg.site.longitude, FORECAST_VARS,
                                    model=cfg.weather.forecast_model, past_days=10, forecast_days=3)
    fx = fx.interpolate(limit=3)
    for p in ("fx0_", "fx1_", "fx2_"):
        fx = add_derived(fx, p)
    act = fx[[c for c in fx.columns if c.startswith("fx0_")]].rename(columns=lambda c: "act_" + c[4:])
    act["gap_flag"] = False
    ds = build_dataset(cfg, act, fx, save=False)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    ds.loc[ds.index > now, ["solar_mw", "wind_mw"]] = np.nan
    return ds, now


def replay_dataset(cfg: VidyutConfig, at: str | None) -> tuple[pd.DataFrame, pd.Timestamp]:
    ds = load_dataset().copy()
    t0 = pd.Timestamp(at, tz="UTC") if at else cfg.splits.bounds()["test"][0] + pd.Timedelta(days=7)
    t0 = t0.floor("h")
    ds.loc[ds.index > t0, ["solar_mw", "wind_mw"]] = np.nan          # hide the future
    return ds, t0


def downscale(hourly: pd.Series, source: str, cfg: VidyutConfig) -> pd.Series:
    """Hourly MW -> 15-min block MW (energy-preserving), solar shaped by clear-sky, wind interpolated."""
    cap = cfg.capacity_mw(source)
    return downscale_solar(hourly, cfg.site, cap) if source == "solar" else downscale_wind(hourly, cap)


def quantile_blocks(per_output: dict[str, pd.DataFrame], cfg: VidyutConfig) -> pd.DataFrame:
    """15-min q05..q95 for every output source over the full horizon (quantiles kept monotone)."""
    out = []
    for s, df in per_output.items():
        idx = pd.DatetimeIndex(df["target_time_utc"])
        src = "solar" if s == "solar" else "wind"            # hybrid/wind: smooth interpolation
        cols = {}
        for c in QCOLS:
            h = pd.Series(df[c].to_numpy(), index=idx)
            cols[c] = (downscale_solar(h, cfg.site, cfg.capacity_mw(s)) if src == "solar"
                       else downscale_wind(h, cfg.capacity_mw(s)))
        b = pd.DataFrame(cols)
        b[list(QCOLS)] = np.sort(b[list(QCOLS)].to_numpy(), axis=1)
        out.append(b.rename_axis("block_end_utc").reset_index().assign(source=s))
    return pd.concat(out, ignore_index=True)


def run_forecast(cfg: VidyutConfig | None = None, mode: str = "replay", at: str | None = None) -> Path:
    """cfg = the operator's plant (default load_config()). Models always run on reference_config()."""
    plant = cfg or load_config()
    ref = reference_config()
    mp = plant_mapping(plant, ref)
    if not mp.ok:
        raise RuntimeError("; ".join(mp.notes) + " (run the setup retrain)")
    # live: real weather + solar geometry at the plant's own coordinates; replay: the reference history
    model_cfg = ref if mode == "replay" else ref.model_copy(update={"site": plant.site})
    ds, t0 = live_dataset(model_cfg) if mode == "live" else replay_dataset(model_cfg, at)
    issues = pd.DatetimeIndex([t0])
    eng = load_object("hybrid", "engines@latest")
    alert_thrs = eng.get("alert_thresholds") if isinstance(eng, dict) else None
    out = RUNS / t0.strftime("%Y%m%dT%H")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("rows_*.parquet"):                   # a previous run of another plant type
        old.unlink()

    per_source: dict[str, pd.DataFrame] = {}
    all_alerts = []
    for s in plant.sources:
        bundle = load_object(s, "bundle@latest")
        rows = frame_source(ds, s, model_cfg, issues, require_target=False)
        external = {}
        if any(m.startswith("chronos2") for m in bundle.ensemble.members):
            from vidyut.models.chronos2 import Chronos2Forecaster  # optional heavy dependency
            ckpt = {"chronos2_zs": "amazon/chronos-2",
                    "chronos2_ft": str(ARTIFACTS / "chronos" / "chronos2_ft" / "finetuned-ckpt")}   # [verify] folder
            external = {m: Chronos2Forecaster(model_id=ckpt[m]).predict_issues(ds, s, issues, bundle.capacity_mw)
                        for m in bundle.ensemble.members if m.startswith("chronos2")}
        q, members, spread = bundle.predict(rows, external)
        ref_cap = bundle.capacity_mw
        absres = (ds[f"{s}_mw"] - ds[f"phys0_{s}_mw"]).abs().rolling(168, min_periods=1).mean()
        recent = float(absres.loc[:t0].iloc[-1]) / ref_cap
        feats = trust_features(q, spread, rows["lead_h"].to_numpy(), np.full(len(q), recent), ref_cap)  # unitless
        tm = eng["trust"][s]
        f = mp.factors[s]                                     # reference MW -> plant MW
        df = pd.DataFrame({"target_time_utc": rows["target_time_utc"], "lead_h": rows["lead_h"],
                           "cal_is_day": rows["cal_is_day"]})
        df[list(QCOLS)] = q.to_numpy() * f
        df["trust_score"] = tm.score(feats)
        df["trust_level"] = [level(x) for x in df["trust_score"]]
        df["trust_reason"] = tm.explain(feats)
        for m, mq in members.items():
            df[f"{m}_q50"] = mq["q50"].to_numpy() * f
        df["source"] = s
        per_source[s] = df
        rows.to_parquet(out / f"rows_{s}.parquet")
        fc = df.set_index("target_time_utc")
        th_s = scale_thresholds(alert_thrs.get(s), f) if alert_thrs else None
        all_alerts += generate_alerts(fc, s, plant.capacity_mw(s), plant.alerts, t0, trust=fc["trust_score"],
                                      thresholds=th_s)

    total = plant.total_source
    if plant.plant.type == "hybrid":
        sol, win = per_source["solar"], per_source["wind"]
        hyb_q = hybrid_forecast(sol[list(QCOLS)], win[list(QCOLS)], sol["cal_is_day"].to_numpy(),
                                eng["rho_by_day"], plant.capacity_mw("solar"), plant.capacity_mw("wind"))
        tot = sol[["target_time_utc", "lead_h", "cal_is_day"]].copy()
        tot[list(QCOLS)] = hyb_q.to_numpy()
        tot["trust_score"] = hybrid_trust_score(sol["q50"].to_numpy(), win["q50"].to_numpy(),
                                                sol["trust_score"].to_numpy(), win["trust_score"].to_numpy())
        tot["trust_level"] = [level(x) for x in tot["trust_score"]]
        tot["trust_reason"] = np.where(sol["trust_score"] <= win["trust_score"], sol["trust_reason"],
                                       win["trust_reason"])
        tot["source"] = "hybrid"
        per_output = {**per_source, "hybrid": tot}
        hyb_factor = plant.capacity_mw("hybrid") / ref.capacity_mw("hybrid")
        th_tot = scale_thresholds(alert_thrs.get("hybrid"), hyb_factor) if alert_thrs else None
    else:
        tot = per_source[total]
        per_output = dict(per_source)
        th_tot = None                                         # single source: its own thresholds already used
    demand_scale = plant.demand.peak_mw / ref.demand.peak_mw
    demand = ds["demand_mw"].reindex(tot["target_time_utc"]) * demand_scale
    fc = tot.set_index("target_time_utc")
    if plant.plant.type == "hybrid":
        all_alerts += generate_alerts(fc, "hybrid", plant.capacity_mw("hybrid"), plant.alerts, t0,
                                      demand=pd.Series(demand.to_numpy(), index=fc.index), thresholds=th_tot)
    else:                                                     # supply-vs-demand check on the plant total
        all_alerts += [a for a in generate_alerts(fc, total, plant.capacity_mw(total), plant.alerts, t0,
                                                  demand=pd.Series(demand.to_numpy(), index=fc.index),
                                                  thresholds=scale_thresholds(alert_thrs.get(total), mp.factors[total])
                                                  if alert_thrs else None)
                       if a.type == "DEFICIT_VS_DEMAND"]
    forecast = pd.concat(list(per_output.values()), ignore_index=True)
    forecast.to_parquet(out / "forecast.parquet")

    # dispatch (advisor vs rule vs none) on the plant-total P50
    idx = pd.DatetimeIndex(tot["target_time_utc"])
    g50, g10, dem = tot["q50"].to_numpy(), tot["q10"].to_numpy(), demand.to_numpy()
    strategies = {"advisor": plan(g50, dem, plant.battery, plant.costs, g10, index=idx),
                  "rule": rule_based(g50, dem, plant.battery, plant.costs, index=idx),
                  "none": no_battery(g50, dem, plant.costs, index=idx)}
    disp = pd.concat([r.schedule.assign(strategy=k) for k, r in strategies.items()]).rename_axis("target_time_utc")
    disp.reset_index().to_parquet(out / "dispatch.parquet")
    (out / "dispatch_kpis.json").write_text(json.dumps({k: r.kpis for k, r in strategies.items()}, indent=2))

    # 15-min quantile blocks for the whole horizon (Revision Advisor + simulator)
    quantile_blocks(per_output, plant).to_parquet(out / "blocks.parquet")

    # day-ahead DSM schedule for the next IST day
    ist_next = (t0.tz_convert("Asia/Kolkata").normalize() + pd.Timedelta(days=1))
    lo, hi = ist_next.tz_convert("UTC"), (ist_next + pd.Timedelta(days=1)).tz_convert("UTC")
    sched = {}
    for s, df in per_source.items():
        # hours overlapping the IST day (IST is UTC+5:30, so the first/last hour straddle midnight)
        d = df[(df["target_time_utc"] > lo) & (df["target_time_utc"] <= hi + pd.Timedelta(hours=1))]
        if len(d) < 24:
            continue
        lvl = eng.get("dsm_level", {}).get(s, 0.5)
        hourly = pd.Series(schedule_at_level(d[list(QCOLS)].to_numpy(), lvl), index=pd.DatetimeIndex(d["target_time_utc"]))
        blk = downscale(hourly, s, plant)
        blk = blk[(blk.index > lo) & (blk.index <= hi)]          # exactly the 96 blocks of the next IST day
        if len(blk) == 96:
            sched[s] = blk
    if sched:
        sdf = pd.DataFrame(sched)
        if plant.plant.type == "hybrid":
            sdf["hybrid"] = sdf.sum(axis=1)
        sdf.rename_axis("block_end_utc").reset_index().to_parquet(out / "dsm_schedule.parquet")

    (out / "alerts.json").write_text(json.dumps([a.to_dict() for a in all_alerts], indent=2))
    meta = {"issue_time_utc": t0.isoformat(), "mode": mode, "created_at": datetime.now(timezone.utc).isoformat(),
            "attribution": ATTRIBUTION, "plant": plant.plant.name, "plant_type": plant.plant.type,
            "sources": plant.sources, "output_sources": plant.output_sources, "total_source": total,
            "mapping": mp.to_dict(), "config_hash": plant.hash(), "reference_hash": ref.hash(),
            "n_alerts": len(all_alerts)}
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    (RUNS / "LATEST").write_text(out.name)
    log.info("forecast run written: %s (%s plant, %d alerts)", out, plant.plant.type, len(all_alerts))
    return out
````

#### T11.3.2 — Try all three plant types  📝
Needs `data/processed/dataset.parquet` (replay). Save as `scratch/plant_types_check.py` and run it:
```python
import json, yaml, pandas as pd
from vidyut.config import PLANT_FILE, load_config
from vidyut.pipelines.forecast import run_forecast
cases = {"hybrid": None,
         "solar": {"plant": {"type": "solar", "name": "Solar only"}, "solar": {"ac_capacity_mw": 20, "dc_capacity_mw": 25}},
         "wind": {"plant": {"type": "wind", "name": "Wind only"}, "wind": {"n_turbines": 10},
                  "site": {"latitude": 23.3, "longitude": 75.9, "name": "x"}}}
for k, over in cases.items():
    if over: PLANT_FILE.write_text(yaml.safe_dump(over))
    elif PLANT_FILE.exists(): PLANT_FILE.unlink()
    out = run_forecast(load_config(), "replay", "2026-04-12T00:00")
    meta = json.loads((out / "run.json").read_text())
    f = pd.read_parquet(out / "forecast.parquet"); s = pd.read_parquet(out / "dsm_schedule.parquet")
    print(k, meta["output_sources"], meta["mapping"]["factors"], meta["mapping"]["notes"][:1], len(s), list(s.columns))
if PLANT_FILE.exists(): PLANT_FILE.unlink()
```
Expected (numbers from the reference run):
```
hybrid ['solar', 'wind', 'hybrid'] {'solar': 1.0, 'wind': 1.0} [] 96 ['block_end_utc', 'solar', 'wind', 'hybrid']
solar ['solar'] {'solar': 0.5} [] 96 ['block_end_utc', 'solar']
wind ['wind'] {'wind': 0.4} ['Plant is 41 km from the reference site; ...'] 96 ['block_end_utc', 'wind']
```
Finally run `vidyut forecast --mode replay` once more (no `plant.yaml`) so `artifacts/runs/LATEST` is a hybrid run
again for the API tests.

---

### 11.4 What-if per plant type  ·  Owner: Dev A  ·  Depends on: 11.3

#### T11.4.1 — `ml/vidyut/engines/whatif.py`  ✅ Tested
`run_whatif(cfg=REFERENCE, …, plant=PLANT)`: simulates only the plant's sources, keeps the physics feature at
reference capacity (what the model learned) and scales the result to the scenario capacity; the hybrid copula is
used only for hybrid plants. The response key stays `"hybrid"` (the plant total) so the API schema is unchanged.
**FILE: `ml/vidyut/engines/whatif.py`** — ✅ Tested

````python
"""H4 What-if engine: perturb the latest run's forecast weather / plant and re-forecast + re-dispatch.

Uses physics + LightGBM members only (Chronos-2 is too slow for interactive use; documented).
Capacity changes: physics is recomputed with the new capacity; GBM output is scaled by new/old capacity
(an approximation, documented in the UI).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from vidyut.config import VidyutConfig
from vidyut.data.solar_twin import simulate_solar
from vidyut.data.wind_twin import simulate_wind
from vidyut.engines.dispatch import plan
from vidyut.engines.hybrid import hybrid_forecast
from vidyut.schema import QCOLS


class Scenario(BaseModel):
    irradiance_scale: float = Field(1.0, ge=0.2, le=1.3)     # 0.5 = much cloudier than forecast
    wind_scale: float = Field(1.0, ge=0.5, le=1.5)
    solar_ac_mw: float | None = Field(None, gt=0, le=500)
    wind_turbines: int | None = Field(None, gt=0, le=250)
    battery_mw: float | None = Field(None, ge=0, le=500)
    battery_mwh: float | None = Field(None, ge=0, le=2000)


def _apply(rows: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    r = rows.copy()
    for c in ("fx_ghi", "fx_dni", "fx_dhi"):
        r[c] = r[c] * sc.irradiance_scale
    if "fx_csi" in r:
        r["fx_csi"] = (r["fx_csi"] * sc.irradiance_scale).clip(0, 1.5)
    for c in ("fx_ws10", "fx_ws100"):
        r[c] = r[c] * sc.wind_scale
    r["fx_ws100_cubed"] = r["fx_ws100"] ** 3
    return r


def _predict(bundle, rows: pd.DataFrame, scale: float) -> pd.DataFrame:
    members = [m for m in bundle.ensemble.members if m in bundle.models]
    X = rows[bundle.features + ["lead_bucket"]]
    preds = {m: bundle.models[m].predict(X) for m in members}
    preds["gbm"] = preds["gbm"] * scale if "gbm" in preds else preds.get("gbm")
    out = np.zeros((len(rows), len(QCOLS)))
    buckets = rows["lead_bucket"].astype(str).to_numpy()
    for b, w in bundle.ensemble.weights.items():
        idx = [bundle.ensemble.members.index(m) for m in members]
        ww = np.asarray(w)[idx]
        ww = ww / ww.sum()
        sel = buckets == b
        out[sel] = sum(wi * preds[m][list(QCOLS)].to_numpy()[sel] for wi, m in zip(ww, members))
    q = pd.DataFrame(np.sort(out, axis=1), columns=list(QCOLS), index=rows.index)
    return bundle.cqr.apply(q, rows, bundle.capacity_mw * scale, zero_at_night=bundle.source == "solar")


def run_whatif(cfg: VidyutConfig, rows: dict[str, pd.DataFrame], bundles: dict, engines: dict,
               demand: np.ndarray, sc: Scenario, plant: VidyutConfig | None = None) -> dict:
    """cfg = REFERENCE config (what the bundles were trained on); plant = operator's plant (default cfg).

    Only the plant's sources are simulated; results are in plant MW. Scenario capacities are plant values.
    """
    plant = plant or cfg
    sol_new = sc.solar_ac_mw or plant.solar.ac_capacity_mw
    new_solar = cfg.solar.model_copy(update={"ac_capacity_mw": sol_new,
                                             "dc_capacity_mw": sol_new * plant.solar.dc_capacity_mw
                                             / plant.solar.ac_capacity_mw})
    new_wind = cfg.wind.model_copy(update={"n_turbines": sc.wind_turbines or plant.wind.n_turbines})
    new_bat = plant.battery.model_copy(update={
        "power_mw": plant.battery.power_mw if sc.battery_mw is None else sc.battery_mw,
        "energy_mwh": plant.battery.energy_mwh if sc.battery_mwh is None else sc.battery_mwh})
    cur_solar = cfg.solar.model_copy(update={"ac_capacity_mw": plant.solar.ac_capacity_mw,
                                             "dc_capacity_mw": plant.solar.dc_capacity_mw})
    cur_wind = cfg.wind.model_copy(update={"n_turbines": plant.wind.n_turbines})
    first = rows[plant.sources[0]]
    result = {}
    for label, (scn, sol_cfg, wind_cfg, bat) in {
        "before": (Scenario(), cur_solar, cur_wind, plant.battery),
        "after": (sc, new_solar, new_wind, new_bat),
    }.items():
        q = {}
        for s in plant.sources:
            r = _apply(rows[s], scn)
            wx = r.set_index(pd.DatetimeIndex(r["target_time_utc"]))
            # physics feature stays at REFERENCE capacity (what the models learned); output is scaled
            phys = simulate_solar(wx, cfg.site, cfg.solar, "fx_") if s == "solar" else simulate_wind(wx, cfg.wind, "fx_")
            r["phys_mw"] = phys.to_numpy()
            old = cfg.capacity_mw(s)
            new = sol_cfg.ac_capacity_mw if s == "solar" else wind_cfg.capacity_mw
            q[s] = _predict(bundles[s], r, 1.0)
            q[s] = q[s] * (new / old)
        if plant.plant.type == "hybrid":
            tot = hybrid_forecast(q["solar"], q["wind"], first["cal_is_day"].to_numpy(), engines["rho_by_day"],
                                  sol_cfg.ac_capacity_mw, wind_cfg.capacity_mw)
        else:
            tot = q[plant.sources[0]]
        disp = plan(tot["q50"].to_numpy(), demand, bat, plant.costs, tot["q10"].to_numpy())
        result[label] = {
            "hybrid": tot.assign(target_time_utc=first["target_time_utc"].to_numpy()),   # key kept for the API
            "energy_mwh_p50": float(tot["q50"].sum()),
            "kpis": disp.kpis,
        }
    return result
````

---

### 11.5 Backend: serve only the plant's series  ·  Owner: Dev A  ·  Depends on: 11.3

Touches: `backend/app/services/{plant,runs,whatif}.py`, `backend/app/api/routes/{health,forecast,impact,dsm}.py`,
`backend/app/schemas/api.py`.

#### T11.5.1 — `backend/app/services/plant.py`  ✅ Tested
The **latest run** decides which series exist (`run.json → output_sources`), so a page never asks for a series the
current run does not contain, even right after a plant change.
**FILE: `backend/app/services/plant.py`** — ✅ Tested

````python
"""Which sources this plant has, and guards for routes that take a `source` parameter (Phase 11)."""
from __future__ import annotations

from fastapi import HTTPException
from vidyut.config import load_config
from vidyut.plant import plant_mapping

from app.services import runs


def served_sources() -> list[str]:
    """Output sources present in the latest run (falls back to the plant config before the first run)."""
    try:
        return list(runs.latest()["meta"].get("output_sources", ["solar", "wind", "hybrid"]))
    except runs.NoRunYet:
        return load_config().output_sources


def resolve_source(source: str | None) -> str:
    """None -> the plant total ('hybrid' or the single source). Unknown for this plant -> HTTP 404."""
    cfg = load_config()
    s = source or cfg.total_source
    if s not in served_sources():
        raise HTTPException(404, f"this plant ({cfg.plant.type}) has no '{s}' series; available: "
                                 f"{', '.join(served_sources())}")
    return s


def mapping() -> dict:
    return plant_mapping().to_dict()
````

#### T11.5.2 — `backend/app/schemas/api.py`  ✅ Tested
New `SiteInfo` fields (plant type, sources, mapping) and three optional `DsmSummary` fields used in Phase 12.
**FILE: `backend/app/schemas/api.py`** — ✅ Tested

````python
"""Response/request models. The frontend's TypeScript types are generated from these (make types)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Source = Literal["solar", "wind", "hybrid"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorBody


class Health(BaseModel):
    status: str
    version: str
    mode: str
    latest_run: str | None = None
    latest_issue_time_utc: str | None = None


class SiteInfo(BaseModel):
    name: str
    plant_type: Literal["solar", "wind", "hybrid"] = "hybrid"
    sources: list[str] = ["solar", "wind"]
    output_sources: list[str] = ["solar", "wind", "hybrid"]
    total_source: str = "hybrid"
    approximate: bool = False                 # forecasts are scaled from a different reference plant
    mapping_notes: list[str] = []
    distance_km: float = 0.0
    latitude: float
    longitude: float
    timezone: str
    solar_ac_mw: float
    wind_mw: float
    battery_mw: float
    battery_mwh: float
    attribution: str
    plant_note: str


class ForecastPoint(BaseModel):
    target_time_utc: str
    lead_h: int
    q05: float
    q10: float
    q50: float
    q90: float
    q95: float
    trust_score: float
    trust_level: str
    trust_reason: str


class ForecastResponse(BaseModel):
    source: Source
    issue_time_utc: str
    mode: str
    capacity_mw: float
    points: list[ForecastPoint]


class HistoryPoint(BaseModel):
    target_time_utc: str
    actual_mw: float
    q10: float
    q50: float
    q90: float


class HistoryResponse(BaseModel):
    source: Literal["solar", "wind"]
    model: str
    lead_h_max: int
    points: list[HistoryPoint]


class ModelRow(BaseModel):
    model: str
    mae: float
    rmse: float
    nmae_pct: float
    nrmse_pct: float
    bias: float
    picp80: float
    picp90: float
    mpiw80_pct: float
    skill_vs_persistence: float | None = None
    lead_bucket: str | None = None


class ModelsResponse(BaseModel):
    source: Literal["solar", "wind"]
    split: str
    rows: list[ModelRow]
    daylight_only: bool = False


class AlertOut(BaseModel):
    id: str
    type: str
    source: str
    start_utc: str
    end_utc: str
    severity: Literal["info", "warning", "critical"]
    probability: float
    magnitude_mw: float
    message: str
    issue_time_utc: str
    acknowledged: bool = False


class DispatchPoint(BaseModel):
    target_time_utc: str
    gen_mw: float
    demand_mw: float
    charge_mw: float
    discharge_mw: float
    soc_mwh: float
    backup_mw: float
    curtail_mw: float


class Kpis(BaseModel):
    backup_mwh: float
    curtail_mwh: float
    cost_inr: float
    co2_t: float
    battery_throughput_mwh: float


class DispatchResponse(BaseModel):
    strategy: Literal["advisor", "rule", "none"]
    points: list[DispatchPoint]
    kpis: dict[str, Kpis]


class WhatIfRequest(BaseModel):
    irradiance_scale: float = 1.0
    wind_scale: float = 1.0
    solar_ac_mw: float | None = None
    wind_turbines: int | None = None
    battery_mw: float | None = None
    battery_mwh: float | None = None


class WhatIfSide(BaseModel):
    energy_mwh_p50: float
    kpis: Kpis
    points: list[dict]


class WhatIfResponse(BaseModel):
    before: WhatIfSide
    after: WhatIfSide


class DsmRow(BaseModel):
    source: str
    strategy: str
    charge_inr: float
    blocks_outside_tolerance_pct: float


class DsmSummary(BaseModel):
    illustrative_rates: bool
    chosen_level: dict[str, float]
    rows: list[DsmRow]
    profile: dict = {}                         # rule profile summary (Phase 12)
    profile_reason: str = ""
    contract_rate_inr_per_kwh: float = 0.0


class ImpactResponse(BaseModel):
    impact: dict
    value_of_forecast: list[dict]
    hybrid: dict
    sources: list[str]
````

#### T11.5.3 — `backend/app/api/routes/health.py`  ✅ Tested
**FILE: `backend/app/api/routes/health.py`** — ✅ Tested

````python
from __future__ import annotations

from fastapi import APIRouter
from vidyut.config import load_config
from vidyut.data.openmeteo import ATTRIBUTION

from app.db import models as db
from app.schemas.api import Health, SiteInfo
from app.services import plant, runs
from app.settings import get_settings

router = APIRouter(tags=["meta"])


@router.api_route("/health", methods=["GET", "HEAD"], response_model=Health)
def health() -> Health:
    """Liveness/readiness probe. Accepts HEAD too: uptime pingers (UptimeRobot) often probe with HEAD."""
    s = get_settings()
    try:
        r = runs.latest()
        return Health(status="ok", version=s.version, mode=s.mode, latest_run=r["name"],
                      latest_issue_time_utc=r["meta"]["issue_time_utc"])
    except runs.NoRunYet:
        return Health(status="no_run_yet", version=s.version, mode=s.mode)


@router.api_route("/health/deep", methods=["GET", "HEAD"])
def health_deep() -> dict:
    """Keep-warm probe: like /health but also makes one tiny query against the database (wakes a suspended
    Neon compute). Always HTTP 200 so a pinger does not page on a slow wake-up; read the `db` field."""
    h = health()
    return {**h.model_dump(), **db.ping()}


@router.get("/site", response_model=SiteInfo)
def site() -> SiteInfo:
    c = load_config()
    m = plant.mapping()
    return SiteInfo(name=c.plant.name, plant_type=c.plant.type, sources=c.sources, output_sources=c.output_sources,
                    total_source=c.total_source, approximate=m["approximate"], mapping_notes=m["notes"],
                    distance_km=m["distance_km"], latitude=c.site.latitude, longitude=c.site.longitude, timezone=c.site.timezone,
                    solar_ac_mw=c.solar.ac_capacity_mw if "solar" in c.sources else 0.0,
                    wind_mw=c.wind.capacity_mw if "wind" in c.sources else 0.0, battery_mw=c.battery.power_mw,
                    battery_mwh=c.battery.energy_mwh, attribution=ATTRIBUTION,
                    plant_note="Virtual digital-twin plant at a real location, calibrated on real data.")
````

#### T11.5.4 — `backend/app/api/routes/forecast.py`  ✅ Tested
`source` is now optional; missing = plant total.
**FILE: `backend/app/api/routes/forecast.py`** — ✅ Tested

````python
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from vidyut.config import load_config

from app.schemas.api import ForecastPoint, ForecastResponse, HistoryPoint, HistoryResponse
from app.services import runs
from app.services.plant import resolve_source

router = APIRouter(tags=["forecast"])


def _iso(s):
    return s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/forecast", response_model=ForecastResponse)
def forecast(source: Literal["solar", "wind", "hybrid"] | None = None,
             horizon: int = Query(48, ge=1, le=48)) -> ForecastResponse:
    """source omitted = the plant total ('hybrid' for hybrid plants, else the plant's only source)."""
    source = resolve_source(source)
    r = runs.latest()
    f = r["forecast"]
    f = f[(f["source"] == source) & (f["lead_h"] <= horizon)].sort_values("lead_h").copy()
    f["target_time_utc"] = _iso(f["target_time_utc"])
    cols = ["target_time_utc", "lead_h", "q05", "q10", "q50", "q90", "q95", "trust_score", "trust_level", "trust_reason"]
    pts = [ForecastPoint(**row) for row in f[cols].to_dict(orient="records")]
    return ForecastResponse(source=source, issue_time_utc=r["meta"]["issue_time_utc"], mode=r["meta"]["mode"],
                            capacity_mw=load_config().capacity_mw(source), points=pts)


@router.get("/forecast/history", response_model=HistoryResponse)
def history(source: Literal["solar", "wind"] = "solar", model: str = "ensemble",
            start: str | None = None, end: str | None = None, lead_h_max: int = Query(24, ge=1, le=48)
            ) -> HistoryResponse:
    """Actual vs predicted on the held-out test period (day-ahead issues at 00 UTC)."""
    p = runs.backtest(source)
    p = p[(p["model"] == model) & (p["split"] == "test") & (p["issue_time_utc"].dt.hour == 0)
          & (p["lead_h"] <= lead_h_max)].sort_values("target_time_utc")
    if start:
        p = p[p["target_time_utc"] >= start]
    if end:
        p = p[p["target_time_utc"] <= end]
    if not start and not end:
        p = p.head(24 * 14)
    p = p.assign(target_time_utc=_iso(p["target_time_utc"]), actual_mw=p["y"])
    pts = [HistoryPoint(**r) for r in p[["target_time_utc", "actual_mw", "q10", "q50", "q90"]].to_dict(orient="records")]
    return HistoryResponse(source=source, model=model, lead_h_max=lead_h_max, points=pts)
````

#### T11.5.5 — `backend/app/services/runs.py`  ✅ Tested
Reads `rows_*.parquet` for whatever sources the run has; `compare_models` uses `reference_config()` (backtests
were made on the reference plant); adds `load(name)` and `blocks(name)` for Phase 13.
**FILE: `backend/app/services/runs.py`** — ✅ Tested

````python
"""Read-only access to forecast runs, backtests and evaluation artifacts written by the ML package."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
from vidyut.config import reference_config
from vidyut.eval.metrics import metrics_table
from vidyut.paths import ARTIFACTS, DOCS

RUNS = ARTIFACTS / "runs"


class NoRunYet(FileNotFoundError):
    pass


def latest_name() -> str:
    p = RUNS / "LATEST"
    if not p.exists():
        raise NoRunYet("no forecast run yet - run `vidyut forecast` or wait for the scheduler")
    return p.read_text().strip()


@lru_cache(maxsize=16)
def _load(name: str) -> dict:
    d = RUNS / name
    out = {"name": name, "meta": json.loads((d / "run.json").read_text()),
           "forecast": pd.read_parquet(d / "forecast.parquet"),
           "alerts": json.loads((d / "alerts.json").read_text()),
           "dispatch": pd.read_parquet(d / "dispatch.parquet"),
           "dispatch_kpis": json.loads((d / "dispatch_kpis.json").read_text()),
           "rows": {p.stem[len("rows_"):]: pd.read_parquet(p) for p in sorted(d.glob("rows_*.parquet"))}}
    p = d / "dsm_schedule.parquet"
    out["dsm_schedule"] = pd.read_parquet(p) if p.exists() else None
    return out


def latest() -> dict:
    return _load(latest_name())


def load(name: str) -> dict:
    """One run by folder name (cached)."""
    if not (RUNS / name / "run.json").exists():
        raise NoRunYet(f"run {name} not found")
    return _load(name)


@lru_cache(maxsize=16)
def blocks(name: str) -> pd.DataFrame:
    """15-min quantile blocks of a run (blocks.parquet, written since Phase 11)."""
    p = RUNS / name / "blocks.parquet"
    if not p.exists():
        raise NoRunYet(f"run {name} has no 15-min blocks — produce a new run with `vidyut forecast`")
    return pd.read_parquet(p)


@lru_cache(maxsize=2)
def backtest(source: str) -> pd.DataFrame:
    p = ARTIFACTS / "backtests" / source / "predictions.parquet"
    if not p.exists():
        raise NoRunYet(f"no backtest for {source} - run `vidyut train`")
    return pd.read_parquet(p)


@lru_cache(maxsize=1)
def evaluation() -> dict:
    p = ARTIFACTS / "evaluation" / "results.json"
    if not p.exists():
        raise NoRunYet("no evaluation yet - run `vidyut evaluate`")
    return json.loads(p.read_text())


@lru_cache(maxsize=16)
def compare_models(source: str, split: str = "test", by: str | None = None, daylight: bool = False) -> pd.DataFrame:
    cfg = reference_config()                       # backtests were made on the reference plant
    p = backtest(source)
    p = p[p["split"] == split]
    is_daylight = daylight and source == "solar"
    return metrics_table(p, cfg.capacity_mw(source), by=[by] if by else None, daylight_only=is_daylight)


def read_doc(name: str) -> str:
    p = DOCS / name
    return p.read_text(encoding="utf-8") if p.exists() else f"_{name} not generated yet_"


def clear_cache() -> None:
    _load.cache_clear()
    blocks.cache_clear()
    backtest.cache_clear()
    evaluation.cache_clear()
    compare_models.cache_clear()


def run_dir(name: str) -> Path:
    return RUNS / name
````

#### T11.5.6 — `backend/app/services/whatif.py`  ✅ Tested
**FILE: `backend/app/services/whatif.py`** — ✅ Tested

````python
"""What-if service: loads models once, caches results per (run, scenario)."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np
from vidyut.config import load_config, reference_config
from vidyut.data.build_dataset import load_dataset
from vidyut.engines.whatif import Scenario, run_whatif
from vidyut.models.registry import load_object

from app.services import runs

_cache: dict[str, dict] = {}


@lru_cache(maxsize=1)
def _models() -> tuple[dict, dict]:
    bundles = {s: load_object(s, "bundle@latest") for s in reference_config().sources}
    return bundles, load_object("hybrid", "engines@latest")


def whatif(sc: Scenario) -> dict:
    run = runs.latest()
    key = run["name"] + load_config().hash() + hashlib.sha256(json.dumps(sc.model_dump(), sort_keys=True).encode()).hexdigest()[:16]
    if key in _cache:
        return _cache[key]
    cfg, ref = load_config(), reference_config()
    bundles, engines = _models()
    rows = run["rows"]
    targets = rows[cfg.sources[0]]["target_time_utc"]
    try:
        demand = load_dataset()["demand_mw"].reindex(targets).to_numpy() * cfg.demand.peak_mw / ref.demand.peak_mw
    except FileNotFoundError:
        demand = np.full(len(targets), cfg.demand.peak_mw * 0.8)
    res = run_whatif(ref, rows, bundles, engines, np.nan_to_num(demand, nan=cfg.demand.peak_mw * 0.8), sc, plant=cfg)
    if len(_cache) > 256:
        _cache.clear()
    _cache[key] = res
    return res
````

#### T11.5.7 — Two one-line route fixes  ✅ Tested
1. `backend/app/api/routes/impact.py`: replace `hybrid=e["hybrid"],` with `hybrid=e.get("hybrid", {}),`
   (single-source evaluations have no hybrid section).
2. `backend/app/api/routes/dsm.py`, function `schedule`: change the signature and first line to
   ```python
   def schedule(source: Literal["solar", "wind", "hybrid"] | None = None) -> Response:
       source = resolve_source(source)
   ```
   and add `from app.services.plant import resolve_source` to the imports. (Phase 13 replaces this whole file.)

Check:
```bash
cd backend && VIDYUT_SCHEDULER_ENABLED=false pytest -q          # 26 passed
printf 'plant:\n  type: solar\n' > ../config/plant.yaml && (cd .. && vidyut forecast --mode replay)
uvicorn app.main:app --port 8000 &  sleep 5
curl -s localhost:8000/site | python -m json.tool | head -12            # plant_type "solar", output_sources ["solar"]
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/forecast?source=wind"   # 404
kill %1; rm ../config/plant.yaml; (cd .. && vidyut forecast --mode replay)
```

---

### 11.6 Frontend: pages follow the plant type  ·  Owner: Dev B  ·  Depends on: 11.5

Touches: `hooks/api.ts`, `app/page.tsx`, `app/forecast/page.tsx`, `app/models/page.tsx`, `app/trust/page.tsx`,
`app/whatif/page.tsx`; new `hooks/plant.ts`, `components/ui/SourceToggle.tsx`.

#### T11.6.1 — Regenerate API types  📝
```bash
make types          # writes frontend/src/lib/api/schema.d.ts; commit it (Vercel builds from git)
```
Check: `grep -c plant_type frontend/src/lib/api/schema.d.ts` → at least `1`.

#### T11.6.2 — `frontend/src/hooks/plant.ts`  ✅ Tested
**FILE: `frontend/src/hooks/plant.ts`** — ✅ Tested

````typescript
"use client";
/** What kind of plant this is (Phase 11). Every page uses this instead of assuming solar + wind. */
import { useSite } from "@/hooks/api";
import type { Source } from "@/lib/api/types";

export type PlantType = "solar" | "wind" | "hybrid";

export type Plant = {
  ready: boolean;                 // false until /site has answered (render skeletons, not hybrid guesses)
  name: string;
  type: PlantType;
  sources: ("solar" | "wind")[];  // generation sources at this plant
  outputs: Source[];              // series the API serves: sources (+ "hybrid" for hybrid plants)
  total: Source;                  // plant total: "hybrid" or the single source
  totalLabel: string;             // "Solar + wind" | "Solar" | "Wind"
  approximate: boolean;           // forecasts scaled from a different reference plant
  notes: string[];
};

const LABEL: Record<PlantType, string> = { hybrid: "Solar + wind", solar: "Solar", wind: "Wind" };

export function usePlant(): Plant {
  const site = useSite();
  const d = site.data;
  const type = (d?.plant_type ?? "hybrid") as PlantType;
  return {
    ready: Boolean(d),
    name: d?.name ?? "",
    type,
    sources: (d?.sources ?? ["solar", "wind"]) as ("solar" | "wind")[],
    outputs: (d?.output_sources ?? ["solar", "wind", "hybrid"]) as Source[],
    total: (d?.total_source ?? "hybrid") as Source,
    totalLabel: LABEL[type],
    approximate: d?.approximate ?? false,
    notes: d?.mapping_notes ?? [],
  };
}

export const SOURCE_LABEL: Record<Source, string> = { solar: "Solar", wind: "Wind", hybrid: "Plant total" };
````

#### T11.6.3 — `frontend/src/components/ui/SourceToggle.tsx`  ✅ Tested
**FILE: `frontend/src/components/ui/SourceToggle.tsx`** — ✅ Tested

````tsx
"use client";
/** Source picker that only offers the sources this plant has. Renders nothing for single-source plants. */
import { SOURCE_LABEL, usePlant } from "@/hooks/plant";
import type { Source } from "@/lib/api/types";
import { Segmented } from "./primitives";

export default function SourceToggle<T extends Source>({ value, onChange, include = "sources" }: {
  value: T;
  onChange: (v: T) => void;
  include?: "sources" | "outputs";      // "outputs" adds the plant total for hybrid plants
}) {
  const plant = usePlant();
  const list = (include === "outputs" ? plant.outputs : plant.sources) as T[];
  if (list.length < 2) return null;
  return <Segmented label="Source" value={value} onChange={onChange}
    options={list.map((s) => ({ value: s, label: SOURCE_LABEL[s] }))} />;
}
````

#### T11.6.4 — `frontend/src/hooks/api.ts`  ✅ Tested
`useForecast(source, horizon, enabled)` — `enabled=false` skips requests for series the plant lacks. Also listens
to the `workflow` SSE event that Phase 13 emits (harmless before that).
**FILE: `frontend/src/hooks/api.ts`** — ✅ Tested

````typescript
"use client";
/** One hook per endpoint. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, API_BASE, ApiError } from "@/lib/api/client";
import type {
  AlertOut, DispatchResponse, DsmSummary, ForecastResponse, Health, HistoryResponse, ImpactResponse,
  ModelsResponse, SiteInfo, Source, WhatIfRequest, WhatIfResponse,
} from "@/lib/api/types";

/**
 * TanStack Query retry policy for waking up cold backend instances (e.g. Render free tier).
 * - Up to 12 retries for network errors and HTTP 502/503/504
 * - Explicitly skips 4xx client errors and 503 NO_DATA_YET (which is a valid state)
 * - Exponential backoff capped at 8 seconds
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 12) return false;
  if (error instanceof ApiError) {
    if (error.status >= 400 && error.status < 500) return false;
    if (error.status === 503 && error.code === "NO_DATA_YET") return false;
    if ([502, 503, 504].includes(error.status)) return true;
    return false;
  }
  // Network errors (Failed to fetch, server offline, DNS failure, etc.)
  return true;
}

export function retryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 8000);
}

export const RETRY_CONFIG = {
  retry: shouldRetry,
  retryDelay,
};

const LIVE = { refetchInterval: 60_000, ...RETRY_CONFIG };

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), ...LIVE });
export const useSite = () => useQuery({ queryKey: ["site"], queryFn: () => api<SiteInfo>("/site"), ...RETRY_CONFIG });
/** `enabled=false` skips the request (e.g. wind on a solar-only plant — the API would answer 404). */
export const useForecast = (source: Source, horizon = 48, enabled = true) =>
  useQuery({ queryKey: ["forecast", source, horizon], enabled, queryFn: () => api<ForecastResponse>(`/forecast?source=${source}&horizon=${horizon}`), ...LIVE });
export const useHistory = (source: "solar" | "wind", model = "ensemble") =>
  useQuery({ queryKey: ["history", source, model], queryFn: () => api<HistoryResponse>(`/forecast/history?source=${source}&model=${model}`), ...RETRY_CONFIG });
export const useModels = (source: "solar" | "wind", by?: "lead_bucket") =>
  useQuery({ queryKey: ["models", source, by], queryFn: () => api<ModelsResponse>(`/models/compare?source=${source}${by ? `&by=${by}` : ""}`), ...RETRY_CONFIG });
export const useAlerts = () => useQuery({ queryKey: ["alerts"], queryFn: () => api<AlertOut[]>("/alerts"), ...LIVE });
export const useDispatch = (strategy: "advisor" | "rule" | "none" = "advisor") =>
  useQuery({ queryKey: ["dispatch", strategy], queryFn: () => api<DispatchResponse>(`/dispatch?strategy=${strategy}`), ...LIVE });
export const useDsm = () => useQuery({ queryKey: ["dsm"], queryFn: () => api<DsmSummary>("/dsm/summary"), ...RETRY_CONFIG });
export const useImpact = () => useQuery({ queryKey: ["impact"], queryFn: () => api<ImpactResponse>("/impact"), ...RETRY_CONFIG });
export const useAssumptions = () =>
  useQuery({ queryKey: ["assumptions"], queryFn: () => api<Record<string, string>>("/assumptions"), ...RETRY_CONFIG });
export const useTrustSummary = () =>
  useQuery({ queryKey: ["trust-summary"], queryFn: () => api<Record<string, { spearman_score_vs_abs_error: number; mae_by_level: Record<string, number> } | null>>("/trust"), ...RETRY_CONFIG });
export const useWhatIf = () =>
  useMutation({ mutationFn: (body: WhatIfRequest) => api<WhatIfResponse>("/whatif", { method: "POST", body: JSON.stringify(body) }) });
export const ackAlert = (id: string) => api<{ ok: boolean }>(`/alerts/${encodeURIComponent(id)}/ack`, { method: "POST" });

/** Subscribe to Server-Sent Events; refresh cached data when a new run completes. */
export function useLiveUpdates(onAlert?: (a: AlertOut) => void) {
  const qc = useQueryClient();
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/alerts/stream`);
    es.addEventListener("run_complete", () => qc.invalidateQueries());
    es.addEventListener("alert", (e) => onAlert?.(JSON.parse((e as MessageEvent).data)));
    es.addEventListener("workflow", () => {   // Phase 14: a new recommendation / schedule may exist
      for (const k of ["recommendations", "schedule-today", "events"]) qc.invalidateQueries({ queryKey: [k] });
    });
    return () => es.close();
  }, [qc, onAlert]);
}
````

#### T11.6.5 — Control Room `frontend/src/app/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Control Room (H1): plant-total forecast with band, per-source P50s (hybrid plants), demand, trust strip,
 *  next alerts, KPIs. Works for solar-only, wind-only and hybrid plants (Phase 11). */
import { useMemo } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Badge, Card, CardTitle, Kpi } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAlerts, useDispatch, useForecast } from "@/hooks/api";
import { usePlant } from "@/hooks/plant";
import { cssVar, mw, mwh, toIST } from "@/lib/format";

export default function ControlRoom() {
  const plant = usePlant();
  const isHybrid = plant.type === "hybrid";
  const hybrid = useForecast(plant.total, 48, plant.ready);          // the plant total
  const solar = useForecast("solar", 48, plant.ready && isHybrid);   // per-source lines only for hybrids
  const wind = useForecast("wind", 48, plant.ready && isHybrid);
  const dispatch = useDispatch("advisor");
  const alerts = useAlerts();

  const option = useMemo(() => {
    if (!hybrid.data || (isHybrid && (!solar.data || !wind.data))) return null;
    const pts = hybrid.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    const demand = dispatch.data?.points.map((p) => [p.target_time_utc, p.demand_mw]) ?? [];
    return {
      ...timeAxisOption("MW"),
      series: [
        ...bandSeries(plant.totalLabel, pts, cssVar(isHybrid ? "--hybrid" : `--${plant.total}`), "hyb"),
        ...(isHybrid && solar.data && wind.data ? [
          { name: "Solar P50", type: "line", data: solar.data.points.map((p) => [p.target_time_utc, p.q50]),
            lineStyle: { color: cssVar("--solar"), type: "dashed" }, itemStyle: { color: cssVar("--solar") }, symbol: "none" },
          { name: "Wind P50", type: "line", data: wind.data.points.map((p) => [p.target_time_utc, p.q50]),
            lineStyle: { color: cssVar("--wind"), type: "dashed" }, itemStyle: { color: cssVar("--wind") }, symbol: "none" },
        ] : []),
        { name: "Demand", type: "line", data: demand, lineStyle: { color: cssVar("--demand"), width: 1.5 },
          itemStyle: { color: cssVar("--demand") }, symbol: "none" },
      ],
    } as const;
  }, [hybrid.data, solar.data, wind.data, dispatch.data, isHybrid, plant.total, plant.totalLabel]);

  const h = hybrid.data?.points ?? [];
  const hasData = Boolean(hybrid.data && h.length > 0);
  const energy = hasData ? h.reduce((s, p) => s + p.q50, 0) : null;
  const minP = hasData ? Math.min(...h.map((p) => p.q10)) : null;
  const maxP = hasData ? Math.max(...h.map((p) => p.q90)) : null;
  const avgTrust = hasData ? h.reduce((s, p) => s + p.trust_score, 0) / h.length : null;
  const upcoming = (alerts.data ?? []).filter((a) => !a.acknowledged).slice(0, 4);

  const forecastQueries = isHybrid ? [hybrid, solar, wind, dispatch] : [hybrid, dispatch];
  const retryingForecast = forecastQueries.filter((q) => q.failureCount > 0 && !q.isError);
  const isForecastRetrying = retryingForecast.length > 0;
  const forecastAttempt = isForecastRetrying ? Math.max(...retryingForecast.map((q) => q.failureCount)) : 1;

  const isAlertsRetrying = alerts.failureCount > 0 && !alerts.isError;

  const isForecastLoading = !plant.ready || forecastQueries.some((q) => q.isLoading);
  const forecastError = forecastQueries.map((q) => q.error).find(Boolean);
  const refetchForecast = () => Promise.all(forecastQueries.map((q) => q.refetch()));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Control Room</h1>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Next 48 h energy (P50)" value={energy !== null ? mwh(energy) : "—"} />
        <Kpi label="Lowest likely (P10)" value={minP !== null ? mw(minP) : "—"} />
        <Kpi label="Highest likely (P90)" value={maxP !== null ? mw(maxP) : "—"} />
        <Kpi label="Average trust" value={avgTrust !== null ? `${avgTrust.toFixed(0)} / 100` : "—"} />
        <Kpi label="Backup needed (plan)" value={dispatch.data ? mwh(dispatch.data.kpis.advisor.backup_mwh) : "—"} />
      </div>
      <Card>
        <CardTitle>{isHybrid ? "Combined solar + wind" : plant.totalLabel} forecast with 80% band</CardTitle>
        <QueryState
          isLoading={isForecastLoading}
          error={forecastError}
          refetch={refetchForecast}
          isRetrying={isForecastRetrying}
          retryCount={forecastAttempt}
        >
          {option && <EChart option={option} height={360} ariaLabel={`${plant.totalLabel} forecast for the next 48 hours with P10–P90 band and demand`} />}
          <div className="mt-3"><TrustRibbon points={h} /></div>
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Next alerts</CardTitle>
        <QueryState
          isLoading={alerts.isLoading}
          error={alerts.error}
          refetch={alerts.refetch}
          empty={!upcoming.length}
          height="h-16"
          isRetrying={isAlertsRetrying}
          retryCount={alerts.failureCount}
        >
          <ul className="divide-y divide-border">
            {upcoming.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <Badge tone={a.severity === "critical" ? "bad" : a.severity === "warning" ? "warn" : "neutral"}>{a.severity}</Badge>
                <span className="font-medium">{a.message}</span>
                <span className="text-muted">{toIST(a.start_utc)} → {toIST(a.end_utc)}</span>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
    </div>
  );
}
````

#### T11.6.6 — Forecast Explorer `frontend/src/app/forecast/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/forecast/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Forecast Explorer: actual vs predicted on held-out days + the next 48 h for one source/model. */
import { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import SourceToggle from "@/components/ui/SourceToggle";
import { QueryState } from "@/components/ui/states";
import { useForecast, useHistory } from "@/hooks/api";
import { usePlant } from "@/hooks/plant";
import { cssVar } from "@/lib/format";

type Src = "solar" | "wind";
const MODELS = ["ensemble", "gbm", "physics", "persistence", "chronos2_zs"] as const;
type ModelKey = (typeof MODELS)[number];

const MODEL_LABELS: Record<ModelKey, string> = {
  ensemble: "Ensemble",
  gbm: "LightGBM",
  physics: "Physics",
  persistence: "Persistence",
  chronos2_zs: "Chronos-2 (Zero-shot)",
};

export default function ForecastPage() {
  const plant = usePlant();
  const [picked, setSource] = useState<Src | null>(null);
  const source: Src = picked && plant.sources.includes(picked) ? picked : plant.sources[0];
  const [model, setModel] = useState<ModelKey>("ensemble");
  const hist = useHistory(source, model);
  const fc = useForecast(source);
  const color = cssVar(source === "solar" ? "--solar" : "--wind");

  const histOption = useMemo(() => {
    if (!hist.data) return null;
    const pts = hist.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    return {
      ...timeAxisOption("MW"),
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 4 }],
      series: [...bandSeries("Forecast", pts, color, "h"),
        { name: "Actual", type: "line", data: hist.data.points.map((p) => [p.target_time_utc, p.actual_mw]),
          lineStyle: { color: cssVar("--text"), width: 1.2 }, itemStyle: { color: cssVar("--text") }, symbol: "none" }],
    };
  }, [hist.data, color]);

  const fcOption = useMemo(() => {
    if (!fc.data) return null;
    const pts = fc.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    return { ...timeAxisOption("MW"), series: bandSeries("Next 48 h", pts, color, "f") };
  }, [fc.data, color]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Forecast Explorer</h1>
        <SourceToggle value={source} onChange={setSource} />
        <Segmented label="Model" value={model} onChange={setModel} options={MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))} />
      </div>
      <Card>
        <CardTitle>Actual vs predicted — held-out test days (day-ahead, issued 05:30 IST)</CardTitle>
        <QueryState isLoading={hist.isLoading} error={hist.error} refetch={hist.refetch} empty={!hist.data?.points.length}>
          {histOption && <EChart option={histOption} height={340} ariaLabel={`Actual versus ${model} forecast for ${source}`} />}
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Next 48 hours (calibrated ensemble)</CardTitle>
        <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch}>
          {fcOption && <EChart option={fcOption} height={300} ariaLabel={`${source} forecast next 48 hours`} />}
          {fc.data && <div className="mt-3"><TrustRibbon points={fc.data.points} /></div>}
        </QueryState>
      </Card>
    </div>
  );
}
````

#### T11.6.7 — Models & Accuracy `frontend/src/app/models/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/models/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Models & Accuracy: baseline vs ML comparison (MAE, RMSE, skill, band coverage) + error by lead time. */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import EChart from "@/components/charts/EChart";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAssumptions } from "@/hooks/api";
import { usePlant } from "@/hooks/plant";
import { api } from "@/lib/api/client";
import type { ModelsResponse } from "@/lib/api/types";
import { cssVar } from "@/lib/format";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Src = "solar" | "wind" | "real";

function useModelsCompare(source: "solar" | "wind", by?: "lead_bucket", daylight?: boolean) {
  return useQuery({
    queryKey: ["models", source, by, daylight],
    queryFn: () =>
      api<ModelsResponse>(
        `/models/compare?source=${source}${by ? `&by=${by}` : ""}${daylight ? "&daylight=true" : ""}`
      ),
  });
}

export default function ModelsPage() {
  const plant = usePlant();
  const [picked, setSource] = useState<Src | null>(null);
  const source: Src = picked === "real" || (picked && plant.sources.includes(picked)) ? picked : plant.sources[0];
  const [daylightFilter, setDaylightFilter] = useState<"all" | "daylight">("daylight");
  const isSolar = source === "solar";
  const daylight = isSolar && daylightFilter === "daylight";
  const effectiveSource = source === "real" ? "solar" : source;
  const overall = useModelsCompare(effectiveSource, undefined, daylight);
  const byLead = useModelsCompare(effectiveSource, "lead_bucket", daylight);
  const best = overall.data?.rows
    .filter((r) => r.model !== "persistence" && !r.model.startsWith("chronos2"))
    .sort((a, b) => a.mae - b.mae)[0]?.model;
  const assumptions = useAssumptions();

  const option = useMemo(() => {
    if (!byLead.data || source === "real") return null;
    const rawBuckets = [...new Set(byLead.data.rows.map((r) => r.lead_bucket).filter((b): b is string => Boolean(b)))];
    const parseFirstLead = (b: string) => {
      const m = b.match(/^(\d+)/);
      return m ? parseInt(m[1], 10) : Number.POSITIVE_INFINITY;
    };
    const buckets = rawBuckets.sort((a, b) => parseFirstLead(a) - parseFirstLead(b));
    const models = [...new Set(byLead.data.rows.map((r) => r.model))];
    const palette = [cssVar("--hybrid"), cssVar("--solar"), cssVar("--wind"), cssVar("--demand"), cssVar("--battery"), cssVar("--backup")];
    return {
      grid: { left: 48, right: 16, top: 32, bottom: 32 },
      tooltip: { trigger: "axis" },
      legend: { top: 0, type: "scroll" },
      xAxis: { type: "category", data: buckets, name: "lead (h)" },
      yAxis: { type: "value", name: "nMAE %" },
      series: models.map((m, i) => ({
        name: m, type: "bar",
        data: buckets.map((b) => byLead.data!.rows.find((r) => r.model === m && r.lead_bucket === b)?.nmae_pct ?? null),
        itemStyle: { color: palette[i % palette.length] },
      })),
    };
  }, [byLead.data, source]);

  const viewLabel = source === "solar"
    ? ((overall.data ? overall.data.daylight_only : daylightFilter === "daylight") ? "Daylight only" : "All hours")
    : "All hours";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Models & Accuracy</h1>
        {source === "solar" && (
          <Segmented
            label="Daylight filter"
            value={daylightFilter}
            onChange={setDaylightFilter}
            options={[
              { value: "all", label: "All hours" },
              { value: "daylight", label: "Daylight only" },
            ]}
          />
        )}
        <Segmented label="Source" value={source} onChange={setSource}
          options={[...plant.sources.map((s) => ({ value: s as Src, label: s === "solar" ? "Solar" : "Wind" })),
            { value: "real" as Src, label: "Real data" }]} />
      </div>

      {source === "real" ? (
        <Card>
          <CardTitle>Results on real generation data</CardTitle>
          <QueryState isLoading={assumptions.isLoading} error={assumptions.error} refetch={assumptions.refetch}>
             <div className="prose-sm max-w-none space-y-2 text-sm [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:px-2 [&_th]:border [&_th]:border-border [&_th]:px-2">
               <ReactMarkdown
                 remarkPlugins={[remarkGfm]}
                 components={{
                   table: ({ children, ...props }) => (
                     <div className="w-full overflow-x-auto my-2">
                       <table {...props}>{children}</table>
                     </div>
                   ),
                 }}
               >
                 {assumptions.data?.real_data_results_md ?? ""}
               </ReactMarkdown>
             </div>
          </QueryState>
        </Card>
      ) : (
        <>
          <Card>
            <CardTitle>Test-period comparison — {viewLabel} (lower error is better; band coverage should be near 80% / 90%)</CardTitle>
            <QueryState isLoading={overall.isLoading} error={overall.error} refetch={overall.refetch}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular-nums">
                  <thead className="text-left text-muted">
                    <tr>{["Model", "MAE MW", "RMSE MW", "nMAE %", "Skill vs persistence", "80% band coverage", "90% band coverage", "Band width %"].map((h) => <th key={h} className="px-2 py-1 font-medium">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {overall.data?.rows.map((r) => {
                      const isBenchmark = r.model.startsWith("chronos2");
                      const isBest = r.model === best;
                      return (
                        <tr key={r.model} className={isBest ? "bg-hybrid/10 font-semibold" : ""}>
                          <td className="px-2 py-1">
                            {r.model}
                            {isBest && " ★"}
                            {isBenchmark && (
                              <span className="ml-1.5 rounded bg-muted/20 px-1 py-0.5 text-xs text-muted font-normal">
                                benchmark
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-1">{r.mae.toFixed(2)}</td>
                          <td className="px-2 py-1">{r.rmse.toFixed(2)}</td>
                          <td className="px-2 py-1">{r.nmae_pct.toFixed(2)}</td>
                          <td className="px-2 py-1">{r.skill_vs_persistence == null ? "—" : `${(100 * r.skill_vs_persistence).toFixed(0)}%`}</td>
                          <td className="px-2 py-1">{(100 * r.picp80).toFixed(1)}%</td>
                          <td className="px-2 py-1">{(100 * r.picp90).toFixed(1)}%</td>
                          <td className="px-2 py-1">{r.mpiw80_pct.toFixed(1)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted">Coverage target: 80% / 90%. All-hours solar coverage is inflated by night hours (output is zero).</p>
            </QueryState>
          </Card>
          <Card>
            <CardTitle>Error by lead time</CardTitle>
            <QueryState isLoading={byLead.isLoading} error={byLead.error}>
              {option && <EChart option={option} height={300} ariaLabel="Normalised MAE by lead-time bucket for each model" />}
            </QueryState>
          </Card>
        </>
      )}
    </div>
  );
}
````

#### T11.6.8 — Trust `frontend/src/app/trust/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/trust/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Trust Layer (H3): evidence that the trust score tracks real error + the per-hour ribbon. */
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useTrustSummary } from "@/hooks/api";
import { usePlant } from "@/hooks/plant";
import { toIST } from "@/lib/format";

export default function TrustPage() {
  const summary = useTrustSummary();
  const plant = usePlant();
  const fc = useForecast(plant.total, 48, plant.ready);
  const lowHours = fc.data?.points.filter((p) => p.trust_score < 40) ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Forecast Trust</h1>
      <Card>
        <CardTitle>Next 48 hours</CardTitle>
        <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch} height="h-12">
          {fc.data && <TrustRibbon points={fc.data.points} />}
          <ul className="mt-3 space-y-1 text-sm">
            {lowHours.slice(0, 6).map((p) => <li key={p.target_time_utc}>{toIST(p.target_time_utc)} — trust {p.trust_score}: {p.trust_reason}</li>)}
          </ul>
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Does the score mean anything? (test period)</CardTitle>
        <QueryState isLoading={summary.isLoading} error={summary.error} refetch={summary.refetch} height="h-24">
          <div className="grid gap-4 md:grid-cols-2">
            {plant.sources.map((s) => {
              const t = summary.data?.[s];
              if (!t) return null;
              return (
                <div key={s} className="text-sm">
                  <div className="font-semibold capitalize">{s}</div>
                  <p>Rank correlation between trust score and actual error: <b>{t.spearman_score_vs_abs_error.toFixed(2)}</b> (negative = higher trust, lower error).</p>
                  <p className="mt-1">Average error by trust level: {Object.entries(t.mae_by_level).map(([k, v]) => `${k} ${v.toFixed(2)} MW`).join(" · ")}</p>
                </div>
              );
            })}
          </div>
        </QueryState>
      </Card>
    </div>
  );
}
````

#### T11.6.9 — What-if `frontend/src/app/whatif/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/whatif/page.tsx`** — ✅ Tested

````tsx
"use client";
/** What-if Simulator (H4): sliders -> POST /whatif (debounced) -> before/after chart and KPIs. */
import { useEffect, useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import { Button, Card, CardTitle, Kpi, RangeInput } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useSite, useWhatIf } from "@/hooks/api";
import { usePlant } from "@/hooks/plant";
import type { WhatIfRequest } from "@/lib/api/types";
import { cssVar, inr, mwh } from "@/lib/format";

const PRESETS: Record<string, Partial<WhatIfRequest>> = {
  "Monsoon cloudy day": { irradiance_scale: 0.45, wind_scale: 1.2 },
  "Low-wind heatwave": { irradiance_scale: 1.05, wind_scale: 0.6 },
  "Double the battery": { battery_mw: 50, battery_mwh: 100 },
};

export default function WhatIfPage() {
  const site = useSite();
  const plant = usePlant();
  const m = useWhatIf();
  const [sc, setSc] = useState<WhatIfRequest>({ irradiance_scale: 1, wind_scale: 1 });
  const { mutate } = m;
  useEffect(() => {
    const t = setTimeout(() => mutate(sc), 400);
    return () => clearTimeout(t);
  }, [sc, mutate]);

  const option = useMemo(() => {
    if (!m.data) return null;
    const conv = (pts: Record<string, unknown>[]) =>
      pts.map((p) => ({ t: String(p.target_time_utc), lo: Number(p.q10), mid: Number(p.q50), hi: Number(p.q90) }));
    return { ...timeAxisOption("MW"),
      series: [...bandSeries("Before", conv(m.data.before.points), cssVar("--demand"), "b"),
               ...bandSeries("After", conv(m.data.after.points), cssVar("--hybrid"), "a")] };
  }, [m.data]);

  const set = (patch: Partial<WhatIfRequest>) => setSc((s) => ({ ...s, ...patch }));
  const b = m.data?.before, a = m.data?.after;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">What-if Simulator</h1>
      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        <Card className="space-y-4">
          <CardTitle>Scenario</CardTitle>
          {plant.sources.includes("solar") && <RangeInput label="Sunlight vs forecast" value={sc.irradiance_scale ?? 1} min={0.2} max={1.3} step={0.05}
            onChange={(v) => set({ irradiance_scale: v })} format={(v) => `${Math.round(v * 100)}%`} />}
          {plant.sources.includes("wind") && <RangeInput label="Wind vs forecast" value={sc.wind_scale ?? 1} min={0.5} max={1.5} step={0.05}
            onChange={(v) => set({ wind_scale: v })} format={(v) => `${Math.round(v * 100)}%`} />}
          <RangeInput label="Battery energy" value={sc.battery_mwh ?? site.data?.battery_mwh ?? 50} min={0} max={200} step={10}
            onChange={(v) => set({ battery_mwh: v })} format={(v) => `${v} MWh`} />
          <RangeInput label="Battery power" value={sc.battery_mw ?? site.data?.battery_mw ?? 25} min={0} max={100} step={5}
            onChange={(v) => set({ battery_mw: v })} format={(v) => `${v} MW`} />
          <div className="flex flex-wrap gap-2">
            {Object.entries(PRESETS).map(([k, v]) => <Button key={k} onClick={() => setSc({ irradiance_scale: 1, wind_scale: 1, ...v })}>{k}</Button>)}
            <Button onClick={() => setSc({ irradiance_scale: 1, wind_scale: 1 })}>Reset</Button>
          </div>
          <p className="text-xs text-muted">Uses physics + LightGBM members (Chronos-2 is skipped for speed). Capacity changes scale the ML output.</p>
        </Card>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Kpi label="Energy 48 h (before → after)" value={b && a ? `${mwh(b.energy_mwh_p50)} → ${mwh(a.energy_mwh_p50)}` : "—"} />
            <Kpi label="Backup (before → after)" value={b && a ? `${mwh(b.kpis.backup_mwh)} → ${mwh(a.kpis.backup_mwh)}` : "—"} />
            <Kpi label="Cost after" value={a ? inr(a.kpis.cost_inr) : "—"} />
            <Kpi label="CO₂ after" value={a ? `${a.kpis.co2_t.toFixed(0)} t` : "—"} />
          </div>
          <Card>
            <CardTitle>{plant.totalLabel} forecast — before vs after</CardTitle>
            <QueryState isLoading={m.isPending && !m.data} error={m.error}>
              {option && <EChart option={option} height={340} ariaLabel="Hybrid forecast before and after the scenario" />}
            </QueryState>
          </Card>
        </div>
      </div>
    </div>
  );
}
````

Check: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` all pass. With `config/plant.yaml`
containing `plant: {type: solar}` and a fresh replay run, the Control Room title reads "Solar forecast with 80% band",
there are no Solar/Wind dashed lines, the Forecast page shows no source toggle, the Models page offers only "Solar" and "Real data", and
the browser console has no 404s.

---

## PHASE 12 — Decision engines: rule profiles, charges, simulator, revisions, report (Day 2)

Goal: pure-Python engines (no web code) for every new decision feature, each with tests. Phase 13 only wires them
to the API.

| Engine | File | Answers |
|---|---|---|
| Rule profiles | `vidyut/rules.py`, `config/rules/*.yaml` | which tolerance, bands, revision limits and deadline apply to this plant? |
| Deviation charges v2 | `vidyut/engines/dsm.py` | what does a schedule cost against an actual (two rate styles), and *why* (explanation)? |
| Penalty simulator | `vidyut/engines/penalty_sim.py` | what if the rules or the schedule were different? |
| Revision Advisor | `vidyut/engines/revision.py` | should the operator revise now, from which block, and why? |
| Daily report | `vidyut/engines/daily_report.py`, `vidyut/eval/pdf.py` | how did yesterday go, in MWh, MW error and ₹? |

Regulatory facts used (researched; status shown in the UI):

| Item | Source | Status |
|---|---|---|
| CERC from 1 Apr 2026: tolerance solar/hybrid ±5 %, wind ±10 %; X-factor 100 % (denominator = available capacity) | CERC order, Apr 2026 | verified |
| CERC band multipliers: under-injection 110/150/200 % of contract rate, over-injection paid 90/50/0 % | CERC Explanatory Memorandum to draft DSM Regulations 2024 | from the draft — verify against the final text |
| CERC revisions: 16/day, effective from the 4th block, one per 1.5 h slot | CERC 2015 RE framework | verify against IEGC 2023 |
| Gujarat GERC 2019: wind ±12 %, solar ±7 %; flat ₹0.25/0.50/0.75 per kWh in 8-point bands; 16 revisions/day wind, 9 solar (05:30–19:00), effective from 4th block, min change 2 %; day-ahead by 09:00 | GERC F&S Regulations 2019 text | verified |
| Madhya Pradesh MPERC 2018 (3rd amendment 2025): error % = 100 × (Actual − Scheduled) / AvC | MPERC gazette | formula verified; **bands NOT verified** (placeholder copies the 2015 CERC structure) |

Reminder for the pitch: schedules go to the **SLDC/RLDC through the QCA**; the regulators (CERC/SERCs) only write
the rules. The official DSM account comes from the load despatch centre — Vidyut's numbers are estimates.

---

### 12.1 State rule profiles  ·  Owner: Dev A  ·  Depends on: 11.1

Touches: new `config/rules/`, new `ml/vidyut/rules.py`; **delete** `config/dsm.yaml` (its illustrative flat
slabs are replaced by `cerc_2026.yaml`).

Profile format (one YAML per regulator). `rate_type: contract_multiplier` → each band has `under` (seller pays
`under × contract rate` for missing energy, i.e. extra = `under − 1`) and `over` (seller is paid only `over ×`
contract rate for surplus, loss = `1 − over`). `rate_type: inr_per_kwh` → each band has a flat `inr_per_kwh`.
The first band normally ends at the tolerance and costs nothing; the last band has `upto_pct: null`.

#### T12.1.1 — `config/rules/cerc_2026.yaml`  ✅ Tested
**FILE: `config/rules/cerc_2026.yaml`** — ✅ Tested

````yaml
# CERC deviation & scheduling profile for inter-state wind/solar/hybrid sellers, from 1 April 2026.
id: cerc_2026
name: "CERC DSM Regulations 2024 (inter-state) — from 1 Apr 2026"
jurisdiction: "Central (CERC) — inter-state sellers, and state plants selling outside their state"
states: []                         # used as the fallback when no state profile exists
status: partially_verified         # verified | partially_verified | unverified_template
notes:
  - "Tolerance (solar/hybrid 5%, wind 10%) and the FY2026-27 X factor (100%) are from the April 2026 CERC order (verified)."
  - "Band edges and multipliers are from CERC's Explanatory Memorandum to the draft DSM Regulations 2024 — verify against the final notified text."
  - "Revision mechanics (16/day, effective from the 4th block, one per 1.5 h slot) are from the 2015 CERC framework — verify against IEGC 2023."
sources:
  - "https://www.energetica-india.net/news/cerc-notifies-phased-x-factor-reduction-for-wind-and-solar-tightens-deviation-bands-from-april-2026"
  - "https://cercind.gov.in/2024/draft_reg/EMDSM.pdf"
  - "https://allaboutrenewables.com/get_pdf_portal_content.php?q=228"
block_minutes: 15
rate_type: contract_multiplier     # charges are multiples of the contract (PPA) rate
x_factor: {solar: 1.0, wind: 1.0, hybrid: 1.0}   # denominator = X*AvC + (1-X)*schedule
tolerance_pct: {solar: 5.0, wind: 10.0, hybrid: 5.0}
bands:                             # upto_pct: null means "and above"
  solar:
    - {upto_pct: 5.0,  under: 1.00, over: 1.00}
    - {upto_pct: 10.0, under: 1.10, over: 0.90}
    - {upto_pct: 20.0, under: 1.50, over: 0.50}
    - {upto_pct: null, under: 2.00, over: 0.00}
  hybrid:
    - {upto_pct: 5.0,  under: 1.00, over: 1.00}
    - {upto_pct: 10.0, under: 1.10, over: 0.90}
    - {upto_pct: 20.0, under: 1.50, over: 0.50}
    - {upto_pct: null, under: 2.00, over: 0.00}
  wind:
    - {upto_pct: 10.0, under: 1.00, over: 1.00}
    - {upto_pct: 15.0, under: 1.10, over: 0.90}
    - {upto_pct: 25.0, under: 1.50, over: 0.50}
    - {upto_pct: null, under: 2.00, over: 0.00}
revisions:
  max_per_day: {solar: 16, wind: 16, hybrid: 16}
  effective_from_block: 4          # notice block counts as block 1
  one_per_slot_hours: 1.5
  min_change_pct: 0.0
  solar_window_ist: null
day_ahead:
  deadline_ist: "10:00"            # [verify] IEGC 2023 timeline
````

#### T12.1.2 — `config/rules/gujarat_gerc_2019.yaml`  ✅ Tested
**FILE: `config/rules/gujarat_gerc_2019.yaml`** — ✅ Tested

````yaml
# Gujarat (GERC) Forecasting, Scheduling & Deviation Settlement for wind and solar, 2019.
id: gujarat_gerc_2019
name: "GERC F&S Regulations 2019 (Gujarat, intra-state)"
jurisdiction: "Gujarat Electricity Regulatory Commission — intra-state wind/solar"
states: ["Gujarat"]
status: verified
notes:
  - "All numbers from the GERC 2019 regulation text (Reg. 3.1, 5.1, 5.9-5.11, 8.5-8.6)."
  - "Hybrid is not defined in the 2019 text: Vidyut applies the stricter SOLAR rules to hybrid (assumption)."
  - "Plants selling outside Gujarat follow CERC rules (Reg. 8.5/8.6 proviso) — set market.interstate: true."
sources:
  - "https://www.cbip.org/regulationsdata/Gujarat/GujaratForecasting2019.pdf"
block_minutes: 15
rate_type: inr_per_kwh             # flat rupees per unit of deviation energy in each band
x_factor: {solar: 1.0, wind: 1.0, hybrid: 1.0}   # error % is measured against Available Capacity
tolerance_pct: {solar: 7.0, wind: 12.0, hybrid: 7.0}
bands:
  solar:
    - {upto_pct: 7.0,  inr_per_kwh: 0.00}
    - {upto_pct: 15.0, inr_per_kwh: 0.25}
    - {upto_pct: 23.0, inr_per_kwh: 0.50}
    - {upto_pct: null, inr_per_kwh: 0.75}
  hybrid:
    - {upto_pct: 7.0,  inr_per_kwh: 0.00}
    - {upto_pct: 15.0, inr_per_kwh: 0.25}
    - {upto_pct: 23.0, inr_per_kwh: 0.50}
    - {upto_pct: null, inr_per_kwh: 0.75}
  wind:
    - {upto_pct: 12.0, inr_per_kwh: 0.00}
    - {upto_pct: 20.0, inr_per_kwh: 0.25}
    - {upto_pct: 28.0, inr_per_kwh: 0.50}
    - {upto_pct: null, inr_per_kwh: 0.75}
revisions:
  max_per_day: {solar: 9, wind: 16, hybrid: 9}
  effective_from_block: 4
  one_per_slot_hours: null
  min_change_pct: 2.0              # a revision must change the schedule by more than 2%
  solar_window_ist: ["05:30", "19:00"]
day_ahead:
  deadline_ist: "09:00"
````

#### T12.1.3 — `config/rules/madhya_pradesh_mperc_2018.yaml`  ✅ Tested
**FILE: `config/rules/madhya_pradesh_mperc_2018.yaml`** — ✅ Tested

````yaml
# Madhya Pradesh (MPERC) Forecasting, Scheduling & DSM Regulations 2018 (3rd amendment 03.10.2025).
id: madhya_pradesh_mperc_2018
name: "MPERC F&S + DSM Regulations 2018 (Madhya Pradesh, intra-state) — UNVERIFIED BANDS"
jurisdiction: "Madhya Pradesh Electricity Regulatory Commission — intra-state wind (>=10 MW), solar (>=5 MW), hybrid (>=10 MW)"
states: ["Madhya Pradesh"]
status: unverified_template
notes:
  - "Verified: error % = 100 x (Actual - Scheduled) / AvC per 15-min block (3rd amendment, 2025); charges are linked to the PPA rate; QCA submits 15-min forecasts."
  - "NOT verified: band edges and multipliers live in the operating-procedure tables (IA-IV), not found online. The values below COPY the 2015 CERC framework structure as a placeholder."
  - "Task T10.2.4: get the MPERC operating procedure (mperc.in / MP SLDC) and replace the bands and revision rules."
sources:
  - "https://mperc.in/uploads/regulation_document/MP-Gazette-AG-44-iii-2025-English-OCR1.pdf"
  - "https://mercomindia.com/madhya-pradesh-solar-wind-generators-qca"
block_minutes: 15
rate_type: contract_multiplier
x_factor: {solar: 1.0, wind: 1.0, hybrid: 1.0}
tolerance_pct: {solar: 15.0, wind: 15.0, hybrid: 15.0}
bands:
  solar:
    - {upto_pct: 15.0, under: 1.00, over: 1.00}
    - {upto_pct: 25.0, under: 1.10, over: 0.90}
    - {upto_pct: 35.0, under: 1.20, over: 0.80}
    - {upto_pct: null, under: 1.30, over: 0.70}
  hybrid:
    - {upto_pct: 15.0, under: 1.00, over: 1.00}
    - {upto_pct: 25.0, under: 1.10, over: 0.90}
    - {upto_pct: 35.0, under: 1.20, over: 0.80}
    - {upto_pct: null, under: 1.30, over: 0.70}
  wind:
    - {upto_pct: 15.0, under: 1.00, over: 1.00}
    - {upto_pct: 25.0, under: 1.10, over: 0.90}
    - {upto_pct: 35.0, under: 1.20, over: 0.80}
    - {upto_pct: null, under: 1.30, over: 0.70}
revisions:
  max_per_day: {solar: 16, wind: 16, hybrid: 16}
  effective_from_block: 4
  one_per_slot_hours: null
  min_change_pct: 0.0
  solar_window_ist: null
day_ahead:
  deadline_ist: "10:00"            # [verify]
````

#### T12.1.4 — `config/rules/_template.yaml` (how to add a state)  ✅ Tested
**FILE: `config/rules/_template.yaml`** — ✅ Tested

````yaml
# Copy to config/rules/<state>_<regulator>_<year>.yaml, fill every field from the regulation text,
# set status: verified only when every number has a source. Files starting with "_" are not loaded.
id: state_regulator_year
name: "<Regulator> F&S / DSM Regulations <year> (<State>)"
jurisdiction: "<who it applies to, thresholds>"
states: ["<State name exactly as in the setup dropdown>"]
status: unverified_template
notes: []
sources: []
block_minutes: 15
rate_type: contract_multiplier       # or inr_per_kwh
x_factor: {solar: 1.0, wind: 1.0, hybrid: 1.0}
tolerance_pct: {solar: 0.0, wind: 0.0, hybrid: 0.0}
bands:                               # contract_multiplier: {upto_pct, under, over}; inr_per_kwh: {upto_pct, inr_per_kwh}
  solar: [{upto_pct: null, under: 1.0, over: 1.0}]
  wind: [{upto_pct: null, under: 1.0, over: 1.0}]
  hybrid: [{upto_pct: null, under: 1.0, over: 1.0}]
revisions:
  max_per_day: {solar: 16, wind: 16, hybrid: 16}
  effective_from_block: 4
  one_per_slot_hours: null
  min_change_pct: 0.0
  solar_window_ist: null
day_ahead:
  deadline_ist: "10:00"
````

#### T12.1.5 — `ml/vidyut/rules.py`  ✅ Tested
`resolve_profile_id(state, interstate, requested)`: explicit choice → that profile; plant selling outside its
state → CERC; a profile listing the state → that one; otherwise CERC with a "fallback" reason shown in the UI.
**FILE: `ml/vidyut/rules.py`** — ✅ Tested

````python
"""State/central deviation & scheduling rule profiles (config/rules/*.yaml).

A profile describes, for one regulator: tolerance bands, deviation charges, the deviation denominator,
revision limits and the day-ahead deadline. The setup wizard lets the operator pick their state;
`profile_for(cfg)` resolves which profile applies.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from vidyut.paths import CONFIG_DIR

RULES_DIR = CONFIG_DIR / "rules"
SOURCES = ("solar", "wind", "hybrid")

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep",
    "Puducherry",
]


class Band(BaseModel):
    upto_pct: Optional[float] = None       # None = no upper limit
    under: float = 1.0                     # contract_multiplier: seller PAYS under x contract rate
    over: float = 1.0                      # contract_multiplier: seller RECEIVES over x contract rate
    inr_per_kwh: float = 0.0               # inr_per_kwh: flat charge on energy in this band


class Revisions(BaseModel):
    max_per_day: dict[str, int]
    effective_from_block: int = Field(4, ge=1)
    one_per_slot_hours: Optional[float] = None
    min_change_pct: float = 0.0
    solar_window_ist: Optional[tuple[str, str]] = None


class DayAhead(BaseModel):
    deadline_ist: str = "10:00"


class RuleProfile(BaseModel):
    id: str
    name: str
    jurisdiction: str = ""
    states: list[str] = []
    status: Literal["verified", "partially_verified", "unverified_template"]
    notes: list[str] = []
    sources: list[str] = []
    block_minutes: int = 15
    rate_type: Literal["contract_multiplier", "inr_per_kwh"]
    x_factor: dict[str, float]
    tolerance_pct: dict[str, float]
    bands: dict[str, list[Band]]
    revisions: Revisions
    day_ahead: DayAhead = DayAhead()

    @model_validator(mode="after")
    def _check(self) -> "RuleProfile":
        for s in SOURCES:
            if s not in self.bands or s not in self.tolerance_pct or s not in self.x_factor:
                raise ValueError(f"profile {self.id}: missing source {s}")
            edges = [b.upto_pct for b in self.bands[s]]
            if edges[-1] is not None or any(e is None for e in edges[:-1]):
                raise ValueError(f"profile {self.id}/{s}: only the last band may have upto_pct null")
            if edges[:-1] != sorted(edges[:-1]):
                raise ValueError(f"profile {self.id}/{s}: band edges must increase")
        return self

    @property
    def block_hours(self) -> float:
        return self.block_minutes / 60.0

    def summary(self) -> dict:
        return {"id": self.id, "name": self.name, "status": self.status, "states": self.states,
                "jurisdiction": self.jurisdiction, "tolerance_pct": self.tolerance_pct,
                "rate_type": self.rate_type, "notes": self.notes, "sources": self.sources,
                "revisions": self.revisions.model_dump(), "day_ahead": self.day_ahead.model_dump()}


@lru_cache(maxsize=32)
def load_profile(profile_id: str) -> RuleProfile:
    path = RULES_DIR / f"{profile_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no rule profile {profile_id!r} in {RULES_DIR}")
    return RuleProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def list_profiles() -> list[RuleProfile]:
    return [load_profile(p.stem) for p in sorted(RULES_DIR.glob("*.yaml")) if not p.stem.startswith("_")]


def resolve_profile_id(state: str, interstate: bool = False, requested: str = "auto") -> tuple[str, str]:
    """Return (profile_id, reason). Inter-state sellers -> CERC; else the state's profile; else CERC fallback."""
    if requested and requested != "auto":
        return requested, "chosen explicitly in setup"
    if interstate:
        return "cerc_2026", "plant sells outside its state -> CERC rules"
    for p in list_profiles():
        if state in p.states:
            return p.id, f"state profile for {state}"
    return "cerc_2026", f"no profile for {state} yet -> CERC used as fallback (add config/rules/<state>.yaml)"


def profile_for(cfg) -> tuple[RuleProfile, str]:
    pid, reason = resolve_profile_id(cfg.market.state, cfg.market.interstate, cfg.market.rule_profile)
    return load_profile(pid), reason
````

#### T12.1.6 — Remove the old DSM file  📝
```bash
git rm config/dsm.yaml
git grep -n "dsm.yaml\|DsmProfile" -- ml backend      # must print nothing after 12.2 and 12.5
```

#### T12.1.7 — Verify the Madhya Pradesh bands (research task, ~2 h)  📝
The MP profile is a labelled placeholder (`status: unverified_template`). Get the MPERC "Procedure for
Forecasting, Scheduling and Deviation Settlement" (operating procedure annexures / tables IA–IV) from mperc.in or
the MP SLDC website (sldcmpindia.com), or ask the QCA of any MP wind/solar plant. Fill `tolerance_pct`, `bands`,
`revisions` and `day_ahead.deadline_ist`, put the document link in `sources`, and set `status: verified` only if
every number came from it. If you cannot get it before the demo, keep the placeholder: the UI already says
"UNVERIFIED BANDS", which judges respect more than invented precision.

---

### 12.2 Deviation charges v2 and charge explanation  ·  Depends on: 12.1

#### T12.2.1 — `ml/vidyut/engines/dsm.py`  ✅ Tested
`deviation_charges(schedule, actual, avc, source, profile, contract_rate)` supports both rate types;
`explain_block(...)` returns the same number as text steps + per-band rows (the Charge Explanation feature);
`expected_charges` integrates over 39 quantile levels (expectation of the charge, not the charge of the
expectation); `prob_outside_tolerance`; `choose_level`; `block_numbers` (IST block 1–96); `schedule_csv`.
**FILE: `ml/vidyut/engines/dsm.py`** — ✅ Tested

````python
"""H5 Deviation Shield: deviation charges, charge explanation, expected charges, schedule choice.

For each 15-minute block:
    denominator  = X * AvC + (1 - X) * schedule                      (X, AvC from the rule profile / plant)
    deviation %  = 100 * (actual - schedule) / denominator
    The absolute deviation % is split across the profile's bands. For each band:
      inr_per_kwh          : extra = energy_in_band * rate
      contract_multiplier  : under-injection extra = energy * (under - 1) * contract_rate   (paid on top)
                             over-injection  extra = energy * (1 - over) * contract_rate    (revenue lost)
"extra" = money lost compared with delivering exactly the schedule. Profiles: config/rules/*.yaml.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from vidyut.rules import RuleProfile
from vidyut.schema import QUANTILES


def _band_parts(abs_pct: np.ndarray, bands) -> list[tuple[float, float, np.ndarray]]:
    """[(lower, upper, part_pct_array)] — how many % points of deviation fall in each band."""
    out, lower = [], 0.0
    for b in bands:
        upper = np.inf if b.upto_pct is None else float(b.upto_pct)
        out.append((lower, upper, np.clip(abs_pct - lower, 0, upper - lower)))
        lower = upper
    return out


def deviation_charges(schedule_mw: np.ndarray, actual_mw: np.ndarray, avc_mw: float, source: str,
                      profile: RuleProfile, contract_rate: float) -> pd.DataFrame:
    schedule_mw = np.asarray(schedule_mw, float)
    actual_mw = np.asarray(actual_mw, float)
    x = profile.x_factor[source]
    denom = np.maximum(x * avc_mw + (1 - x) * schedule_mw, 1e-3)
    dev_mw = actual_mw - schedule_mw
    dev_pct = 100 * dev_mw / denom
    under = dev_mw < 0
    bands = profile.bands[source]
    charge = np.zeros(len(dev_mw))
    for b, (_, _, part) in zip(bands, _band_parts(np.abs(dev_pct), bands)):
        kwh = part / 100 * denom * profile.block_hours * 1000
        if profile.rate_type == "inr_per_kwh":
            charge += kwh * b.inr_per_kwh
        else:
            charge += np.where(under, kwh * (b.under - 1.0), kwh * (1.0 - b.over)) * contract_rate
    tol = profile.tolerance_pct[source]
    return pd.DataFrame({"schedule_mw": schedule_mw, "actual_mw": actual_mw, "deviation_mw": dev_mw,
                         "denominator_mw": denom, "deviation_pct": dev_pct,
                         "beyond_tolerance_pct": np.maximum(np.abs(dev_pct) - tol, 0.0),
                         "charge_inr": np.maximum(charge, 0.0)})


def explain_block(schedule_mw: float, actual_mw: float, avc_mw: float, source: str, profile: RuleProfile,
                  contract_rate: float, label: str = "") -> dict:
    """Step-by-step explanation of one block's charge (Charge Explanation feature)."""
    x = profile.x_factor[source]
    denom = max(x * avc_mw + (1 - x) * schedule_mw, 1e-3)
    dev = actual_mw - schedule_mw
    pct = 100 * dev / denom
    direction = "under-injection" if dev < 0 else ("over-injection" if dev > 0 else "on schedule")
    steps = [
        f"{label}Scheduled {schedule_mw:.2f} MW, actual {actual_mw:.2f} MW -> {direction} of {abs(dev):.2f} MW.",
        f"Denominator = X x AvC + (1 - X) x schedule = {x:.2f} x {avc_mw:.1f} + {1 - x:.2f} x {schedule_mw:.2f}"
        f" = {denom:.2f} MW -> deviation {pct:+.2f}% (tolerance ±{profile.tolerance_pct[source]:.1f}%).",
    ]
    total = 0.0
    lines = []
    for b, (lo, hi, part) in zip(profile.bands[source], _band_parts(np.array([abs(pct)]), profile.bands[source])):
        p = float(part[0])
        if p <= 0:
            continue
        kwh = p / 100 * denom * profile.block_hours * 1000
        hi_txt = "and above" if np.isinf(hi) else f"{hi:g}%"
        if profile.rate_type == "inr_per_kwh":
            extra = kwh * b.inr_per_kwh
            how = f"₹{b.inr_per_kwh:.2f}/kWh"
        elif dev < 0:
            extra = kwh * (b.under - 1.0) * contract_rate
            how = (f"settled at {100 * b.under:.0f}% of contract rate "
                   f"(extra {100 * (b.under - 1):.0f}% x ₹{contract_rate:.2f})")
        else:
            extra = kwh * (1.0 - b.over) * contract_rate
            how = f"paid at {100 * b.over:.0f}% of contract rate (loses {100 * (1 - b.over):.0f}% x ₹{contract_rate:.2f})"
        total += extra
        lines.append({"band": f"{lo:g}%–{hi_txt}", "deviation_points_pct": round(p, 3), "energy_kwh": round(kwh, 1),
                      "rule": how, "extra_inr": round(extra, 2)})
        steps.append(f"Band {lo:g}%–{hi_txt}: {p:.2f} points = {kwh:.0f} kWh, {how} -> ₹{extra:,.2f}")
    steps.append(f"Total extra cost for this block: ₹{total:,.2f}"
                 + (" (within tolerance: no penalty)" if total == 0 else ""))
    return {"schedule_mw": schedule_mw, "actual_mw": actual_mw, "deviation_mw": dev, "deviation_pct": pct,
            "denominator_mw": denom, "direction": direction, "bands": lines, "total_extra_inr": round(total, 2),
            "steps": steps, "profile_id": profile.id, "profile_status": profile.status}


def schedule_at_level(q: np.ndarray, tau: float) -> np.ndarray:
    """Interpolate a schedule at quantile level tau from rows of (q05..q95)."""
    return np.array([np.interp(tau, QUANTILES, row) for row in q])


_LEVELS = np.linspace(0.025, 0.975, 39)


def expected_charges(schedule_mw: np.ndarray, q_blocks: np.ndarray, avc_mw: float, source: str,
                     profile: RuleProfile, contract_rate: float) -> np.ndarray:
    """Expected extra cost per block when the actual is uncertain (quantile rows q05..q95).

    Expectation over 39 evenly spaced probability levels of each block's quantile function.
    Expectation is linear, so block errors need not be independent for the TOTAL to be right.
    """
    schedule_mw = np.asarray(schedule_mw, float)
    out = np.zeros(len(schedule_mw))
    for lv in _LEVELS:
        actual = schedule_at_level(q_blocks, lv)
        out += deviation_charges(schedule_mw, actual, avc_mw, source, profile, contract_rate)["charge_inr"].to_numpy()
    return out / len(_LEVELS)


def prob_outside_tolerance(schedule_mw: np.ndarray, q_blocks: np.ndarray, avc_mw: float, source: str,
                           profile: RuleProfile) -> np.ndarray:
    """P(|deviation %| > tolerance) per block from the quantile function."""
    schedule_mw = np.asarray(schedule_mw, float)
    tol = profile.tolerance_pct[source]
    x = profile.x_factor[source]
    denom = np.maximum(x * avc_mw + (1 - x) * schedule_mw, 1e-3)
    hits = np.zeros(len(schedule_mw))
    for lv in _LEVELS:
        actual = schedule_at_level(q_blocks, lv)
        hits += (np.abs(100 * (actual - schedule_mw) / denom) > tol)
    return hits / len(_LEVELS)


def choose_level(q_blocks: np.ndarray, actual_blocks: np.ndarray, avc: float, source: str, profile: RuleProfile,
                 contract_rate: float, grid: np.ndarray | None = None) -> tuple[float, pd.DataFrame]:
    """Pick the schedule quantile level with the lowest realised charges (fit on VALIDATION blocks only)."""
    grid = np.round(np.arange(0.30, 0.701, 0.05), 2) if grid is None else grid
    res = [(t, deviation_charges(schedule_at_level(q_blocks, t), actual_blocks, avc, source, profile,
                                 contract_rate)["charge_inr"].sum()) for t in grid]
    table = pd.DataFrame(res, columns=["level", "charge_inr"])
    return float(table.loc[table["charge_inr"].idxmin(), "level"]), table


def block_numbers(block_end_utc: pd.DatetimeIndex) -> np.ndarray:
    """IST block number 1..96 for 15-min blocks given by their END time."""
    start = block_end_utc.tz_convert("Asia/Kolkata") - pd.Timedelta(minutes=15)
    return (start.hour * 4 + start.minute // 15 + 1).to_numpy()


def schedule_csv(blocks_mw: pd.Series) -> str:
    """Day-ahead/revised schedule export: one row per 15-min block in IST (block 1 = 00:00-00:15)."""
    ist_end = blocks_mw.index.tz_convert("Asia/Kolkata")
    ist_start = ist_end - pd.Timedelta(minutes=15)
    df = pd.DataFrame({"block_no": block_numbers(blocks_mw.index),
                       "start_ist": ist_start.strftime("%Y-%m-%d %H:%M"), "end_ist": ist_end.strftime("%H:%M"),
                       "schedule_mw": blocks_mw.round(3).to_numpy()})
    return df.to_csv(index=False)
````

Worked example to check by hand (it is also a test): CERC solar, AvC 50 MW, schedule 30 MW, actual 25 MW →
deviation −10 % of AvC; 5 points in the free band, 5 points in the 5–10 % band = 5 % × 50 MW × 0.25 h = 625 kWh
× (1.10 − 1) × ₹2.70 = **₹168.75** for that block.

#### T12.2.2 — Rule and explanation tests  ✅ Tested
**FILE: `ml/tests/test_rules.py`** — ✅ Tested

````python
import numpy as np
import pytest

from vidyut.engines.dsm import deviation_charges, explain_block
from vidyut.rules import list_profiles, load_profile, resolve_profile_id


def test_all_profiles_load_and_cover_sources():
    ids = {p.id for p in list_profiles()}
    assert {"cerc_2026", "gujarat_gerc_2019", "madhya_pradesh_mperc_2018"} <= ids


def test_profile_resolution():
    assert resolve_profile_id("Gujarat")[0] == "gujarat_gerc_2019"
    assert resolve_profile_id("Gujarat", interstate=True)[0] == "cerc_2026"
    pid, reason = resolve_profile_id("Kerala")
    assert pid == "cerc_2026" and "fallback" in reason


def test_gujarat_flat_rupee_bands():
    g = load_profile("gujarat_gerc_2019")             # solar: free to 7 %, Rs0.25 to 15 %, Rs0.50 to 23 %
    ch = deviation_charges(np.array([30.0]), np.array([20.0]), 50.0, "solar", g, 2.70)   # 20 % error
    kwh = lambda pts: pts / 100 * 50 * 0.25 * 1000  # noqa: E731
    assert ch["charge_inr"].iloc[0] == pytest.approx(kwh(8) * 0.25 + kwh(5) * 0.50)


def test_explanation_matches_charge():
    p = load_profile("cerc_2026")
    e = explain_block(30.0, 25.0, 50.0, "solar", p, 2.70)
    c = deviation_charges(np.array([30.0]), np.array([25.0]), 50.0, "solar", p, 2.70)["charge_inr"].iloc[0]
    assert e["total_extra_inr"] == pytest.approx(c, abs=0.01)
    assert e["total_extra_inr"] == pytest.approx(168.75, abs=0.01)   # EXPLAIN.md worked example
    assert any("110%" in s for s in e["steps"])
````

#### T12.2.3 — Update the engine tests for the new DSM signature  ✅ Tested
**FILE: `ml/tests/test_engines.py`** — ✅ Tested

````python
import numpy as np
import pandas as pd
import pytest

from vidyut.engines.alerts import alert_skill, alert_thresholds, generate_alerts, prob_below
from vidyut.engines.dispatch import plan
from vidyut.engines.dsm import deviation_charges
from vidyut.engines.hybrid import combine
from vidyut.engines.trust import hybrid_trust_score
from vidyut.models.downscale import downscale_wind
from vidyut.rules import load_profile


def test_dispatch_feasible_and_battery_helps(cfg):
    t = 24
    gen = np.r_[np.zeros(8), np.full(8, 60.0), np.zeros(8)]
    dem = np.full(t, 25.0)
    r = plan(gen, dem, cfg.battery, cfg.costs)
    s = r.schedule
    bal = s.gen_mw - s.curtail_mw - s.charge_mw + s.discharge_mw + s.backup_mw - s.demand_mw
    assert np.allclose(bal, 0, atol=1e-6)
    assert s.soc_mwh.min() >= cfg.battery.soc_min_frac * cfg.battery.energy_mwh - 1e-6
    bigger = plan(gen, dem, cfg.battery.model_copy(update={"energy_mwh": 200, "power_mw": 50}), cfg.costs)
    assert bigger.kpis["backup_mwh"] <= r.kpis["backup_mwh"] + 1e-6


def test_prob_below_monotone():
    q = np.array([[1, 2, 5, 8, 9.0]])
    p = [prob_below(q, x)[0] for x in (0.5, 2, 5, 8, 20)]
    assert p == sorted(p) and p[2] == pytest.approx(0.5)


def test_combine_bounds():
    qs = np.array([[0, 1, 5, 9, 10.0]])
    qw = np.array([[2, 3, 6, 9, 10.0]])
    out = combine(qs, qw, 40, 50, np.array([0.0]))
    assert (np.diff(out, axis=1) >= 0).all() and out.min() >= 0 and out.max() <= 90


def test_dsm_no_charge_within_tolerance():
    """CERC 2026 wind: 10 % tolerance; 10-15 % band settles under-injection at 110 % of the contract rate."""
    prof = load_profile("cerc_2026")
    ch = deviation_charges(np.array([20.0, 20.0]), np.array([24.0, 13.0]), 50.0, "wind", prof, 2.70)
    assert ch["charge_inr"].iloc[0] == 0                       # +8 % < 10 %
    # -14 %: 4 points in the 10-15 % band -> 4 % x 50 MW x 0.25 h = 500 kWh x 0.10 x 2.70
    assert ch["charge_inr"].iloc[1] == pytest.approx(500 * 0.10 * 2.70)


def test_downscale_preserves_energy():
    idx = pd.date_range("2024-01-01 01:00", periods=24, freq="h", tz="UTC")
    hourly = pd.Series(np.linspace(5, 40, 24), index=idx)
    b = downscale_wind(hourly, 50)
    assert len(b) == 96
    assert abs(b.mean() - hourly.mean()) / hourly.mean() < 0.005


def test_alert_thresholds_train_only_no_leakage(cfg, ds):
    th_orig = alert_thresholds(ds, cfg)
    corrupted = ds.copy()
    val_b = cfg.splits.bounds()["val"]
    test_b = cfg.splits.bounds()["test"]
    corrupted.loc[val_b[0]:val_b[1], ["solar_mw", "wind_mw"]] = 999999.0
    corrupted.loc[test_b[0]:test_b[1], ["solar_mw", "wind_mw"]] = -999999.0
    th_corrupted = alert_thresholds(corrupted, cfg)
    assert th_orig == th_corrupted


def test_alert_thresholds_mapping_and_scalar(cfg, ds):
    th_map = alert_thresholds(ds, cfg)
    th_scalar = alert_thresholds(ds, cfg, low_quantile=0.10)

    # Solar and hybrid use 0.10 in both, so low_mw matches
    assert th_map["solar"]["low_mw"] == th_scalar["solar"]["low_mw"]
    assert th_map["hybrid"]["low_mw"] == th_scalar["hybrid"]["low_mw"]
    # Wind uses P25 in mapping vs P10 in scalar -> wind low threshold is higher
    assert th_map["wind"]["low_mw"] > th_scalar["wind"]["low_mw"]

    # Custom mapping argument
    custom_map = {"solar": 0.15, "wind": 0.30, "hybrid": 0.20}
    th_custom = alert_thresholds(ds, cfg, low_quantile=custom_map)
    assert th_custom["wind"]["low_mw"] > th_map["wind"]["low_mw"]
    assert th_custom["solar"]["low_mw"] > th_map["solar"]["low_mw"]


def test_every_alert_type_can_fire_on_crafted_forecast(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=4, freq="h", tz="UTC")
    # Row 0: low generation, Row 1: ramp up, Row 2: high generation, Row 3: normal
    q_data = [
        [0.1, 0.2, 0.5, 0.8, 1.0],     # well below 3.0 MW -> LOW_GENERATION
        [5.0, 10.0, 20.0, 25.0, 30.0],  # jump from 0.5 to 20.0 (ramp 19.5 >= 10.0) -> RAMP
        [32.0, 35.0, 36.0, 38.0, 39.0], # well above 28.0 MW -> HIGH_GENERATION
        [10.0, 12.0, 15.0, 18.0, 20.0],
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    fc["cal_is_day"] = 1
    thrs = {"low_mw": 3.0, "high_mw": 28.0, "ramp_mw_per_h": 10.0}
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], thresholds=thrs)
    types = {a.type for a in alerts}
    assert "LOW_GENERATION" in types
    assert "HIGH_GENERATION" in types
    assert "RAMP" in types


def test_alert_message_contains_numeric_threshold(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=3, freq="h", tz="UTC")
    q_data = [
        [0.1, 0.2, 0.4, 0.6, 0.8],     # P(X < 3.2 MW) ~ 1.0 -> LOW
        [35.0, 36.0, 37.0, 38.0, 39.0], # ramp from 0.4 to 37.0 >= 8.5 MW/h -> RAMP + HIGH
        [35.0, 36.0, 37.0, 38.0, 39.0], # stays high > 30.0 MW -> HIGH
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    fc["cal_is_day"] = 1
    thrs = {"low_mw": 3.2, "high_mw": 30.0, "ramp_mw_per_h": 8.5}
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], thresholds=thrs)
    for a in alerts:
        if a.type == "LOW_GENERATION":
            assert "3.2 MW" in a.message
            assert "%" in a.message
        elif a.type == "HIGH_GENERATION":
            assert "30.0 MW" in a.message
            assert "%" in a.message
        elif a.type == "RAMP":
            assert "8.5 MW" in a.message


def test_generate_alerts_fallback_when_thresholds_missing(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=2, freq="h", tz="UTC")
    q_data = [
        [0.1, 0.2, 0.5, 0.8, 1.0],      # below 4.0 MW (10% of 40)
        [36.0, 37.0, 38.0, 39.0, 40.0],  # above 34.0 MW (85% of 40) & ramp 37.5 >= 20.0
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    fc["cal_is_day"] = 1
    # Calling with thresholds=None should fall back to config fraction/MW
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], thresholds=None)
    types = {a.type for a in alerts}
    assert "LOW_GENERATION" in types
    assert "HIGH_GENERATION" in types
    assert "RAMP" in types
    for a in alerts:
        if a.type == "LOW_GENERATION":
            assert "4.0 MW" in a.message
        elif a.type == "HIGH_GENERATION":
            assert "34.0 MW" in a.message
        elif a.type == "RAMP":
            assert "20.0 MW" in a.message


def test_alert_skill_unaffected():
    idx = pd.date_range("2024-05-01 00:00", periods=4, freq="h", tz="UTC")
    actual = pd.Series([1.0, 2.0, 5.0, 10.0], index=idx)
    # Target hours 0 and 1 flagged
    flagged = pd.Series([True, True, False, False], index=idx)
    res = alert_skill(flagged, actual, "LOW_GENERATION", 3.0)
    assert res["precision"] == pytest.approx(1.0)
    assert res["recall"] == pytest.approx(1.0)
    assert res["alert_hours"] == 2
    assert res["event_hours"] == 2


def test_hybrid_trust_score():
    # 1. Weights: w_s = 10, w_w = 30 -> (10*80 + 30*40) / 40 = 2000 / 40 = 50.0
    s_weighted = hybrid_trust_score(10.0, 30.0, 80.0, 40.0)
    assert s_weighted == 50.0

    # 2. Both-zero fallback (< 1e-6) -> (80 + 40) / 2 = 60.0
    s_zero = hybrid_trust_score(0.0, 0.0, 80.0, 40.0)
    assert s_zero == 60.0

    # Near-zero fallback (< 1e-6)
    s_near_zero = hybrid_trust_score(1e-8, 1e-8, 80.0, 40.0)
    assert s_near_zero == 60.0

    # 3. Bounds 0..100
    assert hybrid_trust_score(10.0, 20.0, 100.0, 100.0) == 100.0
    assert hybrid_trust_score(10.0, 20.0, 0.0, 0.0) == 0.0

    # 4. Vector inputs
    qs = np.array([10.0, 0.0, 20.0])
    qw = np.array([30.0, 0.0, 20.0])
    ts = np.array([80.0, 80.0, 70.0])
    tw = np.array([40.0, 40.0, 30.0])
    res = hybrid_trust_score(qs, qw, ts, tw)
    np.testing.assert_array_equal(res, np.array([50.0, 60.0, 50.0]))


def test_low_confidence_alert_numeric_context(cfg):
    idx = pd.date_range("2024-05-01 00:00", periods=3, freq="h", tz="UTC")
    q_data = [
        [5.0, 10.0, 15.0, 20.0, 25.0],
        [5.0, 10.0, 15.0, 20.0, 25.0],
        [5.0, 10.0, 15.0, 20.0, 25.0],
    ]
    fc = pd.DataFrame(q_data, index=idx, columns=["q05", "q10", "q50", "q90", "q95"])
    trust = pd.Series([25.0, 30.0, 80.0], index=idx)
    alerts = generate_alerts(fc, "solar", 40.0, cfg.alerts, idx[0], trust=trust)
    conf_alerts = [a for a in alerts if a.type == "LOW_CONFIDENCE"]
    assert len(conf_alerts) == 1
    # Min trust in the window is 25, threshold is cfg.alerts.low_trust_score (40)
    assert f"trust score 25 < {cfg.alerts.low_trust_score:.0f}" in conf_alerts[0].message
````

Check: `cd ml && pytest -q tests/test_rules.py tests/test_engines.py` → all pass.

---

### 12.3 Penalty simulator engine  ·  Depends on: 12.2

#### T12.3.1 — `ml/vidyut/engines/penalty_sim.py`  ✅ Tested
Rules side: profile, contract rate, tolerance override (all band edges shift together), harshness multiplier.
Schedule side: quantile level (P10–P90) plus manual block-range edits. "next" day → expected charges from the
forecast distribution; a past day → realised charges against actuals.
**FILE: `ml/vidyut/engines/penalty_sim.py`** — ✅ Tested

````python
"""Penalty simulator: what would deviation charges be under other RULES and other SCHEDULES?

Rules : pick any profile, change the contract rate, override the tolerance, scale the penalties.
Schedule: choose a quantile level (P30..P70) and/or edit block ranges by hand.
Day   : the next day (expected charges from the forecast distribution) or a past day (realised, needs actuals).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from vidyut.engines.dsm import block_numbers, deviation_charges, expected_charges, prob_outside_tolerance, schedule_at_level
from vidyut.rules import Band, RuleProfile
from vidyut.schema import QCOLS


class BlockEdit(BaseModel):
    from_block: int = Field(ge=1, le=96)
    to_block: int = Field(ge=1, le=96)
    mw: float = Field(ge=0)


class SimInput(BaseModel):
    profile_id: str | None = None                # None = the plant's profile
    contract_rate_inr_per_kwh: float | None = Field(None, gt=0)
    tolerance_override_pct: float | None = Field(None, gt=0, le=50)
    penalty_scale: float = Field(1.0, ge=0, le=5)   # 2.0 = penalties twice as harsh
    schedule_level: float = Field(0.5, ge=0.05, le=0.95)
    edits: list[BlockEdit] = []
    source: str | None = None                    # None = the plant total (resolved by the API)
    day: str = "next"                            # "next" or "YYYY-MM-DD" (past day with actuals)


def override_profile(p: RuleProfile, source: str, tolerance_pct: float | None, penalty_scale: float) -> RuleProfile:
    """Copy of the profile with a new tolerance (all band edges shift by the same amount) and scaled penalties."""
    bands = []
    shift = 0.0 if tolerance_pct is None else tolerance_pct - p.tolerance_pct[source]
    for b in p.bands[source]:
        bands.append(Band(upto_pct=None if b.upto_pct is None else max(b.upto_pct + shift, 0.01),
                          under=1.0 + (b.under - 1.0) * penalty_scale,
                          over=max(1.0 - (1.0 - b.over) * penalty_scale, 0.0),
                          inr_per_kwh=b.inr_per_kwh * penalty_scale))
    tol = dict(p.tolerance_pct)
    if tolerance_pct is not None:
        tol[source] = tolerance_pct
    return p.model_copy(update={"bands": {**p.bands, source: bands}, "tolerance_pct": tol,
                                "name": p.name + " (simulated)"})


def apply_edits(schedule: np.ndarray, blocks: np.ndarray, edits: list[BlockEdit]) -> np.ndarray:
    out = schedule.copy()
    for e in edits:
        out[(blocks >= e.from_block) & (blocks <= e.to_block)] = e.mw
    return out


def simulate(inp: SimInput, profile: RuleProfile, contract_rate: float, q_blocks: pd.DataFrame, avc_mw: float,
             actual_blocks: pd.Series | None = None) -> dict:
    """q_blocks: one IST day of block quantiles indexed by block END (UTC)."""
    src = inp.source or "hybrid"
    prof = override_profile(profile, src, inp.tolerance_override_pct, inp.penalty_scale)
    cr = inp.contract_rate_inr_per_kwh or contract_rate
    q = q_blocks[list(QCOLS)].to_numpy()
    blocks = block_numbers(q_blocks.index)
    base = schedule_at_level(q, 0.5)
    sched = apply_edits(schedule_at_level(q, inp.schedule_level), blocks, inp.edits)
    if actual_blocks is not None:
        act = actual_blocks.reindex(q_blocks.index).to_numpy(float)
        mode = "realised"
        c_s = deviation_charges(sched, act, avc_mw, src, prof, cr)["charge_inr"].to_numpy()
        c_b = deviation_charges(base, act, avc_mw, src, prof, cr)["charge_inr"].to_numpy()
    else:
        act = None
        mode = "expected"
        c_s = expected_charges(sched, q, avc_mw, src, prof, cr)
        c_b = expected_charges(base, q, avc_mw, src, prof, cr)
    p_out = prob_outside_tolerance(sched, q, avc_mw, src, prof)
    table = pd.DataFrame({"block_no": blocks, "block_end_utc": q_blocks.index.astype(str), "schedule_mw": sched.round(3),
                          "p50_mw": q[:, 2].round(3), "p10_mw": q[:, 1].round(3), "p90_mw": q[:, 3].round(3),
                          "actual_mw": None if act is None else np.round(act, 3), "charge_inr": c_s.round(2),
                          "p_outside_tolerance": p_out.round(3)})
    return {"mode": mode, "source": src, "profile": prof.summary(), "contract_rate_inr_per_kwh": cr,
            "total_charge_inr": round(float(c_s.sum()), 2), "baseline_p50_charge_inr": round(float(c_b.sum()), 2),
            "saving_vs_p50_inr": round(float(c_b.sum() - c_s.sum()), 2),
            "blocks_likely_outside_tolerance": int((p_out >= 0.5).sum()),
            "blocks": table.to_dict(orient="records")}
````

---

### 12.4 Revision Advisor engine  ·  Depends on: 12.2

How a refresh is judged (all in `evaluate_revision`):
1. Window = blocks from the **effective block** (block containing *now* + `effective_from_block − 1`, i.e. a
   revision given in block k changes block k+3 under the 4th-block rule) to the end of the IST day.
2. Proposed schedule = the tuned quantile level of the *refreshed* forecast.
3. Triggers: `BAND_BREACH_RISK` (P(outside tolerance) ≥ 60 % in any block), `FORECAST_SHIFT` (mean |P50 −
   schedule| ≥ 5 % of capacity), `ALERT` (generation/ramp/deficit alerts overlapping the window), `LOW_TRUST`
   (informational), `BLOCKED` (rule limits: revisions used up, one per 1.5 h slot, solar window, minimum change).
4. Recommend only if a strong trigger fired **and** expected saving ≥ ₹500 **and** nothing blocks it.
5. Every decision produces human-readable explanation lines (the explainability log).
6. `apply_revision`: if the operator accepts late, the effective block moves forward accordingly.

#### T12.4.1 — `ml/vidyut/engines/revision.py`  ✅ Tested
**FILE: `ml/vidyut/engines/revision.py`** — ✅ Tested

````python
"""H6 Revision Advisor: compare the submitted schedule with each refreshed forecast and recommend
intraday revisions, with an explanation of every trigger.

Indian practice (see config/rules/*.yaml): a plant submits a day-ahead schedule in 96 x 15-min blocks and
may revise it a limited number of times per day; a revision given in block k takes effect from block
k + (effective_from_block - 1). Vidyut never submits anything itself: it recommends, the operator accepts
or rejects, and the decision is logged (submission to SLDC stays manual / via the QCA).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from vidyut.engines.dsm import block_numbers, expected_charges, prob_outside_tolerance, schedule_at_level
from vidyut.rules import RuleProfile
from vidyut.schema import QCOLS

IST = "Asia/Kolkata"
BLOCK = pd.Timedelta(minutes=15)


def block_start(ts_utc: pd.Timestamp) -> pd.Timestamp:
    """Start (UTC) of the 15-min block containing ts (IST blocks align with UTC quarter hours)."""
    return pd.Timestamp(ts_utc).tz_convert("UTC").floor("15min")


def effective_start(now_utc: pd.Timestamp, profile: RuleProfile) -> pd.Timestamp:
    """Start time of the first block a revision given now can change (notice block counts as 1)."""
    return block_start(now_utc) + (profile.revisions.effective_from_block - 1) * BLOCK


def ist_date(ts_utc: pd.Timestamp) -> str:
    return pd.Timestamp(ts_utc).tz_convert(IST).strftime("%Y-%m-%d")


@dataclass
class Trigger:
    type: str          # BAND_BREACH_RISK | FORECAST_SHIFT | ALERT | LOW_TRUST | BLOCKED
    detail: str
    highlight: bool = True


@dataclass
class Evaluation:
    """Result of one refresh. `recommend` says whether a Recommendation should be created."""
    evaluated_at_utc: str
    ist_date: str
    source: str
    profile_id: str
    recommend: bool
    reason: str
    effective_from_utc: str | None = None
    effective_from_block: int | None = None
    notice_block: int | None = None
    window_blocks: list[int] = field(default_factory=list)
    window_end_utc: list[str] = field(default_factory=list)
    current_mw: list[float] = field(default_factory=list)
    proposed_mw: list[float] = field(default_factory=list)
    expected_charge_current_inr: float = 0.0
    expected_charge_proposed_inr: float = 0.0
    expected_saving_inr: float = 0.0
    max_p_breach: float = 0.0
    mean_shift_pct: float = 0.0
    revisions_used: int = 0
    max_revisions: int = 0
    triggers: list[Trigger] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        h = hashlib.sha1(f"{self.evaluated_at_utc}{self.source}{self.ist_date}".encode()).hexdigest()[:6]
        return f"REV-{self.ist_date}-{self.revisions_used + 1:02d}-{h}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d


def _ranges(blocks: list[int]) -> str:
    if not blocks:
        return "-"
    out, start, prev = [], blocks[0], blocks[0]
    for b in blocks[1:]:
        if b != prev + 1:
            out.append(f"{start}–{prev}" if start != prev else f"{start}")
            start = b
        prev = b
    out.append(f"{start}–{prev}" if start != prev else f"{start}")
    return ", ".join(out)


def evaluate_revision(now_utc: pd.Timestamp, schedule: pd.Series, q_blocks: pd.DataFrame, avc_mw: float,
                      source: str, profile: RuleProfile, contract_rate: float, rev_cfg, level: float,
                      revisions_used: int = 0, last_revision_utc: pd.Timestamp | None = None,
                      alerts: list[dict] | None = None, trust: pd.Series | None = None) -> Evaluation:
    """schedule: active schedule MW indexed by block END (UTC). q_blocks: q05..q95 indexed by block END (UTC)."""
    now_utc = pd.Timestamp(now_utc).tz_convert("UTC")
    eff = effective_start(now_utc, profile)
    day = ist_date(eff + BLOCK)
    day_end = (pd.Timestamp(day, tz=IST) + pd.Timedelta(days=1)).tz_convert("UTC")
    max_rev = profile.revisions.max_per_day[source]
    ev = Evaluation(evaluated_at_utc=now_utc.isoformat(), ist_date=day, source=source, profile_id=profile.id,
                    recommend=False, reason="", revisions_used=revisions_used, max_revisions=max_rev,
                    notice_block=int(block_numbers(pd.DatetimeIndex([block_start(now_utc) + BLOCK]))[0]))
    idx = q_blocks.index[(q_blocks.index > eff) & (q_blocks.index <= day_end)]
    idx = idx[schedule.reindex(idx).notna().to_numpy()]
    if len(idx) == 0:
        ev.reason = "no remaining blocks today with both a schedule and a forecast"
        return ev
    q = q_blocks.loc[idx, list(QCOLS)].to_numpy()
    cur = schedule.reindex(idx).to_numpy(float)
    prop = schedule_at_level(q, level)
    blocks = block_numbers(idx).tolist()
    ev.effective_from_utc = eff.isoformat()
    ev.effective_from_block = int(blocks[0])
    ev.window_blocks = [int(b) for b in blocks]
    ev.window_end_utc = [t.isoformat() for t in idx]
    ev.current_mw = np.round(cur, 3).tolist()
    ev.proposed_mw = np.round(prop, 3).tolist()

    e_cur = expected_charges(cur, q, avc_mw, source, profile, contract_rate)
    e_new = expected_charges(prop, q, avc_mw, source, profile, contract_rate)
    p_out = prob_outside_tolerance(cur, q, avc_mw, source, profile)
    shift = 100 * (q[:, 2] - cur) / avc_mw
    ev.expected_charge_current_inr = round(float(e_cur.sum()), 2)
    ev.expected_charge_proposed_inr = round(float(e_new.sum()), 2)
    ev.expected_saving_inr = round(float(e_cur.sum() - e_new.sum()), 2)
    ev.max_p_breach = round(float(p_out.max()), 3)
    ev.mean_shift_pct = round(float(shift.mean()), 2)
    tol = profile.tolerance_pct[source]

    risky = [b for b, p in zip(blocks, p_out) if p >= rev_cfg.p_breach_trigger]
    if risky:
        ev.triggers.append(Trigger("BAND_BREACH_RISK",
                                   f"Blocks {_ranges(risky)}: up to {100 * ev.max_p_breach:.0f}% chance of leaving the "
                                   f"±{tol:g}% band with the current schedule"))
    if abs(ev.mean_shift_pct) >= rev_cfg.shift_trigger_pct:
        word = "below" if ev.mean_shift_pct < 0 else "above"
        ev.triggers.append(Trigger("FORECAST_SHIFT", f"Latest forecast (P50) is on average {abs(ev.mean_shift_pct):.1f}% "
                                                     f"of capacity {word} the submitted schedule"))
    for a in alerts or []:
        a_start, a_end = pd.Timestamp(a["start_utc"]), pd.Timestamp(a["end_utc"])
        if a_end > eff and a_start < day_end and a.get("type") in ("LOW_GENERATION", "HIGH_GENERATION", "RAMP",
                                                                     "DEFICIT_VS_DEMAND"):
            ev.triggers.append(Trigger("ALERT", f"{a['type'].replace('_', ' ').title()}: {a['message']}"))
    if trust is not None and len(trust):
        tmin = float(trust.reindex(idx.ceil("h")).min())
        if tmin < 40:
            ev.triggers.append(Trigger("LOW_TRUST", f"Lowest trust in the window is {tmin:.0f}/100 — forecast is "
                                                    "uncertain; the proposal already accounts for the wide band",
                                       highlight=False))

    # hard constraints from the rule profile
    blocked = []
    if revisions_used >= max_rev:
        blocked.append(f"all {max_rev} revisions for today are used")
    r = profile.revisions
    if r.one_per_slot_hours and last_revision_utc is not None:
        slot = pd.Timedelta(hours=r.one_per_slot_hours)
        day_start = pd.Timestamp(day, tz=IST).tz_convert("UTC")
        if (now_utc - day_start) // slot == (pd.Timestamp(last_revision_utc) - day_start) // slot:
            blocked.append(f"only one revision per {r.one_per_slot_hours:g} h slot")
    if r.solar_window_ist and source != "wind":
        t = now_utc.tz_convert(IST).strftime("%H:%M")
        if not (r.solar_window_ist[0] <= t <= r.solar_window_ist[1]):
            blocked.append(f"solar revisions allowed only {r.solar_window_ist[0]}–{r.solar_window_ist[1]} IST")
    change = float(np.max(np.abs(prop - cur)) / avc_mw * 100)
    if change < r.min_change_pct:
        blocked.append(f"largest change {change:.1f}% is below the {r.min_change_pct:g}% minimum")

    strong = any(t.type in ("BAND_BREACH_RISK", "FORECAST_SHIFT") for t in ev.triggers)
    if blocked:
        ev.triggers.append(Trigger("BLOCKED", "; ".join(blocked)))
        ev.reason = "revision not allowed: " + "; ".join(blocked)
    elif not strong:
        ev.reason = "forecast still close to the schedule — no revision needed"
    elif ev.expected_saving_inr < rev_cfg.min_saving_inr:
        ev.reason = (f"expected saving ₹{ev.expected_saving_inr:,.0f} is below the ₹{rev_cfg.min_saving_inr:,.0f} "
                     "threshold — keep the revision for later")
    else:
        ev.recommend = True
        ev.reason = (f"revise blocks {ev.effective_from_block}–{blocks[-1]}: expected deviation charges fall from "
                     f"₹{ev.expected_charge_current_inr:,.0f} to ₹{ev.expected_charge_proposed_inr:,.0f}")
    ev.explanation = [
        f"Refresh at {now_utc.tz_convert(IST):%d %b %H:%M} IST (notice block {ev.notice_block}); a revision now takes "
        f"effect from block {ev.effective_from_block} ({eff.tz_convert(IST):%H:%M} IST) under {profile.name}.",
        f"Remaining blocks today: {len(idx)}. Expected charges if unchanged ₹{ev.expected_charge_current_inr:,.0f}; "
        f"with the proposed P{round(100 * level)} schedule ₹{ev.expected_charge_proposed_inr:,.0f}.",
        *[f"Trigger — {t.type}: {t.detail}" for t in ev.triggers],
        f"Decision: {'RECOMMEND REVISION' if ev.recommend else 'no revision'} — {ev.reason}.",
        f"Revisions used today: {revisions_used}/{max_rev}.",
    ]
    return ev


def apply_revision(schedule: pd.Series, ev_or_dict, accepted_at_utc: pd.Timestamp, profile: RuleProfile) -> pd.Series:
    """Return the new active schedule: proposed values replace blocks from the effective block onward.

    If the operator accepts late, the effective block moves forward (notice is counted from acceptance).
    """
    d = ev_or_dict.to_dict() if hasattr(ev_or_dict, "to_dict") else ev_or_dict
    eff = max(pd.Timestamp(d["effective_from_utc"]), effective_start(accepted_at_utc, profile))
    new = schedule.copy()
    for t, mw in zip(d["window_end_utc"], d["proposed_mw"]):
        t = pd.Timestamp(t)
        if t > eff:
            new.loc[t] = mw
    return new.sort_index()


def day_ahead_schedule(q_blocks: pd.DataFrame, level: float) -> pd.Series:
    """Penalty-aware day-ahead schedule (Rev 0) at the tuned quantile level."""
    return pd.Series(schedule_at_level(q_blocks[list(QCOLS)].to_numpy(), level), index=q_blocks.index,
                     name="schedule_mw")
````

#### T12.4.2 — Revision tests  ✅ Tested
**FILE: `ml/tests/test_revision.py`** — ✅ Tested

````python
import numpy as np
import pandas as pd

from vidyut.config import RevisionCfg
from vidyut.engines.revision import apply_revision, effective_start, evaluate_revision
from vidyut.rules import load_profile

PROF = load_profile("cerc_2026")
DAY = pd.date_range("2026-05-10 00:15", periods=96, freq="15min", tz="Asia/Kolkata").tz_convert("UTC")


def _q(center: float) -> pd.DataFrame:
    c = np.full(96, center)
    return pd.DataFrame({"q05": c - 6, "q10": c - 4, "q50": c, "q90": c + 4, "q95": c + 6}, index=DAY)


def test_effective_block_is_fourth():
    now = pd.Timestamp("2026-05-10 10:07", tz="Asia/Kolkata").tz_convert("UTC")
    assert effective_start(now, PROF).tz_convert("Asia/Kolkata").strftime("%H:%M") == "10:45"


def test_recommends_when_forecast_drops():
    sched = pd.Series(40.0, index=DAY)
    now = pd.Timestamp("2026-05-10 09:00", tz="Asia/Kolkata").tz_convert("UTC")
    ev = evaluate_revision(now, sched, _q(25.0), 90.0, "hybrid", PROF, 2.70, RevisionCfg(), 0.5)
    assert ev.recommend and ev.expected_saving_inr > 0
    assert {t.type for t in ev.triggers} >= {"BAND_BREACH_RISK", "FORECAST_SHIFT"}
    assert ev.effective_from_block == 40          # 09:00 notice block 37 -> effective 09:45-10:00 = block 40


def test_no_recommendation_when_on_track():
    sched = pd.Series(30.0, index=DAY)
    now = pd.Timestamp("2026-05-10 09:00", tz="Asia/Kolkata").tz_convert("UTC")
    ev = evaluate_revision(now, sched, _q(30.0), 90.0, "hybrid", PROF, 2.70, RevisionCfg(), 0.5)
    assert not ev.recommend and "close to the schedule" in ev.reason


def test_blocked_when_revisions_used_up():
    sched = pd.Series(40.0, index=DAY)
    now = pd.Timestamp("2026-05-10 09:00", tz="Asia/Kolkata").tz_convert("UTC")
    ev = evaluate_revision(now, sched, _q(25.0), 90.0, "hybrid", PROF, 2.70, RevisionCfg(), 0.5, revisions_used=16)
    assert not ev.recommend and any(t.type == "BLOCKED" for t in ev.triggers)


def test_apply_revision_changes_only_future_blocks():
    sched = pd.Series(40.0, index=DAY)
    now = pd.Timestamp("2026-05-10 09:00", tz="Asia/Kolkata").tz_convert("UTC")
    ev = evaluate_revision(now, sched, _q(25.0), 90.0, "hybrid", PROF, 2.70, RevisionCfg(), 0.5)
    new = apply_revision(sched, ev, now, PROF)
    eff = pd.Timestamp(ev.effective_from_utc)
    assert (new[new.index <= eff] == 40.0).all() and (new[new.index > eff] == 25.0).all()
````

Check: `cd ml && pytest -q tests/test_revision.py` → all pass (effective block 10:07 → 10:45; recommends at 09:00;
no recommendation when on track; blocked after 16 revisions; late accept).

---

### 12.5 Training and evaluation for single-source plants + rule-aware DSM evaluation  ·  Depends on: 12.2

Needed for "retrain for my plant" (Phase 13/16): a solar-only plant trains only a solar model, has no hybrid
copula, and its plant total is the solar series. Evaluation now prices deviations with the **operator's** rule
profile and contract rate, and also tunes the schedule level for the hybrid total of hybrid plants.

#### T12.5.1 — Small edits in three files  ✅ Tested
1. `ml/vidyut/features/framing.py`, last line of `frame_all`: replace
   `return {s: frame_source(ds, s, cfg, issues) for s in ("solar", "wind")}` with
   `return {s: frame_source(ds, s, cfg, issues) for s in cfg.sources}       # only the plant's sources`
2. `ml/vidyut/engines/alerts.py`, in `evaluate_alert_quality`: replace the two lines
   `for source in ("solar", "wind", "hybrid"):` / `df = preds_by_source[source]` with the single line
   `for source, df in preds_by_source.items():            # the plant's sources (+ hybrid for hybrid plants)`
3. `ml/vidyut/eval/report.py`: replace both `("solar", "wind")` loops with `cfg.sources`
   (`for s in cfg.sources:` and `... for s in cfg.sources}` in the `meta = {...}` line).

#### T12.5.2 — `ml/vidyut/engines/value_of_forecast.py` (adds `total_long`)  ✅ Tested
**FILE: `ml/vidyut/engines/value_of_forecast.py`** — ✅ Tested

````python
"""Value of forecast: plan the battery with each model's forecast, settle against ACTUAL generation.

Turns forecast accuracy into backup MWh, rupees and tCO2 — the key impact numbers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from vidyut.config import VidyutConfig
from vidyut.engines.dispatch import kpis, no_battery, plan, settle
from vidyut.engines.hybrid import combine
from vidyut.schema import QCOLS

KEYS = ["issue_time_utc", "target_time_utc", "lead_h"]


def hybrid_long(preds_solar: pd.DataFrame, preds_wind: pd.DataFrame, model: str, rho_by_day: dict[int, float],
                cfg: VidyutConfig, issue_hour: int | None = None, max_lead: int | None = None) -> pd.DataFrame:
    """Combine one model's solar and wind long predictions into hybrid quantiles + actual."""
    s = preds_solar[preds_solar["model"] == model]
    w = preds_wind[preds_wind["model"] == model]
    if issue_hour is not None:
        s = s[s["issue_time_utc"].dt.hour == issue_hour]
        w = w[w["issue_time_utc"].dt.hour == issue_hour]
    if max_lead is not None:
        s, w = s[s["lead_h"] <= max_lead], w[w["lead_h"] <= max_lead]
    m = s.merge(w, on=KEYS, suffixes=("_s", "_w"))
    rho = np.array([rho_by_day.get(int(d), 0.0) for d in m["cal_is_day_s"]])
    q = combine(m[[f"{c}_s" for c in QCOLS]].to_numpy(), m[[f"{c}_w" for c in QCOLS]].to_numpy(),
                cfg.capacity_mw("solar"), cfg.capacity_mw("wind"), rho, n_samples=500)
    out = m[KEYS].copy()
    out[list(QCOLS)] = q
    out["y"] = m["y_s"].to_numpy() + m["y_w"].to_numpy()
    out["cal_is_day"] = m["cal_is_day_s"].to_numpy()
    out["model"] = model
    return out.sort_values(KEYS).reset_index(drop=True)


def total_long(preds: dict[str, pd.DataFrame], model: str, rho_by_day: dict[int, float], cfg: VidyutConfig,
               issue_hour: int | None = None, max_lead: int | None = None) -> pd.DataFrame:
    """Plant-total long predictions for one model: hybrid_long() for a hybrid plant, else the single source."""
    if cfg.plant.type == "hybrid":
        return hybrid_long(preds["solar"], preds["wind"], model, rho_by_day, cfg, issue_hour, max_lead)
    p = preds[cfg.total_source]
    p = p[p["model"] == model]
    if issue_hour is not None:
        p = p[p["issue_time_utc"].dt.hour == issue_hour]
    if max_lead is not None:
        p = p[p["lead_h"] <= max_lead]
    return p[KEYS + list(QCOLS) + ["y", "cal_is_day", "model"]].sort_values(KEYS).reset_index(drop=True)


def run_value_of_forecast(hybrid_by_model: dict[str, pd.DataFrame], demand: pd.Series, cfg: VidyutConfig,
                          horizon_h: int = 24) -> pd.DataFrame:
    """Daily rolling plan (one issue per day), SoC carried forward from the settled result."""
    rows = []
    any_df = next(iter(hybrid_by_model.values()))
    strategies = {**hybrid_by_model, "perfect_foresight": any_df.assign(q50=any_df["y"], q10=any_df["y"])}
    for name, df in strategies.items():
        d = df[df["lead_h"] <= horizon_h]
        soc = None
        settled_all = []
        for _, g in d.groupby("issue_time_utc"):
            g = g.sort_values("lead_h")
            dem = demand.reindex(g["target_time_utc"]).to_numpy()
            res = plan(g["q50"].to_numpy(), dem, cfg.battery, cfg.costs, g["q10"].to_numpy(), soc,
                       index=pd.DatetimeIndex(g["target_time_utc"]))
            st = settle(res.schedule, g["y"].to_numpy(), cfg.costs)
            soc = float(st["soc_mwh"].iloc[-1])
            settled_all.append(st)
        k = kpis(pd.concat(settled_all), cfg.costs)
        rows.append({"strategy": name, **k})
    # reference: no battery at all
    d = any_df[any_df["lead_h"] <= horizon_h]
    nb = no_battery(d["y"].to_numpy(), demand.reindex(d["target_time_utc"]).to_numpy(), cfg.costs)
    rows.append({"strategy": "no_battery", **nb.kpis})
    return pd.DataFrame(rows)
````

#### T12.5.3 — `ml/vidyut/engines/impact.py`  ✅ Tested
DSM savings now count only the plant-total rows (summing solar + wind + hybrid would double count).
**FILE: `ml/vidyut/engines/impact.py`** — ✅ Tested

````python
"""Impact engine: turn value-of-forecast and DSM results into headline impact numbers."""
from __future__ import annotations

import pandas as pd

from vidyut.config import VidyutConfig


def impact_summary(vof: pd.DataFrame, cfg: VidyutConfig, dsm: pd.DataFrame | None = None,
                   ours: str = "ensemble", baseline: str = "persistence", days: float | None = None) -> dict:
    """Compare Vidyut (ensemble-planned) with persistence-planned dispatch over the test period."""
    v = vof.set_index("strategy")
    b, o = v.loc[baseline], v.loc[ours]
    backup_avoided = float(b["backup_mwh"] - o["backup_mwh"])
    out = {
        "period_days": days,
        "backup_avoided_mwh": round(backup_avoided, 1),
        "co2_avoided_t": round(backup_avoided * cfg.costs.emission_factor_t_per_mwh, 1),
        "curtailment_avoided_mwh": round(float(b["curtail_mwh"] - o["curtail_mwh"]), 1),
        "cost_saved_inr": round(float(b["cost_inr"] - o["cost_inr"]), 0),
        "battery_vs_no_battery_backup_avoided_mwh": round(float(v.loc["no_battery", "backup_mwh"] - o["backup_mwh"]), 1),
        "emission_factor_t_per_mwh": cfg.costs.emission_factor_t_per_mwh,
        "emission_factor_source": cfg.costs.emission_factor_source,
        "plant_capacity_mw": cfg.capacity_mw(cfg.total_source),
    }
    if dsm is not None and {"strategy", "charge_inr"} <= set(dsm.columns):
        tot = dsm[dsm["source"] == cfg.total_source] if "source" in dsm.columns else dsm   # plant total only
        d = tot.groupby("strategy")["charge_inr"].sum()
        if "persistence" in d and "vidyut_optimized" in d:
            out["dsm_charges_saved_inr"] = round(float(d["persistence"] - d["vidyut_optimized"]), 0)
    return out


def scale_to_capacity(summary: dict, target_mw: float) -> dict:
    """Linear extrapolation to a larger fleet — ALWAYS label as an extrapolation in UI/report."""
    f = target_mw / summary["plant_capacity_mw"]
    keys = ("backup_avoided_mwh", "co2_avoided_t", "curtailment_avoided_mwh", "cost_saved_inr", "dsm_charges_saved_inr")
    return {k: round(summary[k] * f, 1) for k in keys if k in summary} | {"target_mw": target_mw, "extrapolation": True}
````

#### T12.5.4 — `ml/vidyut/pipelines/cli.py`  ✅ Tested
`frame`/`train` use the plant's sources; `train` writes `artifacts/models/reference_config.yaml` (the artifacts
now describe that plant); `evaluate`/`report` read `reference_config()`; `build-dataset --synthetic` uses the
parametric demand shape (CI has no Mendeley files); includes `migrate-artifacts` from T10.2.4.
**FILE: `ml/vidyut/pipelines/cli.py`** — ✅ Tested

````python
"""Vidyut command line. Installed as the `vidyut` command (see ml/pyproject.toml [project.scripts]).

Commands (run in this order the first time):
  vidyut fetch-weather            # Open-Meteo -> data/interim/weather_*.parquet   (needs internet)
  vidyut build-dataset            # -> data/processed/dataset.parquet   (--synthetic for offline dev)
  vidyut frame                    # -> data/processed/framed_{solar,wind}.parquet
  vidyut train [--chronos-dir artifacts/chronos]   # models, ensemble, CQR -> artifacts/
  vidyut evaluate                 # engines (hybrid, trust, alerts, value-of-forecast, DSM, impact)
  vidyut report                   # docs/accuracy-report.md + plots
  vidyut forecast --mode replay   # one run -> artifacts/runs/<issue>/
  vidyut export-kaggle            # bundle for the Kaggle GPU notebooks
Imports are inside each command so the CLI works before later phases exist.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from vidyut.config import load_config, reference_config, write_reference_snapshot
from vidyut.paths import ARTIFACTS, CONFIG_DIR, DATA_DIR, DATA_INTERIM, DATA_PROCESSED, ensure_dirs

app = typer.Typer(add_completion=False, help="Vidyut forecasting pipeline")


@app.command("fetch-weather")
def fetch_weather(offline: bool = typer.Option(False, help="only use cached responses")) -> None:
    from vidyut.data.openmeteo import OpenMeteoClient
    from vidyut.data.weather_tables import build_weather_tables
    cfg = load_config()
    ensure_dirs()
    act, fx = build_weather_tables(cfg, OpenMeteoClient(offline=offline))
    typer.echo(f"actual {act.shape}, forecast {fx.shape} -> {DATA_INTERIM}")


@app.command("build-dataset")
def build_dataset_cmd(synthetic: bool = typer.Option(False, help="use synthetic weather (offline dev only)")) -> None:
    from vidyut.data.build_dataset import build_dataset
    from vidyut.data.quality import check_dataset
    from vidyut.data.weather_tables import build_weather_tables
    cfg = load_config()
    ensure_dirs()
    if synthetic:
        act, fx = build_weather_tables(cfg, synthetic=True)
    else:
        act = pd.read_parquet(DATA_INTERIM / "weather_actual.parquet")
        fx = pd.read_parquet(DATA_INTERIM / "weather_forecast.parquet")
    real_demand = None
    if cfg.demand.shape_source == "india_hourly" and not synthetic:   # CI/offline: parametric demand shape
        from vidyut.real.loaders import load_india_hourly
        real_demand = load_india_hourly()["demand_mw"]
    ds = build_dataset(cfg, act, fx, real_demand)
    problems = check_dataset(ds, cfg)
    if problems:
        typer.echo("QUALITY PROBLEMS:\n- " + "\n- ".join(problems))
        raise typer.Exit(code=1)
    typer.echo(f"dataset OK: {ds.shape} -> {DATA_PROCESSED / 'dataset.parquet'}")


@app.command()
def frame() -> None:
    from vidyut.data.build_dataset import load_dataset
    from vidyut.features.framing import frame_all
    cfg = load_config()
    for s, f in frame_all(load_dataset(), cfg).items():
        f.to_parquet(DATA_PROCESSED / f"framed_{s}.parquet")
        typer.echo(f"{s}: {f.shape} {f['split'].value_counts().to_dict()}")


@app.command()
def train(chronos_dir: Optional[Path] = typer.Option(None, help="folder with <source>_<model>.parquet from Kaggle"),
          chronos_in_ensemble: bool = typer.Option(False, "--chronos-in-ensemble/--no-chronos-in-ensemble",
                                                   help="include Chronos in ensemble (default: False)")
          ) -> None:
    from vidyut.pipelines.train import train_all
    cfg = load_config()
    frames = {s: pd.read_parquet(DATA_PROCESSED / f"framed_{s}.parquet") for s in cfg.sources}
    external = None
    if chronos_dir:
        external = {}
        for s in cfg.sources:
            ext_s = {}
            for p in sorted(chronos_dir.glob(f"{s}_*.parquet")):
                ext_s[p.stem.split("_", 1)[1]] = pd.read_parquet(p)
            for p in sorted(chronos_dir.glob(f"*_{s}.parquet")):
                ext_s.setdefault(p.stem.rsplit("_", 1)[0], pd.read_parquet(p))
            external[s] = ext_s
    params_file = CONFIG_DIR / "gbm_params.yaml"
    gbm_params = None
    if params_file.exists():                      # written by the tuning step (task T4.5.1)
        import yaml
        gbm_params = yaml.safe_load(params_file.read_text())
    train_all(frames, cfg, external, gbm_params=gbm_params, chronos_in_ensemble=chronos_in_ensemble)
    write_reference_snapshot(cfg)          # artifacts now describe THIS plant (vidyut.config.reference_config)
    typer.echo(f"models saved under {ARTIFACTS / 'models'}")


@app.command()
def evaluate() -> None:
    from vidyut.pipelines.evaluate import evaluate_all
    r = evaluate_all(reference_config())
    typer.echo(r["impact"])


@app.command()
def report() -> None:
    from vidyut.eval.report import write_reports
    write_reports(reference_config())
    typer.echo("docs/accuracy-report.md written")


@app.command()
def forecast(mode: str = typer.Option("replay", help="live | replay"),
             at: Optional[str] = typer.Option(None, help="replay 'now', e.g. 2026-05-10T00:00")) -> None:
    from vidyut.pipelines.forecast import run_forecast
    out = run_forecast(load_config(), mode, at)
    typer.echo(f"run written: {out}")


@app.command("export-kaggle")
def export_kaggle() -> None:
    """Bundle dataset + config + vidyut source for the Kaggle GPU notebooks (task T4.3.x / T4.4.x).

    Contains all splits because Chronos-2 must PREDICT val+test; fine-tuning code only ever reads the
    train/val date ranges (enforced in Chronos2Forecaster.finetune_lora).
    """
    from vidyut.paths import REPO_ROOT
    out = DATA_DIR / "kaggle_upload"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(DATA_PROCESSED / "dataset.parquet", out / "dataset.parquet")
    shutil.copy(CONFIG_DIR / "site.yaml", out / "site.yaml")
    shutil.copytree(REPO_ROOT / "ml" / "vidyut", out / "vidyut_src" / "vidyut",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for s in load_config().sources:
        f = pd.read_parquet(DATA_PROCESSED / f"framed_{s}.parquet", columns=["issue_time_utc", "split"])
        issues = f.loc[f["split"].isin(["val", "test"]), ["issue_time_utc"]].drop_duplicates()
        issues.to_parquet(out / f"issues_{s}.parquet")
    typer.echo(f"Kaggle bundle -> {out}\nUpload: kaggle datasets version -p {out} -m 'update' --dir-mode zip")


@app.command("migrate-artifacts")
def migrate_artifacts() -> None:
    """One-off after the TERRA -> Vidyut rename: re-save old artifacts with the new module names."""
    from vidyut.models.registry import migrate_legacy_artifacts
    for f in migrate_legacy_artifacts():
        typer.echo(f"migrated {f}")


@app.command()
def calibrate() -> None:
    from vidyut.real.calibrate_solar import run as cal_solar
    from vidyut.real.calibrate_state import run as cal_state
    from vidyut.real.calibrate_wind import run as cal_wind
    cal_solar()
    cal_wind()
    cal_state()
    typer.echo("calibration written to config/calibration/ and docs/calibration.md")


@app.command("real-benchmark")
def real_benchmark() -> None:
    from vidyut.real.benchmarks import run_all
    run_all()
    typer.echo("docs/real-data-results.md written")


if __name__ == "__main__":
    app()
````

#### T12.5.5 — `ml/vidyut/pipelines/evaluate.py`  ✅ Tested
**FILE: `ml/vidyut/pipelines/evaluate.py`** — ✅ Tested

````python
"""Evaluate the engines on held-out data and save the fitted engine objects.

Fits on the val_cal split (copula rho, trust weights, DSM schedule level) and reports on test:
hybrid band coverage, complementarity, trust-vs-error correlation, alert skill,
value of forecast (backup/cost/CO2), DSM charges, impact summary.
Outputs: artifacts/evaluation/*.json|csv, artifacts/models/hybrid/engines/<ver>/, docs/engine-results.md
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from vidyut.config import VidyutConfig, load_config
from vidyut.data.build_dataset import load_dataset
from vidyut.engines.alerts import alert_thresholds, evaluate_alert_quality
from vidyut.engines.dsm import choose_level, deviation_charges, schedule_at_level
from vidyut.engines.hybrid import complementarity, fit_copula_rho, pit
from vidyut.engines.impact import impact_summary
from vidyut.engines.trust import TrustModel, trust_features
from vidyut.engines.value_of_forecast import hybrid_long, run_value_of_forecast, total_long
from vidyut.eval.metrics import picp
from vidyut.logs import get_logger
from vidyut.models.downscale import downscale_solar, downscale_wind
from vidyut.models.registry import save_object
from vidyut.paths import ARTIFACTS, DOCS
from vidyut.rules import profile_for
from vidyut.schema import QCOLS

log = get_logger(__name__)
KEYS = ["issue_time_utc", "target_time_utc"]


def _load_preds(cfg: VidyutConfig) -> dict[str, pd.DataFrame]:
    return {s: pd.read_parquet(ARTIFACTS / "backtests" / s / "predictions.parquet") for s in cfg.sources}


def fit_rho(preds: dict[str, pd.DataFrame], cfg: VidyutConfig) -> dict[int, float]:
    s = preds["solar"].query("model == 'ensemble' and split == 'val_cal'")
    w = preds["wind"].query("model == 'ensemble' and split == 'val_cal'")
    m = s.merge(w, on=KEYS, suffixes=("_s", "_w"))
    u_s = pit(m["y_s"].to_numpy(), m[[f"{c}_s" for c in QCOLS]].to_numpy(), cfg.capacity_mw("solar"))
    u_w = pit(m["y_w"].to_numpy(), m[[f"{c}_w" for c in QCOLS]].to_numpy(), cfg.capacity_mw("wind"))
    return fit_copula_rho(u_s, u_w, m["cal_is_day_s"].to_numpy())


def fit_trust(p: pd.DataFrame, frame_hist: pd.Series, capacity: float) -> tuple[TrustModel, dict]:
    """p = ensemble rows (one source) for one split; frame_hist = hist_absresid_mean168 aligned to p."""
    spread = p["spread"].to_numpy() if "spread" in p else np.zeros(len(p))
    feats = trust_features(p, spread, p["lead_h"].to_numpy(), frame_hist.to_numpy() / capacity, capacity)
    err = np.abs(p["y"].to_numpy() - p["q50"].to_numpy()) / capacity
    return TrustModel().fit(feats, err), {}


def evaluate_all(cfg: VidyutConfig) -> dict:
    ds = load_dataset()
    preds = _load_preds(cfg)
    hybrid = cfg.plant.type == "hybrid"
    out_dir = ARTIFACTS / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {}

    # ---- spread (model disagreement) per row: std of member medians -------------------------
    for s, p in preds.items():
        members = p[p["model"].isin(["physics", "gbm", "chronos2_zs", "chronos2_ft"])]
        spread = members.groupby(KEYS)["q50"].std().rename("spread").reset_index()
        preds[s] = p.merge(spread, on=KEYS, how="left").fillna({"spread": 0.0})

    # ---- H1 hybrid (hybrid plants only) -------------------------------------------------------
    rho: dict[int, float] = {}
    if hybrid:
        rho = fit_rho(preds, cfg)
        hyb_test = hybrid_long(preds["solar"][preds["solar"]["split"] == "test"],
                               preds["wind"][preds["wind"]["split"] == "test"], "ensemble", rho, cfg)
        results["hybrid"] = {
            "rho_by_day": rho,
            "picp80": picp(hyb_test["y"].to_numpy(), hyb_test["q10"].to_numpy(), hyb_test["q90"].to_numpy()),
            "picp90": picp(hyb_test["y"].to_numpy(), hyb_test["q05"].to_numpy(), hyb_test["q95"].to_numpy()),
            "complementarity_actual": complementarity(ds["solar_mw"], ds["wind_mw"]),
        }

    # ---- H3 trust ----------------------------------------------------------------------------
    trust_models = {}
    for s, p in preds.items():
        hist = ds[f"{s}_mw"] - ds[f"phys0_{s}_mw"]
        absres = hist.abs().rolling(168, min_periods=1).mean()
        cap = cfg.capacity_mw(s)
        e = p[p["model"] == "ensemble"]
        vc, te = e[e["split"] == "val_cal"], e[e["split"] == "test"]
        tm, _ = fit_trust(vc, absres.reindex(vc["issue_time_utc"]).reset_index(drop=True), cap)
        feats = trust_features(te, te["spread"].to_numpy(), te["lead_h"].to_numpy(),
                               absres.reindex(te["issue_time_utc"]).to_numpy() / cap, cap)
        score = tm.score(feats)
        err = np.abs(te["y"].to_numpy() - te["q50"].to_numpy())
        day = te["cal_is_day"].to_numpy() == 1 if s == "solar" else np.ones(len(te), bool)
        rho_s = spearmanr(score[day], err[day]).statistic
        bins = pd.cut(score[day], [-1, 40, 70, 101], labels=["low", "medium", "high"])
        results[f"trust_{s}"] = {"spearman_score_vs_abs_error": float(rho_s),
                                 "mae_by_level": pd.Series(err[day]).groupby(bins, observed=False).mean().round(3).to_dict(),
                                 "weights": tm.weights.round(4).tolist()}
        trust_models[s] = tm

    # ---- alert quality & thresholds (solar, wind, hybrid; daily 00 UTC, 48 h horizon) ------
    thrs = alert_thresholds(ds, cfg)
    sources_test = {s: preds[s][preds[s]["split"] == "test"] for s in cfg.sources}
    if hybrid:
        sources_test["hybrid"] = hyb_test
    alerts_eval = evaluate_alert_quality(sources_test, cfg, thrs)
    total = cfg.total_source
    results["alerts"] = {"thresholds": thrs, **alerts_eval,
                         "low": alerts_eval[total]["low"], "high": alerts_eval[total]["high"]}

    # ---- value of forecast (H2) --------------------------------------------------------------
    hour = cfg.forecast.dayahead_issue_hour_utc
    test_preds = {s: p[p["split"] == "test"] for s, p in preds.items()}
    hyb_by_model = {m: total_long(test_preds, m, rho, cfg, issue_hour=hour, max_lead=24)
                    for m in ("persistence", "physics", "gbm", "ensemble")}
    vof = run_value_of_forecast(hyb_by_model, ds["demand_mw"], cfg, horizon_h=24)
    vof.to_csv(out_dir / "value_of_forecast.csv", index=False)
    results["value_of_forecast"] = vof.to_dict(orient="records")

    # ---- DSM (H5): rules from the OPERATOR's state (Phase 12) ------------------------------------
    levels, dsm, dsm_info = evaluate_dsm(preds, cfg, rho)
    dsm.to_csv(out_dir / "dsm.csv", index=False)
    results["dsm"] = dsm_info

    # ---- impact -------------------------------------------------------------------------------
    days = hyb_by_model["ensemble"]["issue_time_utc"].nunique()
    results["impact"] = impact_summary(vof, cfg, dsm, days=days)

    save_object({"rho_by_day": rho, "trust": trust_models, "dsm_level": levels, "alert_thresholds": thrs},
                "hybrid", "engines", {"config_hash": cfg.hash(), "results": results})
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    write_engine_doc(results)
    log.info("evaluation done: %s", json.dumps(results["impact"], default=str))
    return results


def evaluate_dsm(preds: dict[str, pd.DataFrame], cfg: VidyutConfig, rho: dict[int, float]
                 ) -> tuple[dict[str, float], pd.DataFrame, dict]:
    """Tune the day-ahead schedule level on val_cal and price strategies on test, with the OPERATOR's rule
    profile and contract rate (plant.yaml). Returns (levels, table, results['dsm'] dict)."""
    hour = cfg.forecast.dayahead_issue_hour_utc
    market_cfg = load_config()                       # plant.yaml decides state / rule profile / PPA rate
    prof, why = profile_for(market_cfg)
    cr = market_cfg.market.contract_rate_inr_per_kwh
    dsm_rows, levels = [], {}
    split_preds = {s: {sp: preds[s][preds[s]["split"] == sp] for sp in ("val_cal", "test")} for s in cfg.sources}
    for s in cfg.output_sources:                     # + "hybrid" for hybrid plants
        cap = cfg.capacity_mw(s)
        if s == "solar":
            ds_fn = lambda x, c=cap: downscale_solar(x, cfg.site, c)  # noqa: E731
        else:   # wind and hybrid: smooth interpolation (hybrid = documented approximation)
            ds_fn = lambda x, c=cap: downscale_wind(x, c)  # noqa: E731
        blocks = {}
        for split in ("val_cal", "test"):
            for model in ("persistence", "ensemble"):
                if s == "hybrid":
                    p = hybrid_long(split_preds["solar"][split], split_preds["wind"][split], model, rho, cfg,
                                    issue_hour=hour)
                else:
                    p = split_preds[s][split]
                    p = p[(p["model"] == model) & (p["issue_time_utc"].dt.hour == hour)]
                p = p[p["lead_h"].between(19, 42)].sort_values(KEYS)
                qb, ab = [], []
                for _, gi in p.groupby("issue_time_utc"):
                    idx = pd.DatetimeIndex(gi["target_time_utc"])
                    qb.append(np.column_stack([ds_fn(pd.Series(gi[c].to_numpy(), index=idx)).to_numpy() for c in QCOLS]))
                    ab.append(ds_fn(pd.Series(gi["y"].to_numpy(), index=idx)).to_numpy())
                if qb:
                    blocks[(split, model)] = (np.vstack(qb), np.concatenate(ab))
        level, _ = choose_level(*blocks[("val_cal", "ensemble")], cap, s, prof, cr)
        levels[s] = level
        qt, at = blocks[("test", "ensemble")]
        qp, ap = blocks[("test", "persistence")]
        for strat, sched, act in (("persistence", qp[:, 2], ap), ("vidyut_p50", qt[:, 2], at),
                                  ("vidyut_optimized", schedule_at_level(qt, level), at)):
            ch = deviation_charges(sched, act, cap, s, prof, cr)
            dsm_rows.append({"source": s, "strategy": strat, "charge_inr": float(ch["charge_inr"].sum()),
                             "blocks_outside_tolerance_pct": float(100 * (ch["beyond_tolerance_pct"] > 0).mean())})
    dsm = pd.DataFrame(dsm_rows)
    info = {"illustrative_rates": prof.status != "verified", "profile": prof.summary(), "profile_reason": why,
            "contract_rate_inr_per_kwh": cr, "chosen_level": levels, "table": dsm.to_dict(orient="records")}
    return levels, dsm, info


def retune_dsm(cfg: VidyutConfig) -> dict:
    """Light re-tune after the operator changed state / rule profile / PPA rate (setup wizard, Phase 13).

    Re-uses the saved backtests and copula instead of the full evaluate_all (which needs ~650 MB and does
    not fit a 512 MB free instance). Saves a new engines version and updates results.json['dsm'].
    """
    from vidyut.models.registry import load_object
    eng = load_object("hybrid", "engines@latest")
    preds = _load_preds(cfg)
    levels, dsm, info = evaluate_dsm(preds, cfg, eng.get("rho_by_day", {}))
    out_dir = ARTIFACTS / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    dsm.to_csv(out_dir / "dsm.csv", index=False)
    rpath = out_dir / "results.json"
    results = json.loads(rpath.read_text()) if rpath.exists() else {}
    results["dsm"] = info
    if "impact" in results:
        results["impact"].pop("dsm_charges_saved_inr", None)
        d = dsm[dsm["source"] == cfg.total_source].groupby("strategy")["charge_inr"].sum()
        if "persistence" in d and "vidyut_optimized" in d:
            results["impact"]["dsm_charges_saved_inr"] = round(float(d["persistence"] - d["vidyut_optimized"]), 0)
    rpath.write_text(json.dumps(results, indent=2, default=str))
    save_object({**eng, "dsm_level": levels}, "hybrid", "engines", {"config_hash": cfg.hash(), "results": results,
                                                                    "retuned": True})
    log.info("DSM schedule level re-tuned for %s: %s", info["profile"]["id"], levels)
    return info


def write_engine_doc(r: dict) -> None:
    lines = ["# Engine results (test split)", "", "Generated by `vidyut evaluate`. Do not edit by hand.", ""]
    if "hybrid" in r:
        h = r["hybrid"]
        lines += ["## Hybrid band", f"- PICP80 = {h['picp80']:.3f}, PICP90 = {h['picp90']:.3f}",
                  f"- Copula rho (night/day) = {h['rho_by_day']}", ""]
    lines += ["## Trust"]
    for s in ("solar", "wind"):
        if f"trust_{s}" not in r:
            continue
        t = r[f"trust_{s}"]
        lines.append(f"- {s}: Spearman(score, |error|) = {t['spearman_score_vs_abs_error']:.3f}; "
                     f"MAE by level = {t['mae_by_level']}")
    lines += ["", "## Value of forecast (day-ahead plans settled on actual)", "",
              pd.DataFrame(r["value_of_forecast"]).to_markdown(index=False), "",
              "## Deviation Shield" + (" (ILLUSTRATIVE rates)" if r["dsm"]["illustrative_rates"] else ""), "",
              pd.DataFrame(r["dsm"]["table"]).to_markdown(index=False), "",
              "## Alert quality (test split)", "",
              "Data-driven thresholds derived from training split quantiles (P10 low generation, P90 high generation, "
              "P95 hourly ramp; solar daylight-only for generation thresholds). Deduplicated across daily 00:00 UTC "
              "issue times (48 h horizon).", ""]
    alert_rows = []
    thrs = r.get("alerts", {}).get("thresholds", {})
    for s in ("solar", "wind", "hybrid"):
        if s not in r.get("alerts", {}):
            continue
        s_thrs = thrs.get(s, {})
        s_res = r.get("alerts", {}).get(s, {})
        for kind, kind_label in (("low", "LOW"), ("high", "HIGH")):
            k_res = s_res.get(kind, {})
            thr_mw = s_thrs.get(f"{kind}_mw", float("nan"))
            alert_rows.append({
                "source": s,
                "alert": kind_label,
                "threshold_mw": round(thr_mw, 2),
                "precision": round(k_res.get("precision", 0.0), 3),
                "recall": round(k_res.get("recall", 0.0), 3),
                "alert_hours": k_res.get("alert_hours", 0),
                "event_hours": k_res.get("event_hours", 0),
            })
    lines += [pd.DataFrame(alert_rows).to_markdown(index=False), "",
              "## Impact", "",
              "```json", json.dumps(r["impact"], indent=2), "```"]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "engine-results.md").write_text("\n".join(lines))
````

#### T12.5.6 — Run it  📝
```bash
vidyut evaluate        # prints the impact dict; results.json now has dsm.profile, profile_reason, contract_rate
python -c "import json; d=json.load(open('artifacts/evaluation/results.json'))['dsm']; print(d['profile']['id'], d['chosen_level'])"
```
Expected with the default MP plant: `madhya_pradesh_mperc_2018 {'solar': …, 'wind': …, 'hybrid': …}`.

#### T12.5.7 — Prove a solar-only retrain works (into a scratch folder)  📝
```bash
printf 'plant:\n  type: solar\n  name: Solar retrain test\n' > config/plant.yaml
export VIDYUT_ARTIFACTS_DIR=/tmp/art_solar
vidyut frame && vidyut train && vidyut evaluate && vidyut forecast --mode replay
ls /tmp/art_solar/models          # hybrid  reference_config.yaml  solar   (no wind)
unset VIDYUT_ARTIFACTS_DIR; rm config/plant.yaml; git checkout docs   # report wrote docs/; restore them
```
About 2 minutes on the synthetic dataset. (`vidyut frame` writes `data/processed/framed_solar.parquet`; re-run
`vidyut frame` without the overlay afterwards if you train the reference again.)

---

### 12.6 Daily report engine and PDF  ·  Depends on: 12.2

#### T12.6.1 — Add `reportlab` to `ml/pyproject.toml`  ✅ Tested
In `dependencies`, after `"tabulate>=0.9",` add `"reportlab>=4.0",          # daily report PDF (Phase 12/14)`, then
`pip install -e ml`.

#### T12.6.2 — `ml/vidyut/engines/daily_report.py`  ✅ Tested
Inputs are all 15-min series of one IST day: Rev-0 quantiles, actual, Rev-0 and final schedule, revision decisions,
alerts. Output: energy, accuracy (MAE, RMSE, nMAE, 80 % band coverage), deviation (blocks outside tolerance, ₹,
"if no revision", "saved by revisions", the 5 most expensive blocks explained), revisions, alerts, 96 block rows.
`is_estimate: true` is always set — the official account is the SLDC's.
**FILE: `ml/vidyut/engines/daily_report.py`** — ✅ Tested

````python
"""Daily accuracy & estimated-deviation report for one IST day (on-screen JSON + PDF).

It is an ESTIMATE made by the plant: the official DSM account is issued by the SLDC/RLDC. The report lets
the operator check that account and see what forecasting, revisions and alerts did for the day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from vidyut.engines.dsm import block_numbers, deviation_charges, explain_block
from vidyut.eval.metrics import mae, picp, rmse
from vidyut.rules import RuleProfile
from vidyut.schema import QCOLS


def build_daily_report(day_ist: str, plant_name: str, source: str, avc_mw: float, profile: RuleProfile,
                       contract_rate: float, q_blocks: pd.DataFrame, actual_blocks: pd.Series,
                       schedule_rev0: pd.Series, schedule_final: pd.Series, revisions: list[dict],
                       alerts: list[dict], profile_reason: str = "") -> dict:
    """All block series are indexed by block END (UTC) and cover the 96 blocks of `day_ist`."""
    idx = q_blocks.index
    act = actual_blocks.reindex(idx).to_numpy(float)
    q = q_blocks[list(QCOLS)].to_numpy()
    s0 = schedule_rev0.reindex(idx).to_numpy(float)
    sf = schedule_final.reindex(idx).to_numpy(float)
    ch_final = deviation_charges(sf, act, avc_mw, source, profile, contract_rate)
    ch_rev0 = deviation_charges(s0, act, avc_mw, source, profile, contract_rate)
    blocks = block_numbers(idx)
    worst = ch_final["charge_inr"].to_numpy().argsort()[::-1][:5]
    def label(i: int) -> str:
        start = (idx[i] - pd.Timedelta(minutes=15)).tz_convert("Asia/Kolkata")
        return f"Block {int(blocks[i])} ({start:%H:%M} IST): "

    worst_expl = [explain_block(float(sf[i]), float(act[i]), avc_mw, source, profile, contract_rate, label=label(i))
                  for i in worst if ch_final["charge_inr"].iloc[i] > 0]
    accepted = [r for r in revisions if r.get("status") == "accepted"]
    alert_counts = pd.Series([a["type"] for a in alerts]).value_counts().to_dict() if alerts else {}
    tol = profile.tolerance_pct[source]
    return {
        "date_ist": day_ist, "plant": plant_name, "source": source, "capacity_mw": avc_mw,
        "profile": profile.summary(), "profile_reason": profile_reason, "contract_rate_inr_per_kwh": contract_rate,
        "is_estimate": True,
        "energy": {"forecast_p50_mwh": round(float(q[:, 2].sum() * 0.25), 2),
                   "actual_mwh": round(float(np.nansum(act) * 0.25), 2),
                   "scheduled_final_mwh": round(float(sf.sum() * 0.25), 2)},
        "accuracy": {"mae_mw": round(mae(act, q[:, 2]), 3), "rmse_mw": round(rmse(act, q[:, 2]), 3),
                     "nmae_pct": round(100 * mae(act, q[:, 2]) / avc_mw, 2),
                     "band80_coverage": round(picp(act, q[:, 1], q[:, 3]), 3)},
        "deviation": {"tolerance_pct": tol,
                      "blocks_outside_tolerance": int((ch_final["beyond_tolerance_pct"] > 0).sum()),
                      "estimated_charges_inr": round(float(ch_final["charge_inr"].sum()), 2),
                      "charges_if_no_revision_inr": round(float(ch_rev0["charge_inr"].sum()), 2),
                      "saved_by_revisions_inr": round(float(ch_rev0["charge_inr"].sum() - ch_final["charge_inr"].sum()), 2),
                      "worst_blocks": worst_expl},
        "revisions": {"recommended": len(revisions), "accepted": len(accepted),
                      "rejected": len([r for r in revisions if r.get("status") == "rejected"]),
                      "items": [{k: r.get(k) for k in ("id", "status", "effective_from_block", "expected_saving_inr",
                                                        "reason", "decided_by", "decision_note")} for r in revisions]},
        "alerts": {"count": len(alerts), "by_type": alert_counts},
        "blocks": pd.DataFrame({"block_no": blocks, "p10": q[:, 1], "p50": q[:, 2], "p90": q[:, 3], "actual": act,
                                "schedule_rev0": s0, "schedule_final": sf,
                                "charge_inr": ch_final["charge_inr"].to_numpy()}).round(3).to_dict(orient="records"),
    }
````

#### T12.6.3 — `ml/vidyut/eval/pdf.py`  ✅ Tested
**FILE: `ml/vidyut/eval/pdf.py`** — ✅ Tested

````python
"""Render the daily report dict (engines/daily_report.py) to a PDF with reportlab + one matplotlib chart."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402


def _chart(rep: dict) -> io.BytesIO:
    b = pd.DataFrame(rep["blocks"])
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    ax.fill_between(b["block_no"], b["p10"], b["p90"], alpha=0.25, label="P10–P90 forecast")
    ax.plot(b["block_no"], b["actual"], lw=1.2, label="actual", color="black")
    ax.step(b["block_no"], b["schedule_final"], where="mid", lw=1.2, label="final schedule")
    ax.step(b["block_no"], b["schedule_rev0"], where="mid", lw=0.8, ls="--", label="day-ahead (Rev 0)")
    ax.set_xlabel("15-min block (IST)")
    ax.set_ylabel("MW")
    ax.legend(fontsize=7, ncol=4, loc="upper left")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf


def _table(rows: list[list], widths: list[float]) -> Table:
    t = Table(rows, colWidths=[w * cm for w in widths])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e4")),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def render_daily_pdf(rep: dict) -> bytes:
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=8, leading=10)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title=f"Vidyut daily report {rep['date_ist']}")
    e, d, a, rv = rep["energy"], rep["deviation"], rep["accuracy"], rep["revisions"]
    prof = rep["profile"]
    story = [
        Paragraph(f"Vidyut — Daily accuracy & estimated deviation report — {rep['date_ist']}", styles["Title"]),
        Paragraph(f"Plant: {rep['plant']} · schedule: {rep['source']} · capacity {rep['capacity_mw']:.0f} MW", small),
        Paragraph(f"Rule profile: {prof['name']} (status: {prof['status']}) · contract rate "
                  f"₹{rep['contract_rate_inr_per_kwh']:.2f}/kWh. ESTIMATE — the official DSM account is issued by the "
                  "load despatch centre.", small),
        Spacer(1, 0.3 * cm),
        _table([["Energy forecast (P50)", "Actual", "Final schedule", "MAE", "nMAE", "80% band coverage"],
                [f"{e['forecast_p50_mwh']:.1f} MWh", f"{e['actual_mwh']:.1f} MWh", f"{e['scheduled_final_mwh']:.1f} MWh",
                 f"{a['mae_mw']:.2f} MW", f"{a['nmae_pct']:.1f}%", f"{100 * a['band80_coverage']:.0f}%"]],
               [3.2, 2.6, 2.8, 2.2, 2.0, 3.2]),
        Spacer(1, 0.3 * cm),
        _table([["Blocks outside ±tolerance", "Estimated charges", "If no revision", "Saved by revisions",
                 "Revisions (accepted / recommended)"],
                [f"{d['blocks_outside_tolerance']} of 96 (±{d['tolerance_pct']:g}%)", f"₹{d['estimated_charges_inr']:,.0f}",
                 f"₹{d['charges_if_no_revision_inr']:,.0f}", f"₹{d['saved_by_revisions_inr']:,.0f}",
                 f"{rv['accepted']} / {rv['recommended']}"]],
               [3.6, 3.0, 2.8, 3.0, 3.6]),
        Spacer(1, 0.3 * cm),
        Image(_chart(rep), width=18 * cm, height=6.7 * cm),
        Paragraph("Most expensive blocks — charge explanation", styles["Heading3"]),
    ]
    for w in d["worst_blocks"] or [{"steps": ["No block was charged today."]}]:
        story.append(Paragraph("<br/>".join(w["steps"]), small))
        story.append(Spacer(1, 0.15 * cm))
    if rv["items"]:
        story.append(Paragraph("Revisions", styles["Heading3"]))
        rows = [["ID", "Status", "From block", "Expected saving", "Reason"]]
        rows += [[r["id"], r["status"], str(r["effective_from_block"]), f"₹{(r['expected_saving_inr'] or 0):,.0f}",
                  Paragraph(str(r["reason"])[:160], small)] for r in rv["items"]]
        story.append(_table(rows, [4.2, 1.8, 1.8, 2.4, 7.0]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"Alerts: {rep['alerts']['count']} {rep['alerts']['by_type']}", small))
    story.append(Paragraph("Weather data by Open-Meteo.com (CC BY 4.0). Plant: Vidyut virtual digital twin.", small))
    doc.build(story)
    return buf.getvalue()
````

#### T12.6.4 — Simulator and report tests  ✅ Tested
**FILE: `ml/tests/test_penalty_sim_report.py`** — ✅ Tested

````python
import numpy as np
import pandas as pd

from vidyut.engines.daily_report import build_daily_report
from vidyut.engines.penalty_sim import BlockEdit, SimInput, simulate
from vidyut.eval.pdf import render_daily_pdf
from vidyut.rules import load_profile

DAY = pd.date_range("2026-05-10 00:15", periods=96, freq="15min", tz="Asia/Kolkata").tz_convert("UTC")
Q = pd.DataFrame({"q05": 14.0, "q10": 16.0, "q50": 20.0, "q90": 24.0, "q95": 26.0}, index=DAY)


def test_simulator_harsher_rules_cost_more():
    p = load_profile("cerc_2026")
    base = simulate(SimInput(), p, 2.70, Q, 90.0)
    harsh = simulate(SimInput(penalty_scale=2.0, tolerance_override_pct=2.0), p, 2.70, Q, 90.0)
    assert harsh["total_charge_inr"] > base["total_charge_inr"] >= 0
    assert base["mode"] == "expected" and len(base["blocks"]) == 96


def test_simulator_manual_edit_and_realised():
    p = load_profile("gujarat_gerc_2019")
    actual = pd.Series(20.0, index=DAY)
    r = simulate(SimInput(edits=[BlockEdit(from_block=40, to_block=50, mw=35.0)]), p, 2.70, Q, 90.0, actual)
    assert r["mode"] == "realised" and r["total_charge_inr"] > 0
    assert r["blocks"][44]["schedule_mw"] == 35.0


def test_daily_report_and_pdf():
    p = load_profile("cerc_2026")
    actual = pd.Series(np.linspace(10, 30, 96), index=DAY)
    rev0 = pd.Series(28.0, index=DAY)
    final = rev0.copy()
    final.iloc[48:] = 22.0
    rep = build_daily_report("2026-05-10", "Test plant", "hybrid", 90.0, p, 2.70, Q, actual, rev0, final,
                             [{"id": "REV-1", "status": "accepted", "effective_from_block": 49, "expected_saving_inr": 900,
                               "reason": "test"}], [{"type": "LOW_GENERATION"}])
    assert rep["revisions"]["accepted"] == 1 and rep["is_estimate"]
    pdf = render_daily_pdf(rep)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000
````

Check: `cd ml && pytest -q` → **65 passed**; `ruff check ml` clean.

**Who reads the report?** (open question from the planning chat — answer it during the demo prep, T17.2.3): plant
manager (daily performance), QCA (checks the SLDC's DSM bill), finance (₹ provisions), owner/investor (monthly
roll-up). The PDF is written for the plant manager and the QCA; adjust wording after you ask one real person.

---

## PHASE 13 — Backend: operator workflow, reports, setup and notifications API (Day 3–4)

Goal: the API in §D, backed by tables that survive restarts (decision B2) and a single run-producing function
used by the local scheduler, the production cron and the setup wizard (decision B3).

New backend modules:
```
backend/app/
  db/models.py            + ScheduleVersion, Recommendation, EventLog, Contact, AppState, session(), log_event(), get/set_state()
  services/jobs.py        produce_run(): forecast -> DB -> workflow -> SSE (one lock; replay clock in AppState)
  services/schedule.py    day-ahead proposal, revision evaluation, decide(), virtual_now()
  services/notify.py      WhatsApp: console | twilio | meta; opt-in, quiet hours, de-duplication; YES/NO replies
  services/reports.py     daily report (from DB + dataset), PDF
  services/setup.py       wizard: options, apply (plant.yaml + DB copy + contacts), refresh/retune job, retrain
  api/routes/{workflow,jobs,dsm,reports,setup,notify}.py
  scheduler.py            local APScheduler -> jobs.produce_run
```

---

### 13.1 Dependencies and settings  ·  Owner: Dev A  ·  Depends on: Phase 12

#### T13.1.1 — `backend/pyproject.toml`  ✅ Tested
Adds `httpx` (WhatsApp providers, GitHub dispatch) and `python-multipart` (Twilio posts form data).
**FILE: `backend/pyproject.toml`** — ✅ Tested

````toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "vidyut-backend"
version = "0.1.0"
requires-python = ">=3.10"
# NOTE: install the ML package first:  pip install -e "ml[dev]"   (provides the `vidyut` import)
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "sqlmodel>=0.0.16",
  "apscheduler>=3.10,<4",
  "sse-starlette>=2.0",
  "psycopg[binary]>=3.1",
  "httpx>=0.27",             # WhatsApp providers + GitHub retrain dispatch (Phases 16-17)
  "python-multipart>=0.0.9", # Twilio webhook posts form data (Phase 17)
]

[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27", "ruff>=0.5"]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.ruff]
line-length = 110

[tool.pytest.ini_options]
testpaths = ["tests"]
````
Then `pip install -e "backend[dev]"`.

#### T13.1.2 — `backend/app/settings.py`  ✅ Tested
**FILE: `backend/app/settings.py`** — ✅ Tested

````python
"""Backend settings from environment variables prefixed VIDYUT_ (see backend/.env.example)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIDYUT_", env_file=".env", extra="ignore")

    mode: Literal["live", "replay"] = "replay"
    replay_start: str = "2026-04-10T00:00"
    replay_step_hours: int = 6
    schedule_minutes: int = 60
    scheduler_enabled: bool = True
    cors_origins: str = "http://localhost:3000"
    db_url: str = "sqlite:///./vidyut.db"
    version: str = "0.2.0"

    # Phase 14 — operator workflow
    replay_autoaccept_dayahead: bool = False   # demo helper: auto-submit day-ahead proposals in replay
    job_token: str = ""                        # secret for POST /jobs/tick (GitHub Actions cron); empty = endpoint off

    # Phase 16 — plant setup
    setup_synthetic_weather: bool = False      # local retrain uses synthetic weather (offline demos only)
    retrain_mode: Literal["local", "github", "off"] = "local"   # local thread | GitHub Actions | disabled
    github_repo: str = "OVERxPOWERED/AGNITIA-TERRA06"
    github_token: str = ""                     # fine-grained PAT: Actions read/write on github_repo (github mode)

    # Phase 17 — WhatsApp: console | twilio | meta
    public_app_url: str = "http://localhost:3000"   # used in message links
    public_api_url: str = "http://localhost:8000"   # this API's public URL (Twilio signs the webhook URL)
    notify_provider: Literal["console", "twilio", "meta"] = "console"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"   # Twilio sandbox number
    twilio_content_sid_alert: str = ""         # optional approved template; empty = free-form (24 h session)
    meta_token: str = ""
    meta_phone_number_id: str = ""
    meta_graph_version: str = "v25.0"
    meta_template_alert: str = "vidyut_alert"
    meta_template_revision: str = "vidyut_revision"
    meta_template_lang: str = "en"
    meta_verify_token: str = "vidyut-verify"   # echoed back by GET /webhooks/meta during setup
    meta_app_secret: str = ""                  # verifies X-Hub-Signature-256 on POST /webhooks/meta
    webhook_verify_signatures: bool = True     # set false only in tests

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    from vidyut.compat import alias_legacy_env
    alias_legacy_env()                         # old TERRA_* variables still work after the rename
    return Settings()
````

#### T13.1.3 — `backend/.env.example`  ✅ Tested
**FILE: `backend/.env.example`** — ✅ Tested

````bash
# Copy to backend/.env and adjust. All variables are optional. (Old TERRA_* names still work — Phase 10.)
VIDYUT_MODE=replay                 # live | replay
VIDYUT_REPLAY_START=2026-04-10T00:00   # replay: first virtual "now" (UTC)
VIDYUT_REPLAY_STEP_HOURS=6         # replay: virtual hours advanced per run
VIDYUT_SCHEDULE_MINUTES=60         # how often the in-process job runs (local dev)
VIDYUT_SCHEDULER_ENABLED=true      # false on Render; GitHub Actions calls POST /jobs/tick instead
VIDYUT_CORS_ORIGINS=http://localhost:3000
VIDYUT_DB_URL=sqlite:///./vidyut.db
# VIDYUT_ARTIFACTS_DIR / VIDYUT_DATA_DIR default to <repo>/artifacts and <repo>/data

# --- Phase 14: operator workflow -------------------------------------------------------------
VIDYUT_JOB_TOKEN=                  # secret for POST /jobs/tick (empty = endpoint disabled)
VIDYUT_REPLAY_AUTOACCEPT_DAYAHEAD=false   # demo helper: accept day-ahead proposals automatically

# --- Phase 16: plant setup -------------------------------------------------------------------
VIDYUT_RETRAIN_MODE=local          # local (thread on this machine) | github (Actions) | off
VIDYUT_SETUP_SYNTHETIC_WEATHER=false   # local retrain without internet (numbers not reportable)
VIDYUT_GITHUB_REPO=OVERxPOWERED/AGNITIA-TERRA06
VIDYUT_GITHUB_TOKEN=

# --- Phase 17: WhatsApp ----------------------------------------------------------------------
VIDYUT_PUBLIC_APP_URL=http://localhost:3000
VIDYUT_PUBLIC_API_URL=http://localhost:8000
VIDYUT_NOTIFY_PROVIDER=console     # console | twilio | meta
VIDYUT_TWILIO_ACCOUNT_SID=
VIDYUT_TWILIO_AUTH_TOKEN=
VIDYUT_TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
VIDYUT_META_TOKEN=
VIDYUT_META_PHONE_NUMBER_ID=
VIDYUT_META_APP_SECRET=
VIDYUT_META_VERIFY_TOKEN=vidyut-verify
````

---

### 13.2 Database tables  ·  Depends on: 13.1

`SQLModel.metadata.create_all` (already called in `engine()`) creates the new tables on SQLite **and** Neon at the
next start; existing tables are untouched, so no migration tool is needed. Column notes: `blocks_json` holds the 96
block MW values; `quantiles_json` (Rev 0 only) keeps the forecast quantiles behind the day-ahead schedule so the
daily report never depends on a run folder that a redeploy deleted.

#### T13.2.1 — `backend/app/db/models.py`  ✅ Tested
**FILE: `backend/app/db/models.py`** — ✅ Tested

````python
"""Database models and connections (SQLModel).

Supports SQLite (default) and Postgres (via psycopg3).
Gracefully degrades to local SQLite if configured Postgres is unreachable.

Forecast numbers stay in Parquet run folders. The database holds everything the operator DOES and everything
that must survive a restart of a free-tier host (whose disk is wiped on every deploy):
  RunRow, AlertRow            forecast runs and their alerts (Phase 6)
  ScheduleVersion             submitted schedules per IST day: Rev 0 = day-ahead, 1.. = revisions (Phase 14)
  Recommendation              day-ahead proposals and revision recommendations + the operator decision
  EventLog                    explainability log: refreshes, triggers, decisions, WhatsApp messages
  Contact                     WhatsApp recipients with opt-in (Phase 17)
  AppState                    small key/value store: plant setup YAML, replay clock (Phase 14/16)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, text
from sqlmodel import Field, Session, SQLModel, create_engine, select
from vidyut.paths import ARTIFACTS

from app.settings import get_settings

log = logging.getLogger(__name__)

_engine: Engine | None = None


class RunRow(SQLModel, table=True):
    name: str = Field(primary_key=True)          # folder name, e.g. 20260410T00
    issue_time_utc: str
    mode: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    n_alerts: int = 0


class AlertRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str
    source: str
    start_utc: str
    end_utc: str
    severity: str
    probability: float
    magnitude_mw: float
    message: str
    issue_time_utc: str
    acknowledged: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleVersion(SQLModel, table=True):
    """One submitted schedule for an IST day. revision_no 0 = day-ahead; 1.. = intraday revisions."""
    id: int | None = Field(default=None, primary_key=True)
    ist_date: str = Field(index=True)            # "2026-04-11"
    source: str = "hybrid"                       # the plant total: hybrid | solar | wind
    revision_no: int
    effective_from_block: int = 1
    run_name: str = ""                           # forecast run the schedule came from
    recommendation_id: str = ""
    profile_id: str = ""
    blocks_json: str                             # {"block_end_utc": [...96], "mw": [...96]}
    quantiles_json: str = ""                     # Rev 0 only: {"block_end_utc": [...], "q05": [...], ... "q95": [...]}
    submitted_by: str = ""
    created_at: datetime = Field(default_factory=_now)

    def series(self):
        import pandas as pd
        d = json.loads(self.blocks_json)
        return pd.Series(d["mw"], index=pd.DatetimeIndex(pd.to_datetime(d["block_end_utc"], utc=True)))

    def quantiles(self):
        """Rev 0 forecast quantiles (q05..q95) per block, or None for revisions / old rows."""
        import pandas as pd
        if not self.quantiles_json:
            return None
        d = json.loads(self.quantiles_json)
        idx = pd.DatetimeIndex(pd.to_datetime(d.pop("block_end_utc"), utc=True))
        return pd.DataFrame(d, index=idx)


class Recommendation(SQLModel, table=True):
    id: str = Field(primary_key=True)            # DA-<day>-<run> or REV-<day>-<nn>-<hash>
    kind: str = "revision"                       # day_ahead | revision
    ist_date: str = Field(index=True)
    source: str = "hybrid"
    status: str = Field(default="pending", index=True)   # pending | accepted | rejected | superseded
    run_name: str = ""
    payload_json: str                            # Evaluation.to_dict() or the day-ahead proposal
    created_at: datetime = Field(default_factory=_now)
    decided_at: datetime | None = None
    decided_by: str = ""
    decision_note: str = ""

    def payload(self) -> dict:
        return json.loads(self.payload_json)


class EventLog(SQLModel, table=True):
    """Explainability log shown in the dashboard: every refresh, recommendation, decision and message."""
    id: int | None = Field(default=None, primary_key=True)
    ts_utc: str = Field(index=True)              # virtual time in replay, real time in live
    kind: str = Field(index=True)                # refresh | recommendation | accepted | rejected | superseded |
    #                                              day_ahead_proposed | day_ahead_submitted | whatsapp | setup | job
    title: str
    detail_json: str = "{}"
    ref_id: str = Field(default="", index=True)


class Contact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    role: str = "operator"                       # operator | manager | qca
    whatsapp: str                                # E.164 without spaces, e.g. +919812345678
    opt_in: bool = False                         # WhatsApp policy: only message people who opted in
    min_severity: str = "warning"                # info | warning | critical
    receive_revisions: bool = True
    receive_reports: bool = True


class AppState(SQLModel, table=True):
    """Tiny key/value store for state that must survive restarts (plant_yaml, replay_clock_utc)."""
    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=_now)


def normalize_db_url(raw_url: str) -> str:
    """Normalize postgres:// and postgresql:// to postgresql+psycopg:// preserving query params."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _create_engine_for_url(norm_url: str, default_connect_timeout: int = 5) -> Engine:
    if norm_url.startswith("sqlite"):
        return create_engine(norm_url, connect_args={"check_same_thread": False})

    # Postgres / psycopg
    connect_args: dict[str, Any] = {}
    if "connect_timeout" not in norm_url:
        connect_args["connect_timeout"] = default_connect_timeout

    return create_engine(
        norm_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


def reset_engine() -> None:
    """Reset global engine (used in tests)."""
    global _engine
    _engine = None


def engine() -> Engine:
    """Get or initialize the database engine with graceful fallback."""
    global _engine
    if _engine is not None:
        return _engine

    raw_url = get_settings().db_url
    norm_url = normalize_db_url(raw_url)

    if norm_url.startswith("sqlite"):
        _engine = _create_engine_for_url(norm_url)
        SQLModel.metadata.create_all(_engine)
        return _engine

    # Postgres: attempt connection, fallback to SQLite if unreachable
    try:
        eng = _create_engine_for_url(norm_url)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        SQLModel.metadata.create_all(eng)
        _engine = eng
        log.info("Database connected successfully.")
        return _engine
    except Exception as exc:  # noqa: BLE001
        masked = norm_url.split("@")[-1] if "@" in norm_url else norm_url
        log.warning(
            "Configured database (%s) is unreachable (%s); gracefully falling back to local SQLite",
            masked,
            exc,
        )
        fallback_path = ARTIFACTS / "vidyut_fallback.db"
        try:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_url = f"sqlite:///{fallback_path}"
            _engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
            SQLModel.metadata.create_all(_engine)
        except Exception:  # noqa: BLE001
            _engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
            SQLModel.metadata.create_all(_engine)
        return _engine


def ping() -> dict[str, Any]:
    """Cheap DB round-trip for keep-warm pingers (never raises). Neon free tier suspends compute after
    ~5 idle minutes; any query resets that timer."""
    import time
    t0 = time.perf_counter()
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"db": "unavailable", "error": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def session() -> Session:
    return Session(engine())


def log_event(ts_utc: str, kind: str, title: str, detail: dict | None = None, ref_id: str = "") -> EventLog:
    with session() as s:
        e = EventLog(ts_utc=ts_utc, kind=kind, title=title, detail_json=json.dumps(detail or {}, default=str),
                     ref_id=ref_id)
        s.add(e)
        s.commit()
        s.refresh(e)
        return e


def get_state(key: str, default: str | None = None) -> str | None:
    with session() as s:
        row = s.get(AppState, key)
        return row.value if row else default


def set_state(key: str, value: str) -> None:
    with session() as s:
        s.merge(AppState(key=key, value=value, updated_at=_now()))
        s.commit()


def record_run(name: str, meta: dict, alerts: list[dict]) -> None:
    """Persist run metadata and alerts into the database (idempotent)."""
    with Session(engine()) as s:
        s.merge(RunRow(name=name, issue_time_utc=meta["issue_time_utc"], mode=meta["mode"],
                       n_alerts=len(alerts)))
        for a in alerts:
            existing = s.get(AlertRow, a["id"])
            row = AlertRow(**a, acknowledged=existing.acknowledged if existing else False)
            s.merge(row)
        s.commit()


def reseed_if_empty() -> bool:
    """If DB runs table is empty (fresh or reset DB), ingest latest run from artifacts.

    Idempotent: returns True if reseeded, False if DB already populated or no artifacts yet.
    """
    with Session(engine()) as s:
        has_runs = s.exec(select(RunRow).limit(1)).first() is not None
        if has_runs:
            return False

    try:
        from app.services import runs
        latest_data = runs.latest()
        record_run(latest_data["name"], latest_data["meta"], latest_data["alerts"])
        log.info("Re-seeded empty database from latest run: %s", latest_data["name"])
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("Database re-seed skipped: %s", exc)
        return False


def list_alerts(active_after: str | None = None, limit: int = 200) -> list[AlertRow]:
    with Session(engine()) as s:
        q = select(AlertRow)
        if active_after:
            q = q.where(AlertRow.end_utc >= active_after)
        return list(s.exec(q.order_by(AlertRow.start_utc).limit(limit)))


def acknowledge(alert_id: str) -> bool:
    with Session(engine()) as s:
        row = s.get(AlertRow, alert_id)
        if not row:
            return False
        row.acknowledged = True
        s.add(row)
        s.commit()
        return True
````

---

### 13.3 Services  ·  Depends on: 13.2

#### T13.3.1 — `backend/app/services/jobs.py`  ✅ Tested
Replay clock: `replay_clock_utc` = next virtual issue time, `replay_last_issue_utc` = the latest run's issue time
(the workflow's "now"). At the end of the data the clock wraps to `VIDYUT_REPLAY_START` and logs it.
**FILE: `backend/app/services/jobs.py`** — ✅ Tested

````python
"""Produce one forecast run and push it through the operator workflow (Phase 14).

Used by three callers so the behaviour is identical everywhere:
  * the in-process APScheduler job (local development, VIDYUT_SCHEDULER_ENABLED=true)
  * POST /jobs/tick, called hourly by GitHub Actions in production (Render free instances sleep, so an
    in-process scheduler would never fire; the HTTP call also wakes the instance)
  * the setup wizard, to show the new plant immediately

Replay mode keeps its virtual clock in the database (AppState) so a restart continues where it stopped.
"""
from __future__ import annotations

import json
import threading

import pandas as pd
from vidyut.config import load_config
from vidyut.logs import get_logger
from vidyut.pipelines.forecast import run_forecast

from app.db import models as db
from app.services import runs, schedule
from app.settings import get_settings

log = get_logger(__name__)
_lock = threading.Lock()
CLOCK = "replay_clock_utc"            # next virtual issue time
LAST = "replay_last_issue_utc"        # issue time of the latest replay run


def next_replay_time() -> pd.Timestamp:
    s = get_settings()
    t = pd.Timestamp(db.get_state(CLOCK) or s.replay_start)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    end = load_config().splits.bounds()["test"][1] - pd.Timedelta(days=3)     # keep 48 h + a day of actuals
    if t > end:                                                               # wrap around for long demos
        t = pd.Timestamp(s.replay_start, tz="UTC")
        db.log_event(t.isoformat(), "job", "Replay clock reached the end of the data — restarted", {})
    return t


def produce_run(publish=None, at: str | None = None, advance: bool = True) -> str:
    """Run the forecast, index it, run the workflow (day-ahead proposal, revision check, WhatsApp).

    publish: optional callable(event_dict) for Server-Sent Events. Returns the run folder name.
    Raises if the forecast fails (callers decide whether to swallow).
    """
    s = get_settings()
    with _lock:                                            # never two runs at once (cron + setup + scheduler)
        when = None
        if s.mode == "replay":
            if at:
                when = pd.Timestamp(at)
                when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
            else:
                when = next_replay_time()
        out = run_forecast(load_config(), s.mode, None if when is None else when.isoformat())
        meta = json.loads((out / "run.json").read_text())
        alerts = json.loads((out / "alerts.json").read_text())
        db.record_run(out.name, meta, alerts)
        runs.clear_cache()
        if s.mode == "replay":
            db.set_state(LAST, meta["issue_time_utc"])
            if advance:
                db.set_state(CLOCK, (when + pd.Timedelta(hours=s.replay_step_hours)).isoformat())
        try:
            schedule.after_run(out.name)
        except Exception:
            log.exception("operator workflow failed for run %s", out.name)
    if publish:
        publish({"type": "run_complete", "data": {"run": out.name, "issue_time_utc": meta["issue_time_utc"]}})
        for a in alerts:
            publish({"type": "alert", "data": a})
        publish({"type": "workflow", "data": {"run": out.name}})
    log.info("run %s produced (%s)", out.name, s.mode)
    return out.name
````

#### T13.3.2 — `backend/app/scheduler.py`  ✅ Tested
**FILE: `backend/app/scheduler.py`** — ✅ Tested

````python
"""Background job (local development): produce a forecast run every `schedule_minutes` and notify SSE subscribers.

In production (Render free tier) the instance sleeps when idle, so this scheduler is disabled
(VIDYUT_SCHEDULER_ENABLED=false) and GitHub Actions calls POST /jobs/tick hourly instead (Phase 14).
Both paths call app.services.jobs.produce_run, so behaviour is identical.
"""
from __future__ import annotations

import asyncio

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from vidyut.logs import get_logger

from app.services import jobs
from app.settings import get_settings

log = get_logger(__name__)


class ForecastJob:
    def __init__(self, app) -> None:
        self.app = app
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def tick(self) -> None:
        try:
            jobs.produce_run(publish=self.publish)
        except Exception:
            log.exception("forecast job failed; serving last good run")

    def publish(self, event: dict) -> None:
        loop = getattr(self.app.state, "loop", None)
        for q in list(self.app.state.subscribers):
            if loop:
                loop.call_soon_threadsafe(q.put_nowait, event)

    def start(self) -> None:
        self.scheduler.add_job(self.tick, "interval", minutes=self.settings.schedule_minutes,
                               next_run_time=pd.Timestamp.now(tz="UTC").to_pydatetime())
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)


def attach_loop(app) -> None:
    app.state.loop = asyncio.get_running_loop()
````

#### T13.3.3 — `backend/app/services/schedule.py`  ✅ Tested
`propose_day_ahead` (one proposal per IST day; id `DA-<day>-<run>`; replay auto-accept for demos),
`evaluate_after_run` (always logs a `refresh` event; creates a `Recommendation` and a WhatsApp message only when the
engine recommends), `decide` (Rev 0 for day-ahead, Rev n+1 for revisions; 409 if already decided), `virtual_now`.
**FILE: `backend/app/services/schedule.py`** — ✅ Tested

````python
"""Operator workflow (Phase 14): day-ahead proposal -> submitted schedule -> refresh -> revision recommendation
-> accept / reject, with every step written to the event log (explainability window).

Everything is stored in the database (not in run folders) so it survives restarts of a free-tier host.
Vidyut never submits anything to the grid: accepting means "I will send this to the SLDC through my QCA".
"""
from __future__ import annotations

import json

import pandas as pd
from sqlmodel import select
from vidyut.config import load_config
from vidyut.engines.dsm import block_numbers
from vidyut.engines.revision import apply_revision, evaluate_revision
from vidyut.models.registry import load_object
from vidyut.rules import profile_for
from vidyut.schema import QCOLS

from app.db.models import EventLog, Recommendation, ScheduleVersion, get_state, log_event, session
from app.services import notify, runs
from app.settings import get_settings

IST = "Asia/Kolkata"


def _as_utc(dt) -> pd.Timestamp:
    t = pd.Timestamp(dt)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _blocks_json(s: pd.Series) -> str:
    return json.dumps({"block_end_utc": [t.isoformat() for t in s.index], "mw": [round(float(v), 3) for v in s]})


def _quantiles_json(q: pd.DataFrame) -> str:
    return json.dumps({"block_end_utc": [t.isoformat() for t in q.index],
                       **{c: [round(float(v), 3) for v in q[c]] for c in QCOLS}})


def run_blocks(run_name: str, source: str) -> pd.DataFrame:
    """q05..q95 per 15-min block (index block_end_utc) for one output source of a run."""
    b = runs.blocks(run_name)
    return b[b["source"] == source].set_index("block_end_utc")[list(QCOLS)]


def active_schedule(ist_date: str, source: str = "hybrid") -> ScheduleVersion | None:
    with session() as s:
        return s.exec(select(ScheduleVersion).where(ScheduleVersion.ist_date == ist_date,
                                                    ScheduleVersion.source == source)
                      .order_by(ScheduleVersion.revision_no.desc())).first()


def versions(ist_date: str, source: str = "hybrid") -> list[ScheduleVersion]:
    with session() as s:
        return list(s.exec(select(ScheduleVersion).where(ScheduleVersion.ist_date == ist_date,
                                                         ScheduleVersion.source == source)
                           .order_by(ScheduleVersion.revision_no)))


def recommendations(status: str | None = None, limit: int = 100) -> list[Recommendation]:
    with session() as s:
        q = select(Recommendation)
        if status:
            q = q.where(Recommendation.status == status)
        return list(s.exec(q.order_by(Recommendation.created_at.desc()).limit(limit)))


def events(kind: str | None = None, limit: int = 200) -> list[EventLog]:
    with session() as s:
        q = select(EventLog)
        if kind:
            q = q.where(EventLog.kind == kind)
        return list(s.exec(q.order_by(EventLog.id.desc()).limit(limit)))


def _supersede_pending(ist_date: str, kind: str, now: str) -> None:
    with session() as s:
        for r in s.exec(select(Recommendation).where(Recommendation.ist_date == ist_date,
                                                     Recommendation.kind == kind,
                                                     Recommendation.status == "pending")):
            r.status = "superseded"
            r.decided_at = pd.Timestamp(now).to_pydatetime()
            s.add(r)
            log_event(now, "superseded", f"{r.id} replaced by a newer recommendation", {}, r.id)
        s.commit()


def _slim(p: dict) -> dict:
    """Payload without the bulky per-block arrays (for the event log)."""
    return {k: v for k, v in p.items() if k not in ("blocks_json", "quantiles_json")}


def _rec_dict(r: Recommendation) -> dict:
    return {"id": r.id, "kind": r.kind, "ist_date": r.ist_date, "status": r.status, "run_name": r.run_name,
            "created_at": r.created_at.isoformat(), "decided_by": r.decided_by, "decision_note": r.decision_note,
            "payload": r.payload()}


def propose_day_ahead(run: dict, now: pd.Timestamp) -> Recommendation | None:
    """From each run, offer the penalty-aware schedule for the next IST day if none is submitted yet."""
    cfg = load_config()
    src = cfg.total_source
    sched = run.get("dsm_schedule")
    if sched is None or src not in sched:
        return None
    idx = pd.DatetimeIndex(sched["block_end_utc"])
    day = (idx[0] - pd.Timedelta(minutes=15)).tz_convert(IST).strftime("%Y-%m-%d")
    if active_schedule(day, src) is not None:
        return None
    prof, why = profile_for(cfg)
    eng = load_object("hybrid", "engines@latest")
    level = eng.get("dsm_level", {}).get(src, cfg.revision.expected_level)
    series = pd.Series(sched[src].to_numpy(), index=idx)
    try:
        qjson = _quantiles_json(run_blocks(run["name"], src).reindex(idx))
    except runs.NoRunYet:
        qjson = ""
    payload = {"reason": f"Penalty-aware day-ahead schedule for {day} at P{round(100 * level)} "
                         f"(level tuned on validation to minimise deviation charges under {prof.name}).",
               "deadline_ist": prof.day_ahead.deadline_ist, "profile_id": prof.id, "profile_reason": why,
               "level": level, "blocks_json": _blocks_json(series),
               "energy_mwh": round(float(series.sum() * 0.25), 2), "expected_saving_inr": 0.0,
               "effective_from_block": 1, "quantiles_json": qjson}
    rec = Recommendation(id=f"DA-{day}-{run['name']}", kind="day_ahead", ist_date=day, source=src,
                         run_name=run["name"], payload_json=json.dumps(payload))
    _supersede_pending(day, "day_ahead", now.isoformat())
    with session() as s:
        if s.get(Recommendation, rec.id):
            return None
        s.add(rec)
        s.commit()
        s.refresh(rec)
    log_event(now.isoformat(), "day_ahead_proposed", f"Day-ahead schedule for {day} ready to submit "
              f"(deadline {prof.day_ahead.deadline_ist} IST, {payload['energy_mwh']:.0f} MWh)", _slim(payload), rec.id)
    if get_settings().mode == "replay" and get_settings().replay_autoaccept_dayahead:
        decide(rec.id, True, "auto (replay)", "replay auto-accept", now)
    return rec


def evaluate_after_run(run: dict, now: pd.Timestamp) -> dict | None:
    """Compare today's active schedule with the refreshed forecast; log the refresh; maybe recommend."""
    cfg = load_config()
    src = cfg.total_source
    prof, _ = profile_for(cfg)
    eff_day = (now + pd.Timedelta(minutes=60)).tz_convert(IST).strftime("%Y-%m-%d")
    active = active_schedule(eff_day, src)
    if active is None:
        log_event(now.isoformat(), "refresh", f"Forecast refreshed — no schedule submitted for {eff_day}, "
                  "nothing to compare", {"run": run["name"]}, run["name"])
        return None
    b = run_blocks(run["name"], src)
    eng = load_object("hybrid", "engines@latest")
    level = eng.get("dsm_level", {}).get(src, cfg.revision.expected_level)
    used = active.revision_no
    last_rev = None if used == 0 else _as_utc(active.created_at)
    f = run["forecast"]
    trust = f[f["source"] == src].set_index("target_time_utc")["trust_score"]
    ev = evaluate_revision(now, active.series(), b, cfg.capacity_mw(src), src, prof,
                           cfg.market.contract_rate_inr_per_kwh, cfg.revision, level, used, last_rev,
                           run["alerts"], trust)
    d = ev.to_dict()
    title = ("Revision recommended: " if ev.recommend else "Refresh — no revision: ") + ev.reason
    log_event(now.isoformat(), "refresh", title, d, run["name"])
    if not ev.recommend:
        return d
    _supersede_pending(ev.ist_date, "revision", now.isoformat())
    rec = Recommendation(id=ev.id, kind="revision", ist_date=ev.ist_date, source=src, run_name=run["name"],
                         payload_json=json.dumps(d, default=str))
    with session() as s:
        s.merge(rec)
        s.commit()
    log_event(now.isoformat(), "recommendation", f"{ev.id}: {ev.reason}", d, ev.id)
    rd = _rec_dict(rec)
    notify.notify("revision", ev.id, notify.revision_text(rd), now, "warning",
                  template=get_settings().meta_template_revision,
                  params=[ev.id[-6:], ev.reason, f"₹{ev.expected_saving_inr:,.0f}"])
    return d


def decide(rec_id: str, accept: bool, user: str, note: str, now: pd.Timestamp | None = None) -> dict:
    """Operator decision. Accepting creates a new ScheduleVersion (to be submitted to SLDC via the QCA)."""
    now = now or virtual_now()
    cfg = load_config()
    prof, _ = profile_for(cfg)
    with session() as s:
        rec = s.get(Recommendation, rec_id)
        if rec is None:
            raise KeyError(rec_id)
        if rec.status != "pending":
            raise ValueError(f"recommendation is already {rec.status}")
        rec.status = "accepted" if accept else "rejected"
        rec.decided_at = now.to_pydatetime()
        rec.decided_by = user
        rec.decision_note = note
        s.add(rec)
        s.commit()
        s.refresh(rec)
        p = rec.payload()
    if not accept:
        log_event(now.isoformat(), "rejected", f"{rec_id} rejected by {user}" + (f": {note}" if note else ""), _slim(p),
                  rec_id)
        return _rec_dict(rec)
    if rec.kind == "day_ahead":
        d = json.loads(p["blocks_json"])
        series = pd.Series(d["mw"], index=pd.DatetimeIndex(pd.to_datetime(d["block_end_utc"], utc=True)))
        version = ScheduleVersion(ist_date=rec.ist_date, source=rec.source, revision_no=0, effective_from_block=1,
                                  run_name=rec.run_name, recommendation_id=rec.id, profile_id=p["profile_id"],
                                  blocks_json=_blocks_json(series), quantiles_json=p.get("quantiles_json", ""),
                                  submitted_by=user)
        kind, title = "day_ahead_submitted", f"Day-ahead schedule for {rec.ist_date} accepted by {user} (Rev 0)"
    else:
        active = active_schedule(rec.ist_date, rec.source)
        new = apply_revision(active.series(), p, now, prof)
        changed = new.index > pd.Timestamp(p["effective_from_utc"])
        eff_block = int(block_numbers(pd.DatetimeIndex([new.index[changed][0]]))[0]) if changed.any() else 96
        version = ScheduleVersion(ist_date=rec.ist_date, source=rec.source, revision_no=active.revision_no + 1,
                                  effective_from_block=eff_block, run_name=rec.run_name, recommendation_id=rec.id,
                                  profile_id=prof.id, blocks_json=_blocks_json(new), submitted_by=user)
        kind, title = "accepted", (f"{rec_id} accepted by {user}: Rev {active.revision_no + 1} effective from block "
                                   f"{eff_block}")
    with session() as s:
        s.add(version)
        s.commit()
    log_event(now.isoformat(), kind, title + (f" — {note}" if note else ""), _slim(p), rec_id)
    return _rec_dict(rec)


def virtual_now() -> pd.Timestamp:
    """Replay: the replay clock (latest run's issue time); live: wall clock."""
    if get_settings().mode == "replay":
        clock = get_state("replay_last_issue_utc")
        if clock:
            return pd.Timestamp(clock)
        try:
            return pd.Timestamp(runs.latest()["meta"]["issue_time_utc"])
        except runs.NoRunYet:
            pass
    return pd.Timestamp.now(tz="UTC")


def after_run(run_name: str) -> None:
    """Called by the scheduler after each forecast run."""
    run = runs.load(run_name)
    now = pd.Timestamp(run["meta"]["issue_time_utc"]) if get_settings().mode == "replay" else pd.Timestamp.now(tz="UTC")
    propose_day_ahead(run, now)
    evaluate_after_run(run, now)
    for a in run["alerts"]:
        if a["severity"] in ("warning", "critical"):
            notify.notify("alert", a["id"], notify.alert_text(a), now, a["severity"],
                          params=[f"{a['severity'].upper()} {a['type'].replace('_', ' ').title()}", a["message"],
                                  f"{pd.Timestamp(a['start_utc']).tz_convert(IST):%d %b %H:%M} IST"])
````

#### T13.3.4 — `backend/app/services/notify.py`  ✅ Tested
Default provider `console` only logs — the workflow is fully testable without a phone. Twilio and Meta are
configured in Phase 15. Policy: only opted-in contacts; quiet hours 22:00–06:00 IST except critical; each
alert/recommendation is sent once (dedupe through the event log); replies `YES <code>` / `NO <code>` from a known,
opted-in number decide the pending recommendation whose id ends with the code; signatures are verified.
**FILE: `backend/app/services/notify.py`** — ✅ Tested

````python
"""WhatsApp notifications with three providers:

console : prints/logs messages (development, CI, demos without phones)
twilio  : Twilio WhatsApp API (sandbox for the hackathon: whatsapp:+14155238886; each phone must send the
          sandbox "join <code>" message first; free-form text works inside the 24 h session window)
meta    : WhatsApp Cloud API (production): business-initiated messages MUST use approved templates
          (utility category) — templates `vidyut_alert` and `vidyut_revision`, see VIDYUT_ROADMAP Phase 17

Policy rules enforced here: only contacts with opt_in=True; quiet hours for non-critical messages;
the same alert/recommendation is never sent twice (dedupe via the event log).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
import pandas as pd
from sqlmodel import select
from vidyut.config import load_config
from vidyut.logs import get_logger

from app.db.models import Contact, EventLog, log_event, session
from app.settings import get_settings

log = get_logger(__name__)
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


@dataclass
class SendResult:
    ok: bool
    provider: str
    to: str
    detail: str


def _post_twilio(to: str, text: str, variables: dict | None, client: httpx.Client) -> SendResult:
    s = get_settings()
    data = {"From": s.twilio_whatsapp_from, "To": f"whatsapp:{to}"}
    if s.twilio_content_sid_alert and variables is not None:
        data |= {"ContentSid": s.twilio_content_sid_alert, "ContentVariables": json.dumps(variables)}
    else:
        data["Body"] = text
    r = client.post(f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
                    data=data, auth=(s.twilio_account_sid, s.twilio_auth_token))
    return SendResult(r.status_code < 300, "twilio", to, r.text[:300])


def _post_meta(to: str, template: str, params: list[str], text: str, client: httpx.Client) -> SendResult:
    s = get_settings()
    url = f"https://graph.facebook.com/{s.meta_graph_version}/{s.meta_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to.lstrip("+"),
            "type": "template", "template": {"name": template, "language": {"code": s.meta_template_lang},
                                              "components": [{"type": "body", "parameters": [
                                                  {"type": "text", "text": p[:1000]} for p in params]}]}}
    r = client.post(url, json=body, headers={"Authorization": f"Bearer {s.meta_token}"})
    return SendResult(r.status_code < 300, "meta", to, r.text[:300])


def send_text_meta(to: str, text: str) -> SendResult:
    """Free-form text (allowed only inside the 24 h customer-service window opened by the user's message)."""
    s = get_settings()
    if s.notify_provider != "meta":
        return SendResult(True, s.notify_provider, to, "skipped (not meta)")
    url = f"https://graph.facebook.com/{s.meta_graph_version}/{s.meta_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "text", "text": {"body": text[:4096]}}
    try:
        r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {s.meta_token}"}, timeout=15)
        return SendResult(r.status_code < 300, "meta", to, r.text[:300])
    except httpx.HTTPError as e:
        return SendResult(False, "meta", to, str(e))


def send(to: str, text: str, template: str | None = None, params: list[str] | None = None,
         client: httpx.Client | None = None) -> SendResult:
    provider = get_settings().notify_provider
    if provider == "console":
        log.info("WHATSAPP (console) to %s: %s", to, text)
        return SendResult(True, "console", to, "logged")
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        if provider == "twilio":
            return _post_twilio(to, text, None if params is None else {str(i + 1): p for i, p in enumerate(params)},
                                client)
        return _post_meta(to, template or get_settings().meta_template_alert, params or [text], text, client)
    except httpx.HTTPError as e:
        return SendResult(False, provider, to, str(e))
    finally:
        if own:
            client.close()


def _quiet(now_utc: pd.Timestamp) -> bool:
    start, end = load_config().notifications.quiet_hours_ist
    h = now_utc.tz_convert("Asia/Kolkata").hour
    return (h >= start or h < end) if start > end else (start <= h < end)


def _already_sent(key: str) -> bool:
    with session() as s:
        return s.exec(select(EventLog).where(EventLog.kind == "whatsapp", EventLog.ref_id == key)).first() is not None


def recipients(kind: str, severity: str = "warning") -> list[Contact]:
    with session() as s:
        cs = list(s.exec(select(Contact).where(Contact.opt_in == True)))
    if kind == "alert":
        return [c for c in cs if SEVERITY_RANK[severity] >= SEVERITY_RANK.get(c.min_severity, 1)]
    if kind == "revision":
        return [c for c in cs if c.receive_revisions]
    return [c for c in cs if c.receive_reports]


def notify(kind: str, key: str, text: str, now_utc: pd.Timestamp, severity: str = "warning",
           template: str | None = None, params: list[str] | None = None, client: httpx.Client | None = None) -> int:
    """Send to all matching contacts once per key. Returns the number of messages sent."""
    cfg = load_config().notifications
    if not cfg.enabled or _already_sent(key):
        return 0
    if kind == "alert" and SEVERITY_RANK[severity] < SEVERITY_RANK[cfg.min_severity]:
        return 0
    if severity != "critical" and _quiet(now_utc):
        log_event(now_utc.isoformat(), "whatsapp", f"Held during quiet hours: {text[:80]}", {"key": key}, key)
        return 0
    sent = 0
    for c in recipients(kind, severity):
        r = send(c.whatsapp, text, template, params, client)
        sent += int(r.ok)
        log_event(now_utc.isoformat(), "whatsapp", f"{'Sent' if r.ok else 'FAILED'} to {c.name} via {r.provider}",
                  {"to": c.whatsapp, "text": text, "detail": r.detail}, key)
    return sent


def alert_text(a: dict) -> str:
    t = pd.Timestamp(a["start_utc"]).tz_convert("Asia/Kolkata")
    e = pd.Timestamp(a["end_utc"]).tz_convert("Asia/Kolkata")
    return (f"⚠️ Vidyut {a['severity'].upper()} — {a['type'].replace('_', ' ').title()}\n{a['message']}\n"
            f"{t:%d %b %H:%M}–{e:%H:%M} IST\n{get_settings().public_app_url}/alerts")


def revision_text(rec: dict) -> str:
    p = rec["payload"]
    return (f"📝 Vidyut revision recommended ({rec['id']})\n{p['reason']}\n"
            f"Expected saving ₹{p['expected_saving_inr']:,.0f}. From block {p['effective_from_block']}.\n"
            f"Reply YES {rec['id'][-6:]} to accept or NO {rec['id'][-6:]} to reject, or open "
            f"{get_settings().public_app_url}/revisions")


# ---------- replies from WhatsApp (webhooks) ----------
def twilio_signature_ok(url: str, form: dict[str, str], signature: str) -> bool:
    """Twilio: base64(HMAC-SHA1(auth_token, url + concat(sorted key+value)))."""
    import base64
    import hashlib
    import hmac
    payload = url + "".join(k + form[k] for k in sorted(form))
    mac = hmac.new(get_settings().twilio_auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(mac).decode(), signature or "")


def meta_signature_ok(raw: bytes, header: str) -> bool:
    """Meta: 'sha256=' + hex(HMAC-SHA256(app_secret, raw body))."""
    import hashlib
    import hmac
    mac = hmac.new(get_settings().meta_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + mac, header or "")


def handle_reply(from_number: str, text: str, now_utc: pd.Timestamp | None = None) -> str:
    """'YES ab12cd' / 'NO ab12cd' from an opted-in contact decides the pending recommendation ending in ab12cd.

    Returns the reply text to send back. Anything else gets a help message. Unknown numbers are ignored.
    """
    from app.db.models import Recommendation
    from app.services import schedule

    number = "+" + from_number.replace("whatsapp:", "").lstrip("+")
    with session() as s:
        contact = s.exec(select(Contact).where(Contact.whatsapp == number, Contact.opt_in == True)).first()
        if contact is None:
            return ""
        parts = text.strip().split()
        if len(parts) != 2 or parts[0].upper() not in ("YES", "NO"):
            return "Vidyut: reply YES <code> or NO <code> (the code is in the recommendation message)."
        code = parts[1].lower()
        rec = next((r for r in s.exec(select(Recommendation).where(Recommendation.status == "pending"))
                    if r.id.lower().endswith(code)), None)
    if rec is None:
        return f"Vidyut: no pending recommendation with code {code} (it may be decided or superseded)."
    accept = parts[0].upper() == "YES"
    try:
        schedule.decide(rec.id, accept, f"{contact.name} (WhatsApp)", "via WhatsApp", now_utc)
    except ValueError as e:
        return f"Vidyut: {e}"
    return (f"Vidyut: {rec.id} {'ACCEPTED' if accept else 'REJECTED'}. "
            + ("Remember to submit the revised schedule to SLDC via your QCA." if accept else ""))
````

#### T13.3.5 — `backend/app/services/reports.py`  ✅ Tested
A day is reportable only after it ended (in replay: after the virtual clock passed it). Actuals = the twin's
measured output × the plant mapping factors, downscaled to 15 min (with one extra hour because IST is UTC+5:30).
**FILE: `backend/app/services/reports.py`** — ✅ Tested

````python
"""Daily accuracy & estimated-deviation report (on-screen JSON + PDF), Phase 15.

Inputs, all from the database so the report survives restarts: Rev 0 schedule + its forecast quantiles, the
final schedule, revision decisions, alerts. "Actual" generation = the virtual plant's measured output
(digital twin history in data/processed/dataset.parquet) scaled to the operator's plant.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sqlmodel import select
from vidyut.config import load_config
from vidyut.data.build_dataset import load_dataset
from vidyut.engines.daily_report import build_daily_report
from vidyut.eval.pdf import render_daily_pdf
from vidyut.models.downscale import downscale_solar, downscale_wind
from vidyut.plant import plant_mapping
from vidyut.rules import profile_for
from vidyut.schema import QCOLS

from app.db.models import AlertRow, Recommendation, ScheduleVersion, session
from app.services import runs
from app.services.schedule import versions

IST = "Asia/Kolkata"


class ReportNotReady(Exception):
    pass


def _finished(day: str) -> bool:
    """A day can be reported only after it ended (replay: in virtual time)."""
    from app.services.schedule import virtual_now
    return _day_index(day)[-1] <= virtual_now()


def available_days(source: str | None = None) -> list[str]:
    source = source or load_config().total_source
    with session() as s:
        rows = s.exec(select(ScheduleVersion.ist_date).where(ScheduleVersion.source == source)).all()
    return sorted({d for d in rows if _finished(d)}, reverse=True)


def _day_index(day: str) -> pd.DatetimeIndex:
    start = pd.Timestamp(day, tz=IST) + pd.Timedelta(minutes=15)
    return pd.date_range(start, periods=96, freq="15min").tz_convert("UTC")


def _actual_blocks(day: str, source: str) -> pd.Series:
    """Measured output of the plant for one IST day in 15-min blocks (reference twin x capacity factor)."""
    cfg = load_config()
    try:
        ds = load_dataset()
    except FileNotFoundError:
        raise ReportNotReady("no measured history on this server (data/processed/dataset.parquet)") from None
    idx = _day_index(day)
    lo, hi = idx[0] - pd.Timedelta(minutes=15), idx[-1]
    f = plant_mapping(cfg).factors
    parts = []
    for s in (cfg.sources if source == cfg.total_source else [source]):
        h = ds[f"{s}_mw"].loc[lo:hi + pd.Timedelta(hours=1)]     # IST = UTC+5:30: one extra hour for the last blocks
        h = h[h.index > lo] * f[s]
        if len(h) < 25 or h.isna().any():
            raise ReportNotReady(f"actual generation for {day} is not available yet")
        cap = cfg.capacity_mw(s)
        parts.append((downscale_solar(h, cfg.site, cap) if s == "solar" else downscale_wind(h, cap)).reindex(idx))
    out = sum(parts)
    if out.isna().any():
        raise ReportNotReady(f"actual generation for {day} is incomplete")
    return out


def day_quantiles(rev0: ScheduleVersion, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Forecast quantiles behind Rev 0: stored with the schedule; older rows fall back to the run folder."""
    q = rev0.quantiles()
    if q is None:
        try:
            b = runs.blocks(rev0.run_name)
        except runs.NoRunYet:
            raise ReportNotReady(f"forecast blocks for run {rev0.run_name} are gone") from None
        q = b[b["source"] == rev0.source].set_index("block_end_utc")[list(QCOLS)]
    q = q.reindex(idx)
    if q.isna().any().any():
        raise ReportNotReady(f"forecast blocks for {rev0.ist_date} are incomplete")
    return q


@lru_cache(maxsize=32)
def daily(day: str, source: str | None = None) -> dict:
    cfg = load_config()
    source = source or cfg.total_source
    if not _finished(day):
        raise ReportNotReady(f"{day} has not finished yet")
    vs = versions(day, source)
    if not vs:
        raise ReportNotReady(f"no schedule was submitted for {day}")
    rev0, final = vs[0], vs[-1]
    idx = _day_index(day)
    q = day_quantiles(rev0, idx)
    cap = cfg.capacity_mw(source)
    actual = _actual_blocks(day, source)
    with session() as s:
        recs = [{"id": r.id, "status": r.status, "decided_by": r.decided_by, "decision_note": r.decision_note,
                 **{k: r.payload().get(k) for k in ("effective_from_block", "expected_saving_inr", "reason")}}
                for r in s.exec(select(Recommendation).where(Recommendation.ist_date == day,
                                                             Recommendation.kind == "revision"))]
        lo, hi = idx[0] - pd.Timedelta(minutes=15), idx[-1]
        alerts = [{"type": a.type, "severity": a.severity} for a in s.exec(
            select(AlertRow).where(AlertRow.start_utc >= lo.isoformat(), AlertRow.start_utc <= hi.isoformat()))]
    prof, why = profile_for(cfg)
    return build_daily_report(day, cfg.plant.name, source, cap, prof, cfg.market.contract_rate_inr_per_kwh, q, actual,
                              rev0.series(), final.series(), recs, alerts, why)


def daily_pdf(day: str, source: str | None = None) -> bytes:
    return render_daily_pdf(daily(day, source))
````

#### T13.3.6 — `backend/app/services/setup.py`  ✅ Tested
`apply` writes `config/plant.yaml` and the same YAML into `AppState('plant_yaml')`, rolls back on invalid config,
replaces contacts, and starts a background job: re-tune the schedule level (`evaluate_all`) only if the market
fields changed, then produce a run for the new plant at the *same* virtual time. `materialize_plant_file()` restores
the file from the DB at start-up. `start_retrain`: `local` (thread: weather → dataset → frame → train → snapshot →
evaluate → run) or `github` (dispatches `.github/workflows/retrain.yml`, Phase 16) or `off`.
**FILE: `backend/app/services/setup.py`** — ✅ Tested

````python
"""Plant setup wizard backend (Phase 16).

Saving the wizard:
  1. writes config/plant.yaml (the overlay read by vidyut.config.load_config) AND stores the same YAML in the
     database (AppState 'plant_yaml'), because a free-tier host wipes its disk on every deploy/restart;
     `materialize_plant_file()` re-writes the file from the database at API start-up;
  2. replaces the WhatsApp contacts;
  3. starts a background job: re-tune the schedule level when the rules changed (retune_dsm), then produce a fresh
     forecast run so every page shows the new plant at once (models are scaled — vidyut.plant).
Retraining for the plant is a separate, explicit action (`start_retrain`): a local thread in development or
a GitHub Actions workflow in production (`VIDYUT_RETRAIN_MODE=github`).
"""
from __future__ import annotations

import base64
import threading
from datetime import datetime, timezone

import httpx
import yaml
from pydantic import BaseModel, Field, model_validator
from sqlmodel import delete
from vidyut import rules
from vidyut.config import PLANT_FILE, default_config, load_config, reference_config
from vidyut.logs import get_logger
from vidyut.plant import plant_mapping

from app.db.models import Contact, get_state, log_event, session, set_state
from app.services import runs
from app.settings import get_settings

log = get_logger(__name__)
STATE_KEY = "plant_yaml"
MARKET_KEYS = ("state", "interstate", "rule_profile", "contract_rate_inr_per_kwh")


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = "operator"
    whatsapp: str = Field(pattern=r"^\+[1-9]\d{7,14}$")      # E.164, e.g. +919812345678
    opt_in: bool = False
    min_severity: str = Field("warning", pattern="^(info|warning|critical)$")
    receive_revisions: bool = True
    receive_reports: bool = True


class PlantSetup(BaseModel):
    plant_name: str = Field(min_length=2, max_length=120)
    plant_type: str = Field(pattern="^(solar|wind|hybrid)$")
    owner: str = ""
    qca_name: str = ""
    state: str
    district: str = ""
    interstate: bool = False
    rule_profile: str = "auto"
    contract_rate_inr_per_kwh: float = Field(gt=0, le=20)
    latitude: float = Field(ge=6, le=37.5)                    # India bounding box
    longitude: float = Field(ge=68, le=97.5)
    altitude_m: float = Field(0, ge=-10, le=5000)
    solar_dc_mw: float | None = Field(None, gt=0, le=5000)    # required when the plant has solar
    solar_ac_mw: float | None = Field(None, gt=0, le=5000)
    tilt_deg: float = Field(23, ge=0, le=60)
    azimuth_deg: float = Field(180, ge=0, lt=360)
    turbine_type: str | None = None                           # required when the plant has wind
    n_turbines: int | None = Field(None, ge=1, le=1000)
    hub_height_m: float = Field(90, ge=30, le=200)
    battery_mw: float = Field(0, ge=0, le=5000)
    battery_mwh: float = Field(0, ge=0, le=20000)
    demand_peak_mw: float = Field(gt=0, le=10000)             # contracted supply the plant must serve
    contacts: list[ContactIn] = []

    @model_validator(mode="after")
    def _per_type(self) -> PlantSetup:
        if self.plant_type in ("solar", "hybrid") and not (self.solar_dc_mw and self.solar_ac_mw):
            raise ValueError("solar DC and AC capacity are required for a plant with solar")
        if self.plant_type in ("wind", "hybrid") and not (self.turbine_type and self.n_turbines):
            raise ValueError("turbine model and number of turbines are required for a plant with wind")
        if self.state not in rules.INDIAN_STATES:
            raise ValueError(f"unknown state {self.state!r}")
        return self


JOB = {"kind": "", "state": "idle", "step": "", "progress": 0, "error": "", "started_at": None, "finished_at": None,
       "url": ""}


# ---------- persistence ----------
def save_plant_yaml(text: str) -> None:
    PLANT_FILE.write_text(text, encoding="utf-8")
    set_state(STATE_KEY, text)
    default_config.cache_clear()


def materialize_plant_file() -> bool:
    """API start-up: database copy -> config/plant.yaml (the disk may have been wiped). True if written."""
    try:
        text = get_state(STATE_KEY)
    except Exception as e:  # noqa: BLE001  DB unreachable: keep whatever is on disk
        log.warning("could not read plant setup from the database: %s", e)
        return False
    if text and (not PLANT_FILE.exists() or PLANT_FILE.read_text(encoding="utf-8") != text):
        PLANT_FILE.write_text(text, encoding="utf-8")
        default_config.cache_clear()
        return True
    return False


def configured() -> bool:
    return PLANT_FILE.exists() or bool(get_state(STATE_KEY))


# ---------- read ----------
def status() -> dict:
    cfg = load_config()
    pid, why = rules.resolve_profile_id(cfg.market.state, cfg.market.interstate, cfg.market.rule_profile)
    return {"configured": configured(), "plant_name": cfg.plant.name, "plant_type": cfg.plant.type,
            "state": cfg.market.state, "rule_profile": pid, "rule_profile_reason": why,
            "mapping": plant_mapping().to_dict(), "retrain_mode": get_settings().retrain_mode, "job": dict(JOB)}


def options() -> dict:
    from windpowerlib import get_turbine_types
    t = get_turbine_types(print_out=False)
    t = t[t["has_power_curve"]]
    cfg = load_config()
    return {
        "plant_types": ["solar", "wind", "hybrid"],
        "states": rules.INDIAN_STATES,
        "profiles": [p.summary() for p in rules.list_profiles()],
        "turbine_types": sorted(t["turbine_type"].tolist()),
        "defaults": {"plant_name": cfg.plant.name, "plant_type": cfg.plant.type, "owner": cfg.plant.owner,
                     "qca_name": cfg.plant.qca_name, "state": cfg.market.state, "district": cfg.plant.district,
                     "interstate": cfg.market.interstate, "rule_profile": cfg.market.rule_profile,
                     "contract_rate_inr_per_kwh": cfg.market.contract_rate_inr_per_kwh,
                     "latitude": cfg.site.latitude, "longitude": cfg.site.longitude, "altitude_m": cfg.site.altitude_m,
                     "solar_dc_mw": cfg.solar.dc_capacity_mw, "solar_ac_mw": cfg.solar.ac_capacity_mw,
                     "tilt_deg": cfg.solar.tilt_deg, "azimuth_deg": cfg.solar.azimuth_deg,
                     "turbine_type": cfg.wind.turbine_type, "n_turbines": cfg.wind.n_turbines,
                     "hub_height_m": cfg.wind.hub_height_m, "battery_mw": cfg.battery.power_mw,
                     "battery_mwh": cfg.battery.energy_mwh, "demand_peak_mw": cfg.demand.peak_mw},
    }


# ---------- write ----------
def plant_dict(p: PlantSetup) -> dict:
    """Only the keys the operator controls; everything else keeps the reference value from site.yaml."""
    d = {
        "plant": {"name": p.plant_name, "type": p.plant_type, "owner": p.owner, "qca_name": p.qca_name,
                  "district": p.district},
        "market": {"state": p.state, "interstate": p.interstate, "rule_profile": p.rule_profile,
                   "contract_rate_inr_per_kwh": p.contract_rate_inr_per_kwh},
        "site": {"name": p.plant_name, "latitude": p.latitude, "longitude": p.longitude, "altitude_m": p.altitude_m},
        "battery": {"power_mw": p.battery_mw, "energy_mwh": p.battery_mwh},
        "demand": {"peak_mw": p.demand_peak_mw},
    }
    if p.plant_type in ("solar", "hybrid"):
        d["solar"] = {"dc_capacity_mw": p.solar_dc_mw, "ac_capacity_mw": p.solar_ac_mw, "tilt_deg": p.tilt_deg,
                      "azimuth_deg": p.azimuth_deg}
    if p.plant_type in ("wind", "hybrid"):
        d["wind"] = {"turbine_type": p.turbine_type, "n_turbines": p.n_turbines, "hub_height_m": p.hub_height_m}
    return d


def apply(p: PlantSetup, now_iso: str) -> dict:
    if p.rule_profile != "auto":
        rules.load_profile(p.rule_profile)                    # raises FileNotFoundError if unknown
    old = load_config()
    new = plant_dict(p)
    old_text = PLANT_FILE.read_text(encoding="utf-8") if PLANT_FILE.exists() else None
    save_plant_yaml(yaml.safe_dump(new, sort_keys=False))
    try:
        cfg = load_config()                                   # validate the merged config now
    except Exception:
        if old_text is None:                                  # roll back to the previous file
            PLANT_FILE.unlink(missing_ok=True)
        else:
            save_plant_yaml(old_text)
        raise
    with session() as s:
        s.exec(delete(Contact))
        for c in p.contacts:
            s.add(Contact(**c.model_dump()))
        s.commit()
    market_changed = any(getattr(old.market, k) != getattr(cfg.market, k) for k in MARKET_KEYS)
    m = plant_mapping(cfg)
    log_event(now_iso, "setup", f"Plant setup saved: {p.plant_name} ({p.plant_type}, {p.state})"
              + ("" if m.ok else " — RETRAIN REQUIRED"), {"plant": new["plant"], "mapping": m.to_dict()})
    if m.ok:
        start_refresh(retune=market_changed)
    return {**status(), "market_changed": market_changed}


def _clear_caches() -> None:
    runs.clear_cache()
    from app.services import reports, whatif
    whatif._models.cache_clear()
    reports.daily.cache_clear()


def _thread(kind: str, work) -> None:
    if JOB["state"] == "running":
        raise RuntimeError("a setup job is already running")
    JOB.update(kind=kind, state="running", step="", progress=0, error="", url="",
               started_at=datetime.now(timezone.utc).isoformat(), finished_at=None)

    def run():
        try:
            work()
            JOB.update(state="done", progress=100)
        except Exception as e:
            log.exception("setup job %s failed", kind)
            JOB.update(state="failed", error=str(e))
        finally:
            JOB.update(finished_at=datetime.now(timezone.utc).isoformat())
            _clear_caches()

    threading.Thread(target=run, daemon=True).start()


def start_refresh(retune: bool = False) -> None:
    """Re-tune the DSM schedule level (only if the rules changed), then forecast the new plant."""
    def work():
        from app.services import jobs
        if retune:                                            # light: fits a 512 MB instance (evaluate_all does not)
            from vidyut.pipelines.evaluate import retune_dsm
            JOB.update(step="Re-tuning the schedule for the new deviation rules", progress=20)
            retune_dsm(reference_config())
        JOB.update(step="Forecasting your plant", progress=60)
        last = get_state(jobs.LAST)
        jobs.produce_run(at=last, advance=False)              # same virtual time, new plant
    _thread("refresh", work)


# ---------- retrain ----------
def _retrain_local() -> None:
    from vidyut.config import write_reference_snapshot
    from vidyut.data.build_dataset import build_dataset
    from vidyut.data.weather_tables import build_weather_tables
    from vidyut.features.framing import frame_all
    from vidyut.paths import DATA_PROCESSED
    from vidyut.pipelines.evaluate import evaluate_all
    from vidyut.pipelines.train import train_all

    from app.services import jobs
    cfg = load_config()
    JOB.update(step="Fetching weather for the plant location", progress=5)
    act, fx = build_weather_tables(cfg, synthetic=get_settings().setup_synthetic_weather)
    JOB.update(step="Building the digital-twin history", progress=25)
    ds = build_dataset(cfg, act, fx)
    JOB.update(step="Framing", progress=35)
    frames = frame_all(ds, cfg)
    for s, f in frames.items():
        f.to_parquet(DATA_PROCESSED / f"framed_{s}.parquet")
    JOB.update(step="Training models", progress=45)
    train_all(frames, cfg)
    write_reference_snapshot(cfg)
    JOB.update(step="Evaluating engines", progress=85)
    evaluate_all(cfg)
    JOB.update(step="First forecast", progress=95)
    jobs.produce_run(at=get_state(jobs.LAST), advance=False)


def _retrain_github() -> str:
    """Dispatch .github/workflows/retrain.yml with the plant YAML; the workflow publishes a new artifact release
    and commits deploy/artifacts.lock, which redeploys the API (Phase 16.5)."""
    s = get_settings()
    if not s.github_token:
        raise RuntimeError("VIDYUT_GITHUB_TOKEN is not set")
    plant_b64 = base64.b64encode(PLANT_FILE.read_bytes()).decode()
    r = httpx.post(f"https://api.github.com/repos/{s.github_repo}/actions/workflows/retrain.yml/dispatches",
                   headers={"Authorization": f"Bearer {s.github_token}", "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28"},
                   json={"ref": "main", "inputs": {"plant_yaml_b64": plant_b64}}, timeout=20)
    if r.status_code != 204:
        raise RuntimeError(f"GitHub refused the workflow dispatch: {r.status_code} {r.text[:200]}")
    return f"https://github.com/{s.github_repo}/actions/workflows/retrain.yml"


def start_retrain(now_iso: str) -> dict:
    mode = get_settings().retrain_mode
    if mode == "off":
        raise PermissionError("retraining is disabled on this server (VIDYUT_RETRAIN_MODE=off)")
    if not PLANT_FILE.exists():
        raise FileNotFoundError("save the plant setup first")
    if mode == "github":
        url = _retrain_github()
        JOB.update(kind="retrain", state="dispatched", step="Running on GitHub Actions (about 20-40 min)",
                   progress=0, error="", url=url, started_at=now_iso, finished_at=None)
        log_event(now_iso, "setup", "Retraining dispatched to GitHub Actions", {"url": url})
        return dict(JOB)
    log_event(now_iso, "setup", "Retraining started on this server", {})
    _thread("retrain", _retrain_local)
    return dict(JOB)
````

---

### 13.4 Routes  ·  Depends on: 13.3

#### T13.4.1 — `backend/app/api/routes/workflow.py`  ✅ Tested
**FILE: `backend/app/api/routes/workflow.py`** — ✅ Tested

````python
"""Operator workflow API (Phase 14): active schedule, recommendations (accept / reject), event log, CSV export."""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from vidyut.config import load_config
from vidyut.engines.dsm import schedule_csv
from vidyut.rules import profile_for

from app.services import schedule as svc

router = APIRouter(tags=["workflow"])
Status = Literal["pending", "accepted", "rejected", "superseded"]


class Decision(BaseModel):
    accept: bool
    user: str = Field("operator", min_length=1, max_length=60)
    note: str = Field("", max_length=500)


def _version(v) -> dict:
    d = json.loads(v.blocks_json)
    return {"ist_date": v.ist_date, "source": v.source, "revision_no": v.revision_no,
            "effective_from_block": v.effective_from_block, "run_name": v.run_name,
            "recommendation_id": v.recommendation_id, "profile_id": v.profile_id, "submitted_by": v.submitted_by,
            "created_at": v.created_at.isoformat(), "block_end_utc": d["block_end_utc"], "mw": d["mw"]}


def _rec(r) -> dict:
    d = svc._rec_dict(r)
    d["payload"] = {k: v for k, v in d["payload"].items() if k != "quantiles_json"}   # bulky, UI does not need it
    return d


@router.get("/schedule/today")
def today(date: str | None = None) -> dict:
    """Active schedule + all versions for an IST day (default: the virtual 'today'), and the revision counter."""
    cfg = load_config()
    src = cfg.total_source
    prof, why = profile_for(cfg)
    day = date or svc.virtual_now().tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
    vs = svc.versions(day, src)
    return {"ist_date": day, "source": src, "profile": prof.summary(), "profile_reason": why,
            "revisions_used": max(len(vs) - 1, 0), "max_revisions": prof.revisions.max_per_day[src],
            "active": _version(vs[-1]) if vs else None, "versions": [_version(v) for v in vs],
            "now_utc": svc.virtual_now().isoformat()}


@router.get("/recommendations")
def list_recs(status: Status | None = None, limit: int = 50) -> list[dict]:
    return [_rec(r) for r in svc.recommendations(status, min(limit, 200))]


@router.post("/recommendations/{rec_id}/decision")
def decide(rec_id: str, body: Decision) -> dict:
    try:
        d = svc.decide(rec_id, body.accept, body.user, body.note)
    except KeyError:
        raise HTTPException(404, "recommendation not found") from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    d["payload"] = {k: v for k, v in d["payload"].items() if k != "quantiles_json"}
    return d


@router.get("/events")
def events(kind: str | None = None, limit: int = 200) -> list[dict]:
    return [{"id": e.id, "ts_utc": e.ts_utc, "kind": e.kind, "title": e.title, "ref_id": e.ref_id,
             "detail": json.loads(e.detail_json or "{}")} for e in svc.events(kind, min(limit, 1000))]


@router.get("/schedule/active.csv", response_class=Response)
def active_csv(date: str) -> Response:
    """The ACTIVE (latest accepted) version for an IST day, in the 96-block CSV the QCA uploads."""
    v = svc.active_schedule(date, load_config().total_source)
    if v is None:
        raise HTTPException(404, f"no schedule submitted for {date}")
    return Response(schedule_csv(v.series()), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="vidyut_schedule_{date}_rev{v.revision_no}.csv"'})
````

#### T13.4.2 — `backend/app/api/routes/jobs.py`  ✅ Tested
**FILE: `backend/app/api/routes/jobs.py`** — ✅ Tested

````python
"""POST /jobs/tick — produce one forecast run on demand (production cron, Phase 14).

Protected by a shared secret: header `X-Job-Token: <VIDYUT_JOB_TOKEN>`. With no token configured the
endpoint is disabled (404) so a public deployment cannot be driven by strangers.
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.services import jobs
from app.settings import get_settings

router = APIRouter(tags=["jobs"])


@router.post("/jobs/tick")
async def tick(request: Request, x_job_token: str = Header(default="")) -> dict:
    token = get_settings().job_token
    if not token:
        raise HTTPException(404, "jobs endpoint disabled (set VIDYUT_JOB_TOKEN)")
    if not hmac.compare_digest(x_job_token, token):
        raise HTTPException(401, "bad job token")
    job = getattr(request.app.state, "job", None)
    name = await run_in_threadpool(jobs.produce_run, job.publish if job else None)
    return {"ok": True, "run": name, "now_utc": jobs.db.get_state(jobs.LAST)}
````

#### T13.4.3 — `backend/app/api/routes/dsm.py` (profiles, explain, simulate)  ✅ Tested
**FILE: `backend/app/api/routes/dsm.py`** — ✅ Tested

````python
"""Deviation Shield: tuned-level summary, schedule CSV, rule profiles, charge explanation, penalty simulator."""
from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from vidyut.config import load_config
from vidyut.engines.dsm import explain_block, schedule_csv
from vidyut.engines.penalty_sim import SimInput, simulate
from vidyut.rules import list_profiles, load_profile, profile_for
from vidyut.schema import QCOLS

from app.schemas.api import DsmRow, DsmSummary
from app.services import reports, runs
from app.services.plant import resolve_source

router = APIRouter(tags=["dsm"])
Source = Literal["solar", "wind", "hybrid"]


@router.get("/dsm/summary", response_model=DsmSummary)
def summary() -> DsmSummary:
    d = runs.evaluation()["dsm"]
    return DsmSummary(illustrative_rates=d["illustrative_rates"], chosen_level=d["chosen_level"],
                      rows=[DsmRow(**r) for r in d["table"]], profile=d.get("profile", {}),
                      profile_reason=d.get("profile_reason", ""),
                      contract_rate_inr_per_kwh=d.get("contract_rate_inr_per_kwh", 0.0))


@router.get("/dsm/schedule.csv", response_class=Response)
def schedule(source: Source | None = None) -> Response:
    source = resolve_source(source)
    s = runs.latest()["dsm_schedule"]
    if s is None or source not in s:
        raise HTTPException(404, "no day-ahead schedule in the latest run")
    series = pd.Series(s[source].to_numpy(), index=pd.DatetimeIndex(s["block_end_utc"]))
    # attachment + text/csv: a cross-origin <a download> is ignored by browsers, so the server must
    # force the download, otherwise the user is navigated away from the app to a raw text page
    return Response(schedule_csv(series), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="vidyut_schedule_{source}.csv"'})


@router.get("/dsm/profiles")
def profiles() -> dict:
    """The profile in force for this plant (and why) plus every available profile (Phase 12)."""
    prof, why = profile_for(load_config())
    return {"active": prof.summary(), "reason": why, "all": [p.summary() for p in list_profiles()]}


class ExplainIn(BaseModel):
    schedule_mw: float = Field(ge=0)
    actual_mw: float = Field(ge=0)
    source: Source | None = None
    profile_id: str | None = None
    contract_rate_inr_per_kwh: float | None = Field(None, gt=0)
    label: str = Field("", max_length=80)


@router.post("/dsm/explain")
def explain(body: ExplainIn) -> dict:
    """Step-by-step charge of one block: formula, bands, rupees (the Charge Explanation panel)."""
    cfg = load_config()
    source = resolve_source(body.source)
    try:
        prof = load_profile(body.profile_id) if body.profile_id else profile_for(cfg)[0]
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from None
    return explain_block(body.schedule_mw, body.actual_mw, cfg.capacity_mw(source), source, prof,
                         body.contract_rate_inr_per_kwh or cfg.market.contract_rate_inr_per_kwh, body.label)


def _next_day_blocks(source: str) -> tuple[str, pd.DataFrame]:
    run = runs.latest()
    s = run["dsm_schedule"]
    if s is None:
        raise HTTPException(409, "the latest run has no next-day schedule")
    try:
        b = runs.blocks(run["name"])
    except runs.NoRunYet as e:
        raise HTTPException(409, str(e)) from None
    idx = pd.DatetimeIndex(s["block_end_utc"])
    day = (idx[0] - pd.Timedelta(minutes=15)).tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
    return day, b[b["source"] == source].set_index("block_end_utc")[list(QCOLS)].reindex(idx)


@router.post("/dsm/simulate")
def simulate_route(body: SimInput) -> dict:
    """Penalty simulator (Phase 13): vary the RULES (profile, rate, tolerance, harshness) and the SCHEDULE
    (quantile level, manual block edits). day="next" -> expected charges; a past date -> realised charges."""
    cfg = load_config()
    source = resolve_source(body.source)
    body = body.model_copy(update={"source": source})
    try:
        prof = load_profile(body.profile_id) if body.profile_id else profile_for(cfg)[0]
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from None
    actual = None
    if body.day == "next":
        day, q = _next_day_blocks(source)
    else:
        day = body.day
        vs = reports.versions(day, source)
        if not vs:
            raise HTTPException(409, f"no schedule was submitted for {day}")
        idx = reports._day_index(day)
        try:
            q = reports.day_quantiles(vs[0], idx)
            actual = reports._actual_blocks(day, source)
        except reports.ReportNotReady as e:
            raise HTTPException(409, str(e)) from None
    if q.isna().any().any():
        raise HTTPException(409, f"forecast blocks for {day} are incomplete")
    out = simulate(body, prof, cfg.market.contract_rate_inr_per_kwh, q, cfg.capacity_mw(source), actual)
    return {"day": day, **out}
````

#### T13.4.4 — `backend/app/api/routes/reports.py`  ✅ Tested
**FILE: `backend/app/api/routes/reports.py`** — ✅ Tested

````python
"""Daily accuracy & estimated-deviation report: on-screen JSON and PDF download."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services import reports as svc

router = APIRouter(tags=["reports"])
Source = Literal["solar", "wind", "hybrid"]


@router.get("/reports/days")
def days(source: Source | None = None) -> list[str]:
    return svc.available_days(source)


@router.get("/reports/daily")
def daily(date: str, source: Source | None = None) -> dict:
    try:
        return svc.daily(date, source)
    except svc.ReportNotReady as e:
        raise HTTPException(409, str(e)) from None


@router.get("/reports/daily.pdf")
def daily_pdf(date: str, source: Source | None = None) -> Response:
    try:
        pdf = svc.daily_pdf(date, source)
    except svc.ReportNotReady as e:
        raise HTTPException(409, str(e)) from None
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="vidyut-report-{date}.pdf"'})
````

#### T13.4.5 — `backend/app/api/routes/setup.py`  ✅ Tested
**FILE: `backend/app/api/routes/setup.py`** — ✅ Tested

````python
"""Plant setup wizard API (first-open flow, Phase 16)."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.services import setup as svc

router = APIRouter(tags=["setup"])


@router.get("/setup/status")
def status() -> dict:
    return svc.status()


@router.get("/setup/options")
def options() -> dict:
    return svc.options()


@router.post("/setup")
def apply(body: svc.PlantSetup) -> dict:
    if svc.JOB["state"] == "running":
        raise HTTPException(409, "a setup job is already running — wait for it to finish")
    try:
        return svc.apply(body, pd.Timestamp.now(tz="UTC").isoformat())
    except (FileNotFoundError, ValidationError, ValueError) as e:
        raise HTTPException(422, str(e)) from None


@router.post("/setup/retrain")
def retrain() -> dict:
    try:
        return svc.start_retrain(pd.Timestamp.now(tz="UTC").isoformat())
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except FileNotFoundError as e:
        raise HTTPException(409, str(e)) from None
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


@router.get("/setup/job")
def job() -> dict:
    return dict(svc.JOB)
````

#### T13.4.6 — `backend/app/api/routes/notify.py` (contacts, test message, webhooks)  ✅ Tested
**FILE: `backend/app/api/routes/notify.py`** — ✅ Tested

````python
"""WhatsApp: contacts, test message, and inbound webhooks (Twilio + Meta) for YES/NO replies."""
from __future__ import annotations

import json

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlmodel import select

from app.db.models import Contact, log_event, session
from app.services import notify
from app.settings import get_settings

router = APIRouter(tags=["notify"])


class TestIn(BaseModel):
    to: str | None = None          # default: every opted-in contact


@router.get("/notify/contacts")
def contacts() -> list[dict]:
    with session() as s:
        return [c.model_dump() for c in s.exec(select(Contact))]


@router.get("/notify/status")
def status() -> dict:
    s = get_settings()
    return {"provider": s.notify_provider,
            "configured": s.notify_provider == "console"
            or (s.notify_provider == "twilio" and bool(s.twilio_account_sid and s.twilio_auth_token))
            or (s.notify_provider == "meta" and bool(s.meta_token and s.meta_phone_number_id)),
            "sandbox": s.notify_provider == "twilio" and s.twilio_whatsapp_from.endswith("14155238886")}


@router.post("/notify/test")
def test(body: TestIn) -> list[dict]:
    with session() as s:
        targets = [body.to] if body.to else [c.whatsapp for c in s.exec(select(Contact).where(Contact.opt_in == True))]
    if not targets:
        raise HTTPException(409, "no opted-in contacts; add one in Settings first")
    out = []
    for to in targets:
        r = notify.send(to, "✅ Vidyut test message — WhatsApp alerts are working.",
                        get_settings().meta_template_alert, ["TEST", "WhatsApp alerts are working", "now"])
        log_event(pd.Timestamp.now(tz="UTC").isoformat(), "whatsapp", f"Test to {to}: {'ok' if r.ok else 'FAILED'}",
                  {"detail": r.detail}, f"test-{to}")
        out.append({"to": to, "ok": r.ok, "provider": r.provider, "detail": r.detail})
    return out


@router.post("/webhooks/twilio")
async def twilio_webhook(request: Request) -> Response:
    form = {k: str(v) for k, v in (await request.form()).items()}
    if get_settings().webhook_verify_signatures:
        url = get_settings().public_api_url.rstrip("/") + "/webhooks/twilio"
        if not notify.twilio_signature_ok(url, form, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(403, "bad signature")
    reply = notify.handle_reply(form.get("From", ""), form.get("Body", ""))
    xml = "<Response>" + (f"<Message>{reply}</Message>" if reply else "") + "</Response>"
    return Response(xml, media_type="application/xml")


@router.get("/webhooks/meta", response_class=PlainTextResponse)
def meta_verify(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
                challenge: str = Query(alias="hub.challenge")) -> str:
    if mode == "subscribe" and token == get_settings().meta_verify_token:
        return challenge
    raise HTTPException(403, "verification failed")


@router.post("/webhooks/meta")
async def meta_webhook(request: Request) -> dict:
    raw = await request.body()
    if get_settings().webhook_verify_signatures and not notify.meta_signature_ok(
            raw, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(403, "bad signature")
    body = json.loads(raw or b"{}")
    for entry in body.get("entry", []):
        for ch in entry.get("changes", []):
            for m in ch.get("value", {}).get("messages", []):
                text = (m.get("text", {}).get("body") or m.get("button", {}).get("payload")
                        or m.get("interactive", {}).get("button_reply", {}).get("id") or "")
                reply = notify.handle_reply(m.get("from", ""), text)
                if reply:   # inside the 24 h window after the user's message free-form text is allowed
                    notify.send_text_meta(m.get("from", ""), reply)
    return {"ok": True}      # always 200 quickly, or Meta retries
````

#### T13.4.7 — `backend/app/main.py`  ✅ Tested
Registers the new routers and calls `materialize_plant_file()` right after the DB engine starts.
**FILE: `backend/app/main.py`** — ✅ Tested

````python
"""FastAPI application factory. Run: uvicorn app.main:app --reload --port 8000 (from backend/)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    alerts,
    assumptions,
    dispatch,
    dsm,
    forecast,
    health,
    impact,
    jobs,
    models,
    notify,
    reports,
    setup,
    whatif,
    workflow,
)
from app.db.models import engine, reseed_if_empty
from app.scheduler import ForecastJob, attach_loop
from app.services.runs import NoRunYet
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine()                                   # initialize DB tables (with fallback)
    from app.services.setup import materialize_plant_file
    materialize_plant_file()                   # plant setup lives in the DB; the free-tier disk is wiped on deploy
    reseed_if_empty()                          # re-seed if DB is empty
    from app.services import runs
    try:
        runs.latest()                          # warm caches
    except NoRunYet:
        pass
    app.state.subscribers = set()
    attach_loop(app)
    job = ForecastJob(app)
    if get_settings().scheduler_enabled:
        job.start()
    app.state.job = job
    yield
    if get_settings().scheduler_enabled:
        job.stop()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Vidyut API", version=s.version, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["*"], allow_headers=["*"])
    for r in (health, forecast, models, alerts, dispatch, whatif, dsm, impact, assumptions,
              workflow, reports, setup, notify, jobs):          # Phases 14-17
        app.include_router(r.router)

    @app.exception_handler(NoRunYet)
    async def no_run(_: Request, exc: NoRunYet):
        return JSONResponse(status_code=503, content={"error": {"code": "NO_DATA_YET", "message": str(exc)}})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL", "message": str(exc)}})

    return app


app = create_app()
````

---

### 13.5 Tests  ·  Depends on: 13.4

#### T13.5.1 — `backend/tests/test_workflow.py`  ✅ Tested
Covers: day-ahead proposal → accept → Rev 0 with stored quantiles → CSV; a deliberately low schedule → revision
recommended with triggers → WhatsApp `NO` reply rejects → newer one accepted → Rev 2 with the right effective
block → event-log kinds; unknown numbers ignored; Meta verification; profiles / explain / simulate (harsher rules
cost more, edits apply); report only after the day ended + PDF + realised simulation; `/jobs/tick` token and clock;
setup validation and a full solar-only setup (background refresh → `/site` says solar, wind 404); notify status.
The test points `PLANT_FILE` at a temp folder so your real `config/plant.yaml` is never touched. It writes forecast
runs into `artifacts/runs/` and leaves a hybrid reference run at the end, so `test_api.py` passes in any order.
**FILE: `backend/tests/test_workflow.py`** — ✅ Tested

````python
"""Operator workflow, reports, simulator, setup, jobs and WhatsApp webhook tests (Phases 12-17).

Needs what CI already builds before the backend tests: trained artifacts and data/processed/dataset.parquet
(`vidyut build-dataset --synthetic && vidyut frame && vidyut train && vidyut evaluate`). No network: the
WhatsApp provider is "console".
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd
import pytest

os.environ["VIDYUT_SCHEDULER_ENABLED"] = "false"
os.environ["VIDYUT_MODE"] = "replay"
os.environ["VIDYUT_DB_URL"] = "sqlite:///./test_workflow.db"
os.environ["VIDYUT_WEBHOOK_VERIFY_SIGNATURES"] = "false"
os.environ["VIDYUT_JOB_TOKEN"] = "test-token"
os.environ["VIDYUT_NOTIFY_PROVIDER"] = "console"
if os.path.exists("test_workflow.db"):
    os.remove("test_workflow.db")

from fastapi.testclient import TestClient
from sqlmodel import select
from vidyut import config as vcfg

from app.db import models as dbm
from app.db.models import Contact, ScheduleVersion, session
from app.main import app
from app.services import jobs, reports, runs, schedule
from app.services import setup as setup_svc
from app.settings import get_settings

get_settings.cache_clear()       # another test module may have imported the app with other settings
dbm.reset_engine()
reports.daily.cache_clear()
DAY = "2026-04-11"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    plant = tmp_path_factory.mktemp("cfg") / "plant.yaml"          # never touch the real config/plant.yaml
    old = vcfg.PLANT_FILE
    vcfg.PLANT_FILE = setup_svc.PLANT_FILE = plant
    vcfg.default_config.cache_clear()
    with TestClient(app) as c:
        yield c
    vcfg.PLANT_FILE = setup_svc.PLANT_FILE = old
    vcfg.default_config.cache_clear()
    from vidyut.pipelines.forecast import run_forecast  # leave a hybrid reference run for test_api.py
    run_forecast(vcfg.load_config(), "replay", "2026-04-10T00:00")


@pytest.fixture(scope="module")
def run(client):
    name = jobs.produce_run(at="2026-04-10T00:00", advance=False)   # also proposes the day-ahead schedule
    return runs.load(name)


def test_day_ahead_proposal_and_accept(client, run):
    pending = client.get("/recommendations?status=pending").json()
    da = [r for r in pending if r["kind"] == "day_ahead"]
    assert len(da) == 1 and da[0]["ist_date"] == DAY and "quantiles_json" not in da[0]["payload"]
    r = client.post(f"/recommendations/{da[0]['id']}/decision", json={"accept": True, "user": "asha", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert client.post(f"/recommendations/{da[0]['id']}/decision", json={"accept": True}).status_code == 409
    t = client.get(f"/schedule/today?date={DAY}").json()
    assert t["active"]["revision_no"] == 0 and len(t["active"]["mw"]) == 96
    with session() as s:
        v = s.exec(select(ScheduleVersion).where(ScheduleVersion.ist_date == DAY)).first()
        assert v.quantiles() is not None and len(v.quantiles()) == 96      # stored for the report
    csv = client.get(f"/schedule/active.csv?date={DAY}")
    assert csv.status_code == 200 and csv.text.startswith("block_no")


def test_revision_recommended_rejected_then_accepted(client, run):
    with session() as s:   # pretend the operator submitted a schedule far below the forecast
        v = s.exec(select(ScheduleVersion).where(ScheduleVersion.ist_date == DAY)).first()
        d = json.loads(v.blocks_json)
        s.add(ScheduleVersion(ist_date=DAY, source=v.source, revision_no=1, effective_from_block=1, run_name=v.run_name,
                              profile_id=v.profile_id, submitted_by="test",
                              blocks_json=json.dumps({"block_end_utc": d["block_end_utc"],
                                                      "mw": [m * 0.4 for m in d["mw"]]})))
        s.add(Contact(name="Asha", whatsapp="+919800000001", opt_in=True))
        s.commit()
    now = pd.Timestamp(f"{DAY} 10:00", tz="Asia/Kolkata").tz_convert("UTC")
    ev = schedule.evaluate_after_run(run, now)
    assert ev["recommend"], ev["reason"]
    assert any(t["type"] in ("FORECAST_SHIFT", "BAND_BREACH_RISK") for t in ev["triggers"])
    # a WhatsApp reply decides it
    r = client.post("/webhooks/twilio", data={"From": "whatsapp:+919800000001", "Body": f"NO {ev['id'][-6:]}"})
    assert r.status_code == 200 and "REJECTED" in r.text
    ev2 = schedule.evaluate_after_run(run, now + pd.Timedelta(minutes=30))
    assert ev2["recommend"]
    r = client.post(f"/recommendations/{ev2['id']}/decision", json={"accept": True, "user": "asha"})
    assert r.status_code == 200
    t = client.get(f"/schedule/today?date={DAY}").json()
    assert t["active"]["revision_no"] == 2 and t["revisions_used"] == 2
    assert t["active"]["effective_from_block"] >= ev2["effective_from_block"]
    kinds = {e["kind"] for e in client.get("/events").json()}
    assert {"day_ahead_proposed", "day_ahead_submitted", "refresh", "recommendation", "rejected", "accepted",
            "whatsapp"} <= kinds


def test_unknown_number_and_bad_text(client):
    r = client.post("/webhooks/twilio", data={"From": "whatsapp:+10000000000", "Body": "YES abc"})
    assert r.text == "<Response></Response>"
    r = client.post("/webhooks/twilio", data={"From": "whatsapp:+919800000001", "Body": "hello"})
    assert "reply YES" in r.text


def test_meta_verify(client):
    r = client.get("/webhooks/meta", params={"hub.mode": "subscribe", "hub.verify_token": "vidyut-verify",
                                             "hub.challenge": "42"})
    assert r.text == "42"
    bad = client.get("/webhooks/meta", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"})
    assert bad.status_code == 403


def test_profiles_explain_simulate(client, run):
    p = client.get("/dsm/profiles").json()
    assert {x["id"] for x in p["all"]} >= {"cerc_2026", "gujarat_gerc_2019", "madhya_pradesh_mperc_2018"}
    e = client.post("/dsm/explain", json={"schedule_mw": 10, "actual_mw": 8.6, "source": "solar",
                                          "profile_id": "cerc_2026", "contract_rate_inr_per_kwh": 2.7}).json()
    assert e["steps"] and e["total_extra_inr"] >= 0
    base = client.post("/dsm/simulate", json={}).json()
    harsh = client.post("/dsm/simulate", json={"penalty_scale": 2}).json()
    assert base["mode"] == "expected" and len(base["blocks"]) == 96
    assert harsh["total_charge_inr"] >= base["total_charge_inr"]
    edit = client.post("/dsm/simulate", json={"edits": [{"from_block": 40, "to_block": 48, "mw": 0}]}).json()
    assert edit["blocks"][44]["schedule_mw"] == 0


def test_daily_report_and_pdf(client, run):
    assert DAY not in client.get("/reports/days").json()            # the replay clock is still on 10 Apr
    assert client.get(f"/reports/daily?date={DAY}").status_code == 409
    dbm.set_state(jobs.LAST, "2026-04-12T06:00:00+00:00")           # move the virtual clock past the day
    assert DAY in client.get("/reports/days").json()
    r = client.get(f"/reports/daily?date={DAY}")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["is_estimate"] and len(j["blocks"]) == 96 and j["revisions"]["accepted"] == 1
    pdf = client.get(f"/reports/daily.pdf?date={DAY}")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    realised = client.post("/dsm/simulate", json={"day": DAY}).json()
    assert realised["mode"] == "realised"


def test_jobs_tick_needs_token_and_advances_clock(client, run):
    assert client.post("/jobs/tick").status_code == 401
    before = jobs.next_replay_time()
    r = client.post("/jobs/tick", headers={"X-Job-Token": "test-token"})
    assert r.status_code == 200, r.text
    assert jobs.next_replay_time() > before


def test_setup_validation_and_solar_only_plant(client, run):
    o = client.get("/setup/options").json()
    assert "Madhya Pradesh" in o["states"] and o["turbine_types"] and o["plant_types"] == ["solar", "wind", "hybrid"]
    base = {**o["defaults"], "plant_name": "Ujjain Solar", "contacts": []}
    assert client.post("/setup", json={**base, "latitude": 51.5}).status_code == 422          # outside India
    assert client.post("/setup", json={**base, "plant_type": "wind", "turbine_type": None}).status_code == 422
    r = client.post("/setup", json={**base, "plant_type": "solar", "solar_ac_mw": 20, "solar_dc_mw": 25,
                                    "demand_peak_mw": 15})
    assert r.status_code == 200, r.text
    for _ in range(120):                                  # background refresh produces a solar-only run
        if setup_svc.JOB["state"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert setup_svc.JOB["state"] == "done", setup_svc.JOB
    site = client.get("/site").json()
    assert site["plant_type"] == "solar" and site["output_sources"] == ["solar"]
    assert client.get("/forecast?source=wind").status_code == 404
    assert client.get("/forecast").json()["source"] == "solar"
    assert client.get("/setup/status").json()["configured"] is True


def test_notify_status_and_test(client):
    assert client.get("/notify/status").json()["provider"] == "console"
    r = client.post("/notify/test", json={})
    assert r.status_code in (200, 409)                    # 409 when setup replaced the contacts with none
````

#### T13.5.2 — Run everything  📝
```bash
vidyut forecast --mode replay                       # a fresh hybrid run with blocks.parquet
cd backend && rm -f test_*.db && VIDYUT_SCHEDULER_ENABLED=false pytest -q    # 35 passed
cd .. && ruff check ml backend
```

#### T13.5.3 — Click through the API  📝
```bash
cd backend && VIDYUT_SCHEDULER_ENABLED=false VIDYUT_JOB_TOKEN=t VIDYUT_REPLAY_AUTOACCEPT_DAYAHEAD=true \
  uvicorn app.main:app --port 8000
# second terminal:
for i in $(seq 1 9); do curl -s -X POST -H "X-Job-Token: t" localhost:8000/jobs/tick; echo; done
curl -s "localhost:8000/events?kind=refresh" | python -m json.tool | grep title
curl -s localhost:8000/reports/days                 # ["2026-04-11"]: 9 ticks x 6 h moved the virtual clock past that IST day
curl -s -o report.pdf "localhost:8000/reports/daily.pdf?date=2026-04-11" && file report.pdf
```
Open `http://localhost:8000/docs` — every route of §D is listed.

**Demo tip — getting a revision on stage.** Replay forecasts of consecutive runs are close to each other, so
revisions are rare (that is correct behaviour). To show one reliably, lower the trigger for the demo plant in
`config/plant.yaml` (`revision: {shift_trigger_pct: 2.0, min_saving_inr: 100}`) or pick a replay start just before
a front/monsoon change in the test period (look for a day where `/forecast` P50 moves > 5 % between runs).

---

## PHASE 14 — Frontend: Revisions & Log, simulator, charge explanation, report, setup, settings (Day 2–4)

Goal: the operator-facing pages. Dev B can start 14.1–14.2 as soon as the §D contract is agreed (mock with the
example JSON from `http://localhost:8000/docs` once Dev A's Phase 13 runs).

Rules for these pages (same as Phase 7): all data through hooks (`hooks/workflow.ts`), every panel wrapped in
`QueryState` (it already handles Render cold starts), IST in the UI, no browser storage for anything important,
no `setState` inside `useEffect` (the project's eslint config rejects it — derive values instead, or re-mount a
component with `key=`).

New navigation: **Revisions & Log** (after Trust), **Daily Report** (after Deviation Shield), **Settings** (last).
The setup wizard is reached automatically on first open and from Settings.

---

### 14.1 Types, hooks, navigation  ·  Owner: Dev B  ·  Depends on: 13.4 (or the §D contract)

#### T14.1.1 — `frontend/src/lib/api/workflow.ts`  ✅ Tested
These endpoints return plain dicts, so their TypeScript types are written by hand (keep them in sync with the
Python files named at the top).
**FILE: `frontend/src/lib/api/workflow.ts`** — ✅ Tested

````typescript
/** Types for the operator-workflow endpoints (they return plain dicts, so these are written by hand —
 *  keep them in sync with backend/app/api/routes/{workflow,setup,reports,notify,dsm}.py). */
import type { Source } from "./types";

export type Trigger = { type: "BAND_BREACH_RISK" | "FORECAST_SHIFT" | "ALERT" | "LOW_TRUST" | "BLOCKED"; detail: string; highlight: boolean };

export type RevisionPayload = {
  id: string; evaluated_at_utc: string; ist_date: string; source: Source; profile_id: string; recommend: boolean;
  reason: string; effective_from_utc: string | null; effective_from_block: number | null; notice_block: number | null;
  window_blocks: number[]; window_end_utc: string[]; current_mw: number[]; proposed_mw: number[];
  expected_charge_current_inr: number; expected_charge_proposed_inr: number; expected_saving_inr: number;
  max_p_breach: number; mean_shift_pct: number; revisions_used: number; max_revisions: number;
  triggers: Trigger[]; explanation: string[];
};
export type DayAheadPayload = {
  reason: string; deadline_ist: string; profile_id: string; profile_reason: string; level: number;
  blocks_json: string; energy_mwh: number; expected_saving_inr: number; effective_from_block: number;
};
export type Recommendation = {
  id: string; kind: "day_ahead" | "revision"; ist_date: string; status: "pending" | "accepted" | "rejected" | "superseded";
  run_name: string; created_at: string; decided_by: string | null; decision_note: string | null;
  payload: RevisionPayload | DayAheadPayload;
};
export type ScheduleVersion = {
  ist_date: string; source: Source; revision_no: number; effective_from_block: number; run_name: string;
  recommendation_id: string | null; profile_id: string; submitted_by: string; created_at: string;
  block_end_utc: string[]; mw: number[];
};
export type RuleProfileSummary = {
  id: string; name: string; status: "verified" | "partially_verified" | "unverified_template"; states: string[];
  jurisdiction: string; tolerance_pct: Record<Source, number>; rate_type: string; notes: string; sources: string[];
  revisions: { max_per_day: Record<Source, number>; effective_from_block: number; one_per_slot_hours: number | null;
    min_change_pct: number; solar_window_ist: [string, string] | null };
  day_ahead: { deadline_ist: string };
};
export type TodaySchedule = {
  ist_date: string; source: Source; profile: RuleProfileSummary; profile_reason: string; revisions_used: number;
  max_revisions: number; active: ScheduleVersion | null; versions: ScheduleVersion[]; now_utc: string;
};
export type EventRow = { id: number; ts_utc: string; kind: string; title: string; ref_id: string | null; detail: Record<string, unknown> };

export type ChargeExplanation = {
  schedule_mw: number; actual_mw: number; deviation_mw: number; deviation_pct: number; denominator_mw: number;
  direction: string; total_extra_inr: number; steps: string[]; profile_id: string; profile_status: string;
  bands: { band: string; deviation_points_pct: number; energy_kwh: number; rule: string; extra_inr: number }[];
};
export type BlockEdit = { from_block: number; to_block: number; mw: number };
export type SimInput = {
  profile_id?: string | null; contract_rate_inr_per_kwh?: number | null; tolerance_override_pct?: number | null;
  penalty_scale: number; schedule_level: number; edits: BlockEdit[]; source?: Source | null; day: string;
};
export type SimBlock = { block_no: number; block_end_utc: string; schedule_mw: number; p50_mw: number; p10_mw: number; p90_mw: number; actual_mw: number | null; charge_inr: number; p_outside_tolerance: number };
export type SimResult = {
  day: string; mode: "expected" | "realised"; source: Source; profile: RuleProfileSummary; contract_rate_inr_per_kwh: number;
  total_charge_inr: number; baseline_p50_charge_inr: number; saving_vs_p50_inr: number;
  blocks_likely_outside_tolerance: number; blocks: SimBlock[];
};

export type DailyReport = {
  date_ist: string; plant: string; source: Source; capacity_mw: number; profile: RuleProfileSummary; profile_reason: string;
  contract_rate_inr_per_kwh: number; is_estimate: true;
  energy: { forecast_p50_mwh: number; actual_mwh: number; scheduled_final_mwh: number };
  accuracy: { mae_mw: number | null; rmse_mw: number | null; nmae_pct: number | null; band80_coverage: number | null };
  deviation: { tolerance_pct: number; blocks_outside_tolerance: number; estimated_charges_inr: number;
    charges_if_no_revision_inr: number; saved_by_revisions_inr: number; worst_blocks: ChargeExplanation[] };
  revisions: { recommended: number; accepted: number; rejected: number;
    items: { id: string; status: string; effective_from_block: number; expected_saving_inr: number; reason: string; decided_by: string | null; decision_note: string | null }[] };
  alerts: { count: number; by_type: Record<string, number> };
  blocks: { block_no: number; p10: number; p50: number; p90: number; actual: number; schedule_rev0: number; schedule_final: number; charge_inr: number }[];
};

export type Contact = { name: string; role: string; whatsapp: string; opt_in: boolean; min_severity: "info" | "warning" | "critical"; receive_revisions: boolean; receive_reports: boolean };
export type PlantType = "solar" | "wind" | "hybrid";
export type PlantSetup = {
  plant_name: string; plant_type: PlantType; owner: string; qca_name: string; state: string; district: string;
  interstate: boolean; rule_profile: string; contract_rate_inr_per_kwh: number;
  latitude: number; longitude: number; altitude_m: number;
  solar_dc_mw: number | null; solar_ac_mw: number | null; tilt_deg: number; azimuth_deg: number;
  turbine_type: string | null; n_turbines: number | null; hub_height_m: number;
  battery_mw: number; battery_mwh: number; demand_peak_mw: number; contacts: Contact[];
};
export type SetupJob = {
  kind: "" | "refresh" | "retrain"; state: "idle" | "running" | "done" | "failed" | "dispatched"; step: string;
  progress: number; error: string; url: string; started_at: string | null; finished_at: string | null;
};
export type PlantMapping = {
  plant_type: PlantType; sources: ("solar" | "wind")[]; total_source: Source; factors: Record<string, number>;
  distance_km: number; approximate: boolean; notes: string[]; missing: string[];
};
export type SetupStatus = {
  configured: boolean; plant_name: string; plant_type: PlantType; state: string; rule_profile: string;
  rule_profile_reason: string; mapping: PlantMapping; retrain_mode: "local" | "github" | "off"; job: SetupJob;
};
export type SetupOptions = {
  plant_types: PlantType[]; states: string[]; profiles: RuleProfileSummary[]; turbine_types: string[];
  defaults: Omit<PlantSetup, "contacts">;
};
export type NotifyStatus = { provider: "console" | "twilio" | "meta"; configured: boolean; sandbox: boolean };
export type TestResult = { to: string; ok: boolean; provider: string; detail: string };
````

#### T14.1.2 — `frontend/src/hooks/workflow.ts`  ✅ Tested
**FILE: `frontend/src/hooks/workflow.ts`** — ✅ Tested

````typescript
"use client";
/** Hooks for the operator workflow (revisions, event log, reports, setup, WhatsApp, simulator). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RETRY_CONFIG } from "@/hooks/api";
import { api } from "@/lib/api/client";
import type { Source } from "@/lib/api/types";
import type {
  ChargeExplanation, Contact, DailyReport, EventRow, NotifyStatus, PlantSetup, Recommendation, RuleProfileSummary,
  SetupJob, SetupOptions, SetupStatus, SimInput, SimResult, TestResult, TodaySchedule,
} from "@/lib/api/workflow";

const LIVE = { refetchInterval: 30_000, ...RETRY_CONFIG };
const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const useToday = (date?: string) =>
  useQuery({ queryKey: ["schedule-today", date], queryFn: () => api<TodaySchedule>(`/schedule/today${date ? `?date=${date}` : ""}`), ...LIVE });
export const useRecommendations = (status?: Recommendation["status"]) =>
  useQuery({ queryKey: ["recommendations", status], queryFn: () => api<Recommendation[]>(`/recommendations${status ? `?status=${status}` : ""}`), ...LIVE });
export const useEvents = (kind?: string) =>
  useQuery({ queryKey: ["events", kind], queryFn: () => api<EventRow[]>(`/events${kind ? `?kind=${kind}` : ""}`), ...LIVE });

export function useDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; accept: boolean; user: string; note: string }) =>
      api<Recommendation>(`/recommendations/${encodeURIComponent(v.id)}/decision`, post({ accept: v.accept, user: v.user, note: v.note })),
    onSuccess: () => {
      for (const k of ["recommendations", "schedule-today", "events", "report-days"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });
}

export const useProfiles = () =>
  useQuery({ queryKey: ["profiles"], queryFn: () => api<{ active: RuleProfileSummary; reason: string; all: RuleProfileSummary[] }>("/dsm/profiles") });
export const useExplain = () =>
  useMutation({ mutationFn: (b: { schedule_mw: number; actual_mw: number; source?: Source; profile_id?: string; label?: string }) =>
    api<ChargeExplanation>("/dsm/explain", post(b)) });
export const useSimulate = () => useMutation({ mutationFn: (b: SimInput) => api<SimResult>("/dsm/simulate", post(b)) });

export const useReportDays = () => useQuery({ queryKey: ["report-days"], queryFn: () => api<string[]>("/reports/days") });
export const useDailyReport = (date: string | undefined) =>
  useQuery({ queryKey: ["report", date], enabled: !!date, retry: false, queryFn: () => api<DailyReport>(`/reports/daily?date=${date}`) });

export const useSetupStatus = () =>
  useQuery({ queryKey: ["setup-status"], queryFn: () => api<SetupStatus>("/setup/status"), ...RETRY_CONFIG });
export const useSetupOptions = () => useQuery({ queryKey: ["setup-options"], queryFn: () => api<SetupOptions>("/setup/options") });
export const useSetupJob = (enabled: boolean) =>
  useQuery({ queryKey: ["setup-job"], enabled, refetchInterval: enabled ? 2000 : false, queryFn: () => api<SetupJob>("/setup/job"),
    ...RETRY_CONFIG });
export function useApplySetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: PlantSetup) => api<SetupStatus & { market_changed: boolean }>("/setup", post(b)),
    onSuccess: () => qc.invalidateQueries(),
  });
}
export const useRetrain = () => useMutation({ mutationFn: () => api<SetupJob>("/setup/retrain", { method: "POST" }) });

export const useContacts = () => useQuery({ queryKey: ["contacts"], queryFn: () => api<Contact[]>("/notify/contacts") });
export const useNotifyStatus = () => useQuery({ queryKey: ["notify-status"], queryFn: () => api<NotifyStatus>("/notify/status") });
export const useTestWhatsApp = () => useMutation({ mutationFn: (to?: string) => api<TestResult[]>("/notify/test", post({ to })) });
````

#### T14.1.3 — `frontend/src/components/shell/nav.ts`  ✅ Tested
**FILE: `frontend/src/components/shell/nav.ts`** — ✅ Tested

````typescript
export const NAV = [
  { href: "/", label: "Control Room" },
  { href: "/forecast", label: "Forecast" },
  { href: "/models", label: "Models & Accuracy" },
  { href: "/trust", label: "Trust" },
  { href: "/revisions", label: "Revisions & Log" },
  { href: "/alerts", label: "Alerts" },
  { href: "/dispatch", label: "Dispatch" },
  { href: "/whatif", label: "What-if" },
  { href: "/deviation", label: "Deviation Shield" },
  { href: "/reports", label: "Daily Report" },
  { href: "/impact", label: "Impact" },
  { href: "/assumptions", label: "Assumptions" },
  { href: "/settings", label: "Settings" },
] as const;
````

#### T14.1.4 — Page titles  ✅ Tested
Create `layout.tsx` in each new route folder (`revisions`, `reports`, `settings`, `setup`) — same pattern as the
existing pages. Example for `frontend/src/app/revisions/layout.tsx` (use titles "Daily Report", "Settings",
"Plant Setup" for the others):
**FILE: `frontend/src/app/revisions/layout.tsx`** — ✅ Tested

````tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Revisions & Log",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
````

---

### 14.2 Deviation Shield: simulator + charge explanation  ·  Depends on: 14.1

#### T14.2.1 — `frontend/src/components/workflow/ChargeExplainer.tsx`  ✅ Tested
**FILE: `frontend/src/components/workflow/ChargeExplainer.tsx`** — ✅ Tested

````tsx
"use client";
/** Charge explanation: how one block's deviation charge is calculated, step by step. */
import { useEffect, useState } from "react";
import { Button, Card, CardTitle } from "@/components/ui/primitives";
import { useExplain } from "@/hooks/workflow";
import type { Source } from "@/lib/api/types";
import { inr } from "@/lib/format";

export type ExplainSeed = { schedule_mw: number; actual_mw: number; label: string } | null;

export default function ChargeExplainer({ seed, source, profileId }: { seed: ExplainSeed; source?: Source; profileId?: string }) {
  const ex = useExplain();
  // the parent re-mounts this component (key=...) for every new seed, so state starts from the seed
  const [s, setS] = useState(seed?.schedule_mw ?? 10);
  const [a, setA] = useState(seed?.actual_mw ?? 8.6);
  const label = seed?.label ?? "";
  const { mutate } = ex;
  useEffect(() => {
    if (seed) mutate({ schedule_mw: seed.schedule_mw, actual_mw: seed.actual_mw, source, profile_id: profileId, label: seed.label });
  }, [seed, source, profileId, mutate]);
  const field = "mt-1 w-28 rounded-lg border border-border bg-bg px-2 py-1";
  return (
    <Card id="explain">
      <CardTitle>Charge explanation</CardTitle>
      <div className="flex flex-wrap items-end gap-2 text-sm">
        <label>Scheduled MW<input type="number" step="0.1" className={`${field} block`} value={s} onChange={(e) => setS(Number(e.target.value))} /></label>
        <label>Actual MW<input type="number" step="0.1" className={`${field} block`} value={a} onChange={(e) => setA(Number(e.target.value))} /></label>
        <Button onClick={() => ex.mutate({ schedule_mw: s, actual_mw: a, source, profile_id: profileId, label })}>Explain</Button>
        <span className="text-xs text-muted">or click a block in the simulator table</span>
      </div>
      {ex.data && (
        <div className="mt-3 space-y-2 text-sm">
          <ol className="list-decimal space-y-1 pl-5">{ex.data.steps.map((x, i) => <li key={i}>{x}</li>)}</ol>
          {ex.data.bands.length > 0 && (
            <table className="w-full text-xs tabular-nums"><thead className="text-left text-muted"><tr><th>Band</th><th>Points</th><th>kWh</th><th>Rule</th><th>₹</th></tr></thead>
              <tbody>{ex.data.bands.map((b) => <tr key={b.band}><td>{b.band}</td><td>{b.deviation_points_pct}</td><td>{b.energy_kwh}</td><td>{b.rule}</td><td>{inr(b.extra_inr)}</td></tr>)}</tbody></table>
          )}
          <p className="font-semibold">Total for this block: {inr(ex.data.total_extra_inr)}</p>
        </div>
      )}
      {ex.error && <p className="mt-2 text-sm text-bad">{(ex.error as Error).message}</p>}
    </Card>
  );
}
````

#### T14.2.2 — `frontend/src/components/workflow/PenaltySimulator.tsx`  ✅ Tested
Debounced (250 ms) `POST /dsm/simulate`; waits for `/site` so a solar plant never asks for "hybrid"; clicking a row
of the block table sends that block to the Charge Explanation panel (for future days "actual" = P50).
**FILE: `frontend/src/components/workflow/PenaltySimulator.tsx`** — ✅ Tested

````tsx
"use client";
/** Penalty simulator: change the RULES (profile, rate, tolerance, harshness) and the SCHEDULE (level, block edits). */
import { useEffect, useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { Badge, Button, Card, CardTitle, Kpi, RangeInput } from "@/components/ui/primitives";
import SourceToggle from "@/components/ui/SourceToggle";
import { usePlant } from "@/hooks/plant";
import { useProfiles, useReportDays, useSimulate } from "@/hooks/workflow";
import type { Source } from "@/lib/api/types";
import type { BlockEdit, SimBlock } from "@/lib/api/workflow";
import { cssVar, inr } from "@/lib/format";
import type { ExplainSeed } from "./ChargeExplainer";

export default function PenaltySimulator({ onExplain }: { onExplain: (s: ExplainSeed, source: Source, profileId?: string) => void }) {
  const profiles = useProfiles();
  const days = useReportDays();
  const sim = useSimulate();
  const plant = usePlant();
  const [picked, setSource] = useState<Source | null>(null);
  const source: Source = picked && plant.outputs.includes(picked) ? picked : plant.total;
  const [profileId, setProfileId] = useState<string>("");
  const [rate, setRate] = useState<number | "">("");
  const [tol, setTol] = useState<number | "">("");
  const [scale, setScale] = useState(1);
  const [level, setLevel] = useState(0.5);
  const [day, setDay] = useState("next");
  const [edits, setEdits] = useState<BlockEdit[]>([]);
  const [draft, setDraft] = useState<BlockEdit>({ from_block: 40, to_block: 52, mw: 0 });
  const { mutate } = sim;

  const ready = plant.ready;
  useEffect(() => {
    if (!ready) return;                 // wait for /site so a solar plant never asks for "hybrid"
    const t = setTimeout(() => mutate({
      source, day, penalty_scale: scale, schedule_level: level, edits, profile_id: profileId || null,
      contract_rate_inr_per_kwh: rate === "" ? null : rate, tolerance_override_pct: tol === "" ? null : tol,
    }), 250);
    return () => clearTimeout(t);
  }, [ready, source, day, scale, level, edits, profileId, rate, tol, mutate]);

  const r = sim.data;
  const option = useMemo(() => !r ? {} : ({
    grid: { left: 48, right: 48, top: 30, bottom: 40 }, legend: { top: 0 }, tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: r.blocks.map((b) => b.block_no), name: "block (IST)", nameLocation: "middle", nameGap: 26 },
    yAxis: [{ type: "value", name: "MW" }, { type: "value", name: "₹", splitLine: { show: false } }],
    series: [
      { name: "P50", type: "line", data: r.blocks.map((b) => b.p50_mw), showSymbol: false, color: cssVar("--muted") },
      ...(r.mode === "realised" ? [{ name: "actual", type: "line", data: r.blocks.map((b) => b.actual_mw), showSymbol: false, color: cssVar("--text") }] : []),
      { name: "schedule", type: "line", step: "middle", data: r.blocks.map((b) => b.schedule_mw), showSymbol: false, color: cssVar("--hybrid") },
      { name: r.mode === "expected" ? "expected charge ₹" : "charge ₹", type: "bar", yAxisIndex: 1, data: r.blocks.map((b) => b.charge_inr), color: cssVar("--bad"), barWidth: 3 },
    ],
  }), [r]);

  const explain = (b: SimBlock) => onExplain({ schedule_mw: b.schedule_mw, actual_mw: b.actual_mw ?? b.p50_mw,
    label: `Block ${b.block_no}${b.actual_mw == null ? " (actual = P50 forecast)" : ""}: ` }, source, profileId || undefined);
  const field = "mt-1 block w-full rounded-lg border border-border bg-bg px-2 py-1";

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <CardTitle className="mr-auto mb-0">Penalty simulator</CardTitle>
        <SourceToggle include="outputs" value={source} onChange={setSource} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-3">
          <p className="text-xs font-semibold text-muted uppercase">Rules</p>
          <label className="block text-sm">Rule profile<select className={field} value={profileId} onChange={(e) => setProfileId(e.target.value)}>
            <option value="">Plant&apos;s profile ({profiles.data?.active.name ?? "…"})</option>
            {profiles.data?.all.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select></label>
          <label className="block text-sm">Contract rate ₹/kWh (blank = plant)<input type="number" step="0.05" className={field} value={rate} onChange={(e) => setRate(e.target.value === "" ? "" : Number(e.target.value))} /></label>
          <label className="block text-sm">Tolerance % (blank = profile)<input type="number" step="0.5" className={field} value={tol} onChange={(e) => setTol(e.target.value === "" ? "" : Number(e.target.value))} /></label>
          <RangeInput label="Penalty harshness" value={scale} min={0} max={3} step={0.25} onChange={setScale} format={(v) => `${v}×`} />
        </div>
        <div className="space-y-3">
          <p className="text-xs font-semibold text-muted uppercase">Schedule</p>
          <label className="block text-sm">Day<select className={field} value={day} onChange={(e) => setDay(e.target.value)}>
            <option value="next">Next day (expected charges)</option>
            {days.data?.map((d) => <option key={d} value={d}>{d} (realised)</option>)}
          </select></label>
          <RangeInput label="Schedule level" value={level} min={0.1} max={0.9} step={0.05} onChange={setLevel} format={(v) => `P${Math.round(v * 100)}`} />
          <div className="flex items-end gap-1 text-sm">
            <label>From<input type="number" min={1} max={96} className={field} value={draft.from_block} onChange={(e) => setDraft({ ...draft, from_block: Number(e.target.value) })} /></label>
            <label>To<input type="number" min={1} max={96} className={field} value={draft.to_block} onChange={(e) => setDraft({ ...draft, to_block: Number(e.target.value) })} /></label>
            <label>MW<input type="number" min={0} className={field} value={draft.mw} onChange={(e) => setDraft({ ...draft, mw: Number(e.target.value) })} /></label>
            <Button onClick={() => setEdits([...edits, draft])}>Add</Button>
          </div>
          <div className="flex flex-wrap gap-1">{edits.map((e, i) => <button key={i} onClick={() => setEdits(edits.filter((_, j) => j !== i))}><Badge>blocks {e.from_block}–{e.to_block} = {e.mw} MW ✕</Badge></button>)}</div>
        </div>
        <div className="grid grid-cols-2 content-start gap-2">
          <Kpi label={r?.mode === "realised" ? "Charges" : "Expected charges"} value={r ? inr(r.total_charge_inr) : "…"} />
          <Kpi label="vs P50 schedule" value={r ? inr(r.saving_vs_p50_inr) : "…"} hint="positive = cheaper" />
          <Kpi label="Blocks likely outside band" value={r ? String(r.blocks_likely_outside_tolerance) : "…"} />
          <Kpi label="Day" value={r?.day ?? "…"} />
        </div>
      </div>
      {sim.error && <p className="mt-2 text-sm text-bad">{(sim.error as Error).message}</p>}
      {r && <div className="mt-3"><EChart option={option} height={260} ariaLabel="Simulated schedule and charges per block" /></div>}
      {r && (
        <details className="mt-2"><summary className="cursor-pointer text-sm text-muted">Block table (click a row to explain its charge)</summary>
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-xs tabular-nums"><thead className="sticky top-0 bg-panel text-left text-muted"><tr><th>Block</th><th>Schedule</th><th>P10</th><th>P50</th><th>P90</th><th>Actual</th><th>P(outside)</th><th>₹</th></tr></thead>
              <tbody>{r.blocks.map((b) => (
                <tr key={b.block_no} className="cursor-pointer hover:bg-border/50" onClick={() => explain(b)}>
                  <td>{b.block_no}</td><td>{b.schedule_mw}</td><td>{b.p10_mw}</td><td>{b.p50_mw}</td><td>{b.p90_mw}</td><td>{b.actual_mw ?? "—"}</td><td>{Math.round(b.p_outside_tolerance * 100)}%</td><td>{inr(b.charge_inr)}</td>
                </tr>))}</tbody></table>
          </div>
        </details>
      )}
    </Card>
  );
}
````

#### T14.2.3 — `frontend/src/app/deviation/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/deviation/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Deviation Shield (H5 + Phases 12-13): rule profile in force, DSM charges by strategy (test period),
 *  penalty simulator, charge explanation, and the next-day 96-block schedule download. */
import { useState } from "react";
import { Badge, Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import ChargeExplainer, { type ExplainSeed } from "@/components/workflow/ChargeExplainer";
import PenaltySimulator from "@/components/workflow/PenaltySimulator";
import { useDsm } from "@/hooks/api";
import { SOURCE_LABEL, usePlant } from "@/hooks/plant";
import { API_BASE } from "@/lib/api/client";
import type { Source } from "@/lib/api/types";
import { inr, pct } from "@/lib/format";

export default function DeviationPage() {
  const dsm = useDsm();
  const plant = usePlant();
  const [seed, setSeed] = useState<{ seed: ExplainSeed; source?: Source; profileId?: string }>({ seed: null });
  const profile = dsm.data?.profile as { name?: string; status?: string } | undefined;
  const rows = (dsm.data?.rows ?? []).filter((r) => plant.outputs.includes(r.source as Source));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Deviation Shield</h1>
        {profile?.name && <Badge tone={profile.status === "verified" ? "good" : "warn"}>{profile.name} · {String(profile.status).replaceAll("_", " ")}</Badge>}
        {dsm.data?.illustrative_rates && <Badge tone="warn">Illustrative rates — verify before quoting</Badge>}
      </div>
      <Card>
        <CardTitle>Estimated deviation charges on held-out days (15-min blocks, day-ahead schedule)</CardTitle>
        <QueryState isLoading={dsm.isLoading} error={dsm.error} refetch={dsm.refetch}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-muted"><tr><th className="px-2 py-1">Source</th><th className="px-2 py-1">Schedule from</th><th className="px-2 py-1">Charges</th><th className="px-2 py-1">Blocks outside tolerance</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.source + r.strategy} className={r.strategy === "vidyut_optimized" ? "font-semibold" : ""}>
                    <td className="px-2 py-1">{SOURCE_LABEL[r.source as Source] ?? r.source}</td>
                    <td className="px-2 py-1">{r.strategy.replace("_", " ")}</td>
                    <td className="px-2 py-1">{inr(r.charge_inr)}</td>
                    <td className="px-2 py-1">{pct(r.blocks_outside_tolerance_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {dsm.data && <p className="mt-2 text-xs text-muted">Optimised schedule level: {Object.entries(dsm.data.chosen_level).filter(([k]) => plant.outputs.includes(k as Source)).map(([k, v]) => `${SOURCE_LABEL[k as Source] ?? k} P${Math.round(v * 100)}`).join(", ")}. {dsm.data.profile_reason}{dsm.data.contract_rate_inr_per_kwh ? ` · contract rate ₹${dsm.data.contract_rate_inr_per_kwh}/kWh` : ""}. Measured on the reference plant (virtual twin).</p>}
        </QueryState>
      </Card>
      <PenaltySimulator onExplain={(s, source, profileId) => {
        setSeed({ seed: s, source, profileId });
        document.getElementById("explain")?.scrollIntoView({ behavior: "smooth" });
      }} />
      <ChargeExplainer key={JSON.stringify(seed)} seed={seed.seed} source={seed.source} profileId={seed.profileId} />
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Next-day schedule (96 × 15-min blocks, IST)</CardTitle>
          <p className="text-sm text-muted">Generated from the latest calibrated forecast. The accepted (active) schedule is on Revisions &amp; Log.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {plant.outputs.map((s) => (
            <a key={s} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-border/60"
              href={`${API_BASE}/dsm/schedule.csv?source=${s}`} download={`vidyut_schedule_${s}.csv`}>Download {SOURCE_LABEL[s].toLowerCase()} CSV</a>
          ))}
        </div>
      </Card>
    </div>
  );
}
````

---

### 14.3 Revisions & Log  ·  Depends on: 14.1

#### T14.3.1 — `frontend/src/components/workflow/RecommendationCard.tsx`  ✅ Tested
Highlighted triggers (left border), expected saving, effective block, revisions used, current-vs-proposed chart,
full explanation, name + note, Accept / Reject, and the reminder that Vidyut does not submit to the grid.
**FILE: `frontend/src/components/workflow/RecommendationCard.tsx`** — ✅ Tested

````tsx
"use client";
/** A pending recommendation: highlighted triggers, current vs proposed chart, explanation, Accept / Reject. */
import { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { useDecide } from "@/hooks/workflow";
import type { DayAheadPayload, Recommendation, RevisionPayload } from "@/lib/api/workflow";
import { cssVar, inr, toIST } from "@/lib/format";

function chartFor(rec: Recommendation) {
  if (rec.kind === "revision") {
    const p = rec.payload as RevisionPayload;
    return { x: p.window_blocks.map(String), a: p.current_mw, b: p.proposed_mw, aName: "submitted schedule", bName: "proposed revision" };
  }
  const d = JSON.parse((rec.payload as DayAheadPayload).blocks_json) as { mw: number[] };
  return { x: d.mw.map((_, i) => String(i + 1)), a: null, b: d.mw, aName: "", bName: "proposed day-ahead schedule" };
}

export default function RecommendationCard({ rec }: { rec: Recommendation }) {
  const decide = useDecide();
  const [user, setUser] = useState("");
  const [note, setNote] = useState("");
  const c = useMemo(() => chartFor(rec), [rec]);
  const option = useMemo(() => ({
    grid: { left: 48, right: 16, top: 30, bottom: 40 },
    legend: { top: 0 }, tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: c.x, name: "block (IST)", nameLocation: "middle", nameGap: 26 },
    yAxis: { type: "value", name: "MW" },
    series: [
      ...(c.a ? [{ name: c.aName, type: "line", step: "middle", data: c.a, showSymbol: false, lineStyle: { type: "dashed" }, color: cssVar("--muted") }] : []),
      { name: c.bName, type: "line", step: "middle", data: c.b, showSymbol: false, color: cssVar("--hybrid") },
    ],
  }), [c]);
  const rev = rec.kind === "revision" ? (rec.payload as RevisionPayload) : null;
  const da = rec.kind === "day_ahead" ? (rec.payload as DayAheadPayload) : null;
  const go = (accept: boolean) => decide.mutate({ id: rec.id, accept, user: user.trim() || "operator", note });

  return (
    <Card className="border-warn/60">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="warn">{rec.kind === "revision" ? "Revision recommended" : "Day-ahead schedule ready"}</Badge>
        <span className="font-mono text-xs text-muted">{rec.id}</span>
        <span className="ml-auto text-xs text-muted">created {toIST(rec.created_at)}</span>
      </div>
      <p className="mt-2 text-sm font-medium">{rec.payload.reason}</p>
      {rev && (
        <>
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            <Badge tone="good">Expected saving {inr(rev.expected_saving_inr)}</Badge>
            <Badge>From block {rev.effective_from_block}</Badge>
            <Badge>Revisions used {rev.revisions_used}/{rev.max_revisions}</Badge>
          </div>
          <ul className="mt-3 space-y-1" aria-label="Triggers">
            {rev.triggers.map((t, i) => (
              <li key={i} className={t.highlight ? "rounded-lg border-l-4 border-warn bg-warn/10 px-3 py-1.5 text-sm" : "px-3 py-1 text-sm text-muted"}>
                <b>{t.type.replaceAll("_", " ")}</b> — {t.detail}
              </li>
            ))}
          </ul>
        </>
      )}
      {da && <p className="mt-1 text-sm text-muted">Submit to SLDC via your QCA before {da.deadline_ist} IST · {da.energy_mwh.toFixed(0)} MWh · {da.profile_reason}</p>}
      <div className="mt-3"><EChart option={option} height={220} ariaLabel="Current versus proposed schedule" /></div>
      {rev && (
        <details className="mt-2 text-sm"><summary className="cursor-pointer text-muted">Why? Full explanation</summary>
          <ol className="mt-1 list-decimal pl-5 text-muted">{rev.explanation.map((l, i) => <li key={i}>{l}</li>)}</ol>
        </details>
      )}
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-sm">Your name<input className="mt-1 block rounded-lg border border-border bg-bg px-2 py-1" value={user} onChange={(e) => setUser(e.target.value)} placeholder="operator" /></label>
        <label className="min-w-48 flex-1 text-sm">Note (optional)<input className="mt-1 block w-full rounded-lg border border-border bg-bg px-2 py-1" value={note} onChange={(e) => setNote(e.target.value)} /></label>
        <Button className="border-good text-good" disabled={decide.isPending} onClick={() => go(true)}>Accept</Button>
        <Button className="border-bad text-bad" disabled={decide.isPending} onClick={() => go(false)}>Reject</Button>
      </div>
      {decide.error && <p className="mt-2 text-sm text-bad">{(decide.error as Error).message}</p>}
      <p className="mt-2 text-xs text-muted">Vidyut does not submit anything to the grid. After accepting, send the schedule to SLDC through your QCA.</p>
    </Card>
  );
}
````

#### T14.3.2 — `frontend/src/components/workflow/EventLog.tsx`  ✅ Tested
The explainability window: filter All / Refreshes / Recommendations / Decisions / WhatsApp; each row expands to its
triggers (highlighted) and explanation lines.
**FILE: `frontend/src/components/workflow/EventLog.tsx`** — ✅ Tested

````tsx
"use client";
/** Explainability log window: every refresh, recommendation, decision and WhatsApp message, newest first. */
import { useState } from "react";
import { Badge, Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useEvents } from "@/hooks/workflow";
import type { EventRow } from "@/lib/api/workflow";
import { toIST } from "@/lib/format";

const FILTERS = [
  { value: "all", label: "All" }, { value: "refresh", label: "Refreshes" }, { value: "recommendation", label: "Recommendations" },
  { value: "decisions", label: "Decisions" }, { value: "whatsapp", label: "WhatsApp" },
] as const;
type F = (typeof FILTERS)[number]["value"];
const DECISIONS = new Set(["accepted", "rejected", "superseded", "day_ahead_submitted", "day_ahead_proposed"]);
const TONE: Record<string, "good" | "warn" | "bad" | "hybrid" | "neutral"> = {
  recommendation: "warn", accepted: "good", day_ahead_submitted: "good", rejected: "bad", superseded: "neutral",
  whatsapp: "hybrid", refresh: "neutral", setup: "hybrid", day_ahead_proposed: "warn",
};

function Detail({ e }: { e: EventRow }) {
  const lines = (e.detail.explanation as string[] | undefined) ?? [];
  const triggers = (e.detail.triggers as { type: string; detail: string; highlight: boolean }[] | undefined) ?? [];
  if (!lines.length && !triggers.length) return <pre className="overflow-x-auto text-xs text-muted">{JSON.stringify(e.detail, null, 2)}</pre>;
  return (
    <div className="space-y-1 text-xs">
      {triggers.map((t, i) => (
        <div key={i} className={t.highlight ? "rounded bg-warn/15 px-2 py-1" : "px-2 py-1 text-muted"}>
          <b>{t.type.replaceAll("_", " ")}</b> — {t.detail}
        </div>
      ))}
      <ul className="list-disc pl-5 text-muted">{lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
    </div>
  );
}

export default function EventLog() {
  const [f, setF] = useState<F>("all");
  const q = useEvents(f === "all" || f === "decisions" ? undefined : f);
  const rows = (q.data ?? []).filter((e) => f !== "decisions" || DECISIONS.has(e.kind));
  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <CardTitle className="mr-auto mb-0">Event log</CardTitle>
        <Segmented label="Filter events" value={f} options={[...FILTERS]} onChange={setF} />
      </div>
      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch} empty={!rows.length} height="h-40">
        <ol className="max-h-[480px] space-y-1 overflow-y-auto" aria-label="Event log">
          {rows.map((e) => (
            <li key={e.id}>
              <details className="rounded-lg border border-border px-3 py-2">
                <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm">
                  <span className="w-32 shrink-0 text-xs text-muted tabular-nums">{toIST(e.ts_utc)}</span>
                  <Badge tone={TONE[e.kind] ?? "neutral"}>{e.kind.replaceAll("_", " ")}</Badge>
                  <span className="min-w-0 flex-1">{e.title}</span>
                </summary>
                <div className="mt-2"><Detail e={e} /></div>
              </details>
            </li>
          ))}
        </ol>
      </QueryState>
    </Card>
  );
}
````

#### T14.3.3 — `frontend/src/app/revisions/page.tsx`  ✅ Tested
**FILE: `frontend/src/app/revisions/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Revision Advisor: pending recommendations (accept / reject), today's schedule versions, explainability log. */
import { useMemo } from "react";
import EChart from "@/components/charts/EChart";
import { Badge, Card, CardTitle, Kpi } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import EventLog from "@/components/workflow/EventLog";
import RecommendationCard from "@/components/workflow/RecommendationCard";
import { useRecommendations, useToday } from "@/hooks/workflow";
import { API_BASE } from "@/lib/api/client";
import { cssVar } from "@/lib/format";

export default function RevisionsPage() {
  const pending = useRecommendations("pending");
  const today = useToday();
  const t = today.data;
  const option = useMemo(() => !t?.versions.length ? {} : ({
    grid: { left: 48, right: 16, top: 30, bottom: 40 }, legend: { top: 0 }, tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: t.versions[0].mw.map((_, i) => i + 1), name: "block (IST)", nameLocation: "middle", nameGap: 26 },
    yAxis: { type: "value", name: "MW" },
    series: t.versions.map((v, i) => ({
      name: `Rev ${v.revision_no}`, type: "line", step: "middle", showSymbol: false, data: v.mw,
      lineStyle: { width: i === t.versions.length - 1 ? 2.2 : 1, type: i === t.versions.length - 1 ? "solid" : "dashed" },
      color: i === t.versions.length - 1 ? cssVar("--hybrid") : undefined,
    })),
  }), [t]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Revisions &amp; Log</h1>
        {t && <Badge tone={t.profile.status === "verified" ? "good" : "warn"}>{t.profile.name} · {t.profile.status.replaceAll("_", " ")}</Badge>}
      </div>
      <QueryState isLoading={pending.isLoading} error={pending.error} refetch={pending.refetch} height="h-24">
        {pending.data?.length ? pending.data.map((r) => <RecommendationCard key={r.id} rec={r} />)
          : <Card className="text-sm text-muted">No pending recommendation — the submitted schedule is still the best choice. Vidyut re-checks after every forecast refresh.</Card>}
      </QueryState>
      <QueryState isLoading={today.isLoading} error={today.error} refetch={today.refetch} height="h-64">
        {t && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Kpi label="Schedule day (IST)" value={t.ist_date} />
              <Kpi label="Revisions used" value={`${t.revisions_used} / ${t.max_revisions}`} hint={`effective from the ${t.profile.revisions.effective_from_block}th block`} />
              <Kpi label="Active version" value={t.active ? `Rev ${t.active.revision_no}` : "none"} hint={t.active ? `by ${t.active.submitted_by}` : "no schedule submitted"} />
              <Kpi label="Day-ahead deadline" value={`${t.profile.day_ahead.deadline_ist} IST`} />
            </div>
            <Card>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="mr-auto mb-0">Schedule versions for {t.ist_date}</CardTitle>
                {t.active && <a className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-border/60" href={`${API_BASE}/schedule/active.csv?date=${t.ist_date}`}>Download active CSV</a>}
              </div>
              {t.versions.length ? <EChart option={option} height={260} ariaLabel="Schedule versions" />
                : <p className="text-sm text-muted">No schedule submitted for this day yet. Accept the day-ahead proposal when it appears.</p>}
            </Card>
          </>
        )}
      </QueryState>
      <EventLog />
    </div>
  );
}
````

---

### 14.4 Daily Report  ·  Depends on: 14.1

#### T14.4.1 — `frontend/src/app/reports/page.tsx`  ✅ Tested
Day picker (newest finished day by default), KPI row, forecast/schedule/actual chart with ₹ per block, the most
expensive blocks explained, revisions table, **Download PDF** (`/reports/daily.pdf`), "ESTIMATE" badge.
**FILE: `frontend/src/app/reports/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Daily accuracy & estimated deviation report: KPIs, chart, most expensive blocks explained, PDF export. */
import { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { Badge, Card, CardTitle, Kpi } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useDailyReport, useReportDays } from "@/hooks/workflow";
import { API_BASE } from "@/lib/api/client";
import { cssVar, inr, mw, pct } from "@/lib/format";

export default function ReportsPage() {
  const days = useReportDays();
  const [picked, setDay] = useState<string>();
  const day = picked ?? days.data?.[0];            // newest day until the user picks one
  const rep = useDailyReport(day);
  const r = rep.data;
  const option = useMemo(() => !r ? {} : ({
    grid: { left: 48, right: 16, top: 30, bottom: 40 }, legend: { top: 0 }, tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: r.blocks.map((b) => b.block_no), name: "block (IST)", nameLocation: "middle", nameGap: 26 },
    yAxis: [{ type: "value", name: "MW" }, { type: "value", name: "₹ / block", splitLine: { show: false } }],
    series: [
      { name: "P10", type: "line", data: r.blocks.map((b) => b.p10), stack: "band", lineStyle: { opacity: 0 }, showSymbol: false, tooltip: { show: false } },
      { name: "P10–P90", type: "line", data: r.blocks.map((b) => b.p90 - b.p10), stack: "band", lineStyle: { opacity: 0 }, areaStyle: { opacity: 0.2 }, showSymbol: false, color: cssVar("--hybrid") },
      { name: "actual", type: "line", data: r.blocks.map((b) => b.actual), showSymbol: false, color: cssVar("--text") },
      { name: "final schedule", type: "line", step: "middle", data: r.blocks.map((b) => b.schedule_final), showSymbol: false, color: cssVar("--hybrid") },
      { name: "Rev 0", type: "line", step: "middle", data: r.blocks.map((b) => b.schedule_rev0), showSymbol: false, lineStyle: { type: "dashed" }, color: cssVar("--muted") },
      { name: "charge ₹", type: "bar", yAxisIndex: 1, data: r.blocks.map((b) => b.charge_inr), color: cssVar("--bad"), barWidth: 3 },
    ],
  }), [r]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Daily Report</h1>
        <label className="text-sm">Day (IST){" "}
          <select className="rounded-lg border border-border bg-bg px-2 py-1" value={day ?? ""} onChange={(e) => setDay(e.target.value)}>
            {(days.data ?? []).map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
        {r && <a className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-border/60" href={`${API_BASE}/reports/daily.pdf?date=${r.date_ist}`}>Download PDF</a>}
      </div>
      {!days.isLoading && !days.data?.length && <Card className="text-sm text-muted">No report yet: a report appears once a day-ahead schedule has been accepted and the day has passed.</Card>}
      {day && (
        <QueryState isLoading={rep.isLoading} error={rep.error} refetch={rep.refetch}>
          {r && (
            <>
              <Badge tone="warn">ESTIMATE — the official DSM account is issued by the load despatch centre · {r.profile.name}</Badge>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Kpi label="Actual energy" value={`${r.energy.actual_mwh.toFixed(1)} MWh`} hint={`forecast P50 ${r.energy.forecast_p50_mwh.toFixed(1)} MWh`} />
                <Kpi label="Forecast error (nMAE)" value={r.accuracy.nmae_pct == null ? "—" : pct(r.accuracy.nmae_pct)}
                  hint={`MAE ${r.accuracy.mae_mw == null ? "—" : mw(r.accuracy.mae_mw, 2)} · 80% band covered ${r.accuracy.band80_coverage == null ? "—" : Math.round(r.accuracy.band80_coverage * 100) + "%"}`} />
                <Kpi label="Estimated deviation charges" value={inr(r.deviation.estimated_charges_inr)} hint={`${r.deviation.blocks_outside_tolerance}/96 blocks outside ±${r.deviation.tolerance_pct}%`} />
                <Kpi label="Saved by revisions" value={inr(r.deviation.saved_by_revisions_inr)} hint={`${r.revisions.accepted} accepted / ${r.revisions.recommended} recommended`} />
              </div>
              <Card><EChart option={option} height={300} ariaLabel="Forecast, schedule, actual and charge per block" /></Card>
              <Card>
                <CardTitle>Most expensive blocks — how each charge was calculated</CardTitle>
                {r.deviation.worst_blocks.length ? r.deviation.worst_blocks.map((w, i) => (
                  <ol key={i} className="mb-3 list-decimal pl-5 text-sm">{w.steps.map((s, j) => <li key={j}>{s}</li>)}</ol>
                )) : <p className="text-sm text-muted">No block was charged on this day.</p>}
              </Card>
              <Card>
                <CardTitle>Revisions</CardTitle>
                {r.revisions.items.length ? (
                  <table className="w-full text-sm"><thead className="text-left text-muted"><tr><th>ID</th><th>Status</th><th>From block</th><th>Expected saving</th><th>Decided by</th></tr></thead>
                    <tbody>{r.revisions.items.map((x) => <tr key={x.id}><td className="font-mono text-xs">{x.id}</td><td>{x.status}</td><td>{x.effective_from_block}</td><td>{inr(x.expected_saving_inr ?? 0)}</td><td>{x.decided_by ?? "—"}</td></tr>)}</tbody></table>
                ) : <p className="text-sm text-muted">No revision was recommended.</p>}
              </Card>
            </>
          )}
        </QueryState>
      )}
    </div>
  );
}
````

---

### 14.5 Plant setup wizard  ·  Depends on: 14.1

#### T14.5.1 — `frontend/src/app/setup/page.tsx`  ✅ Tested
Step 1 plant type cards (Solar only / Wind only / Solar + wind) + name, state, location, QCA. Step 2 inter-state
toggle, rule profile (automatic shows which profile the state gets and whether it is verified), PPA rate, contracted
supply. Step 3 only the equipment of the chosen type + battery. Step 4 WhatsApp contacts with an explicit opt-in
checkbox. Step 5 review + validation; "Save & start" shows the background job progress and opens the Control Room
when done (or Settings if the trained models lack a source and need a retrain).
**FILE: `frontend/src/app/setup/page.tsx`** — ✅ Tested

````tsx
"use client";
/** First-open plant setup wizard (Phase 16): plant & type → market & rules → equipment → WhatsApp → review & save. */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Button, Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useApplySetup, useSetupJob, useSetupOptions } from "@/hooks/workflow";
import type { Contact, PlantSetup, PlantType, RuleProfileSummary } from "@/lib/api/workflow";
import { cn } from "@/lib/cn";

const STEPS = ["Plant", "Market & rules", "Equipment", "WhatsApp", "Review"] as const;
const E164 = /^\+[1-9]\d{7,14}$/;
const input = "mt-1 block w-full rounded-lg border border-border bg-bg px-2 py-1.5";
const TYPES: { value: PlantType; label: string; hint: string }[] = [
  { value: "solar", label: "Solar only", hint: "PV plant" },
  { value: "wind", label: "Wind only", hint: "wind farm" },
  { value: "hybrid", label: "Solar + wind", hint: "co-located hybrid" },
];

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return <label className="block text-sm">{label}{children}{hint && <span className="mt-0.5 block text-xs text-muted">{hint}</span>}</label>;
}

/** Same rule as vidyut.rules.resolve_profile_id (keep in sync). */
function resolve(f: PlantSetup, profiles: RuleProfileSummary[]): RuleProfileSummary | undefined {
  if (f.rule_profile !== "auto") return profiles.find((p) => p.id === f.rule_profile);
  if (f.interstate) return profiles.find((p) => p.id === "cerc_2026");
  return profiles.find((p) => p.states.includes(f.state)) ?? profiles.find((p) => p.id === "cerc_2026");
}

export default function SetupPage() {
  const opts = useSetupOptions();
  const apply = useApplySetup();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [edited, setF] = useState<PlantSetup | null>(null);
  // the form starts from the server defaults; the first edit copies them into state
  const f: PlantSetup | null = edited ?? (opts.data ? { contacts: [], ...opts.data.defaults } : null);
  const [started, setStarted] = useState(false);
  const job = useSetupJob(started);

  useEffect(() => { if (job.data?.state === "done") router.push("/"); }, [job.data, router]);

  const set = <K extends keyof PlantSetup>(k: K, v: PlantSetup[K]) => f && setF({ ...f, [k]: v });
  const num = (k: keyof PlantSetup) => (e: React.ChangeEvent<HTMLInputElement>) => set(k, Number(e.target.value) as never);
  const setContact = (i: number, c: Partial<Contact>) => f && set("contacts", f.contacts.map((x, j) => (j === i ? { ...x, ...c } : x)));
  const prof = f && opts.data ? resolve(f, opts.data.profiles) : undefined;
  const hasSolar = f?.plant_type !== "wind";
  const hasWind = f?.plant_type !== "solar";

  const errors: string[] = [];
  if (f) {
    if (f.plant_name.trim().length < 2) errors.push("Plant name is required");
    if (f.latitude < 6 || f.latitude > 37.5 || f.longitude < 68 || f.longitude > 97.5) errors.push("Location must be in India");
    if (hasSolar && (!f.solar_ac_mw || !f.solar_dc_mw)) errors.push("Solar DC and AC capacity are required");
    if (hasWind && (!f.n_turbines || !f.turbine_type)) errors.push("Turbine model and count are required");
    if (!(f.demand_peak_mw > 0)) errors.push("Contracted supply must be > 0");
    f.contacts.forEach((c, i) => { if (!E164.test(c.whatsapp)) errors.push(`Contact ${i + 1}: number must look like +919812345678`); });
  }

  async function save() {
    if (!f) return;
    const body: PlantSetup = {   // do not send equipment the plant does not have
      ...f,
      solar_ac_mw: hasSolar ? f.solar_ac_mw : null, solar_dc_mw: hasSolar ? f.solar_dc_mw : null,
      turbine_type: hasWind ? f.turbine_type : null, n_turbines: hasWind ? f.n_turbines : null,
    };
    const r = await apply.mutateAsync(body);
    if (r.mapping.missing.length) router.push("/settings");   // needs a retrain before forecasting
    else setStarted(true);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">Set up your plant</h1>
      <p className="text-sm text-muted">Done once by the plant engineer. You can change everything later in Settings.</p>
      <ol className="flex flex-wrap gap-2" aria-label="Setup steps">
        {STEPS.map((s, i) => <li key={s}><button onClick={() => setStep(i)} aria-current={i === step ? "step" : undefined}
          className={cn("rounded-full px-3 py-1 text-sm", i === step ? "bg-text text-bg" : "bg-border text-muted")}>{i + 1}. {s}</button></li>)}
      </ol>
      <QueryState isLoading={opts.isLoading || !f} error={opts.error} refetch={opts.refetch}>
        {f && opts.data && (
          <Card className="space-y-3">
            {step === 0 && (<>
              <CardTitle>Plant</CardTitle>
              <div role="radiogroup" aria-label="Plant type" className="grid gap-2 sm:grid-cols-3">
                {TYPES.map((t) => (
                  <button key={t.value} role="radio" aria-checked={f.plant_type === t.value} onClick={() => set("plant_type", t.value)}
                    className={cn("rounded-xl border p-3 text-left", f.plant_type === t.value ? "border-hybrid bg-hybrid/10" : "border-border")}>
                    <div className="font-medium">{t.label}</div><div className="text-xs text-muted">{t.hint}</div>
                  </button>
                ))}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Plant name"><input className={input} value={f.plant_name} onChange={(e) => set("plant_name", e.target.value)} /></Field>
                <Field label="Owner / company"><input className={input} value={f.owner} onChange={(e) => set("owner", e.target.value)} /></Field>
                <Field label="State"><select className={input} value={f.state} onChange={(e) => set("state", e.target.value)}>{opts.data.states.map((s) => <option key={s}>{s}</option>)}</select></Field>
                <Field label="District"><input className={input} value={f.district} onChange={(e) => set("district", e.target.value)} /></Field>
                <Field label="Latitude" hint="decimal degrees, e.g. 22.97"><input type="number" step="0.0001" className={input} value={f.latitude} onChange={num("latitude")} /></Field>
                <Field label="Longitude" hint="decimal degrees, e.g. 76.05"><input type="number" step="0.0001" className={input} value={f.longitude} onChange={num("longitude")} /></Field>
                <Field label="Altitude (m)"><input type="number" className={input} value={f.altitude_m} onChange={num("altitude_m")} /></Field>
                <Field label="QCA (scheduling agency)" hint="who submits your schedules to the SLDC"><input className={input} value={f.qca_name} onChange={(e) => set("qca_name", e.target.value)} /></Field>
              </div>
            </>)}
            {step === 1 && (<>
              <CardTitle>Market & deviation rules</CardTitle>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.interstate} onChange={(e) => set("interstate", e.target.checked)} /> Sells outside its state (inter-state, CERC rules apply)</label>
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Rule profile"><select className={input} value={f.rule_profile} onChange={(e) => set("rule_profile", e.target.value)}>
                  <option value="auto">Automatic (from state)</option>
                  {opts.data.profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select></Field>
                <Field label="Contract / PPA rate (₹/kWh)" hint="used to value deviation charges"><input type="number" step="0.01" className={input} value={f.contract_rate_inr_per_kwh} onChange={num("contract_rate_inr_per_kwh")} /></Field>
                <Field label="Contracted supply peak (MW)" hint="the load profile the plant + battery must serve"><input type="number" className={input} value={f.demand_peak_mw} onChange={num("demand_peak_mw")} /></Field>
              </div>
              {prof && (
                <div className="rounded-lg border border-border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2"><b>{prof.name}</b>
                    <Badge tone={prof.status === "verified" ? "good" : "warn"}>{prof.status.replaceAll("_", " ")}</Badge></div>
                  <p className="mt-1 text-muted">Tolerance: solar ±{prof.tolerance_pct.solar}%, wind ±{prof.tolerance_pct.wind}% · revisions/day: {prof.revisions.max_per_day[f.plant_type]} · day-ahead deadline {prof.day_ahead.deadline_ist} IST</p>
                  {prof.status !== "verified" && <p className="mt-1 text-warn">Some values in this profile are not verified from the regulation text. Estimates are illustrative.</p>}
                </div>
              )}
            </>)}
            {step === 2 && (<>
              <CardTitle>Equipment</CardTitle>
              {hasSolar && <div className="grid gap-3 md:grid-cols-4">
                <Field label="Solar DC (MWp)"><input type="number" className={input} value={f.solar_dc_mw ?? ""} onChange={num("solar_dc_mw")} /></Field>
                <Field label="Solar AC (MW)"><input type="number" className={input} value={f.solar_ac_mw ?? ""} onChange={num("solar_ac_mw")} /></Field>
                <Field label="Tilt (°)"><input type="number" className={input} value={f.tilt_deg} onChange={num("tilt_deg")} /></Field>
                <Field label="Azimuth (°)" hint="180 = facing south"><input type="number" className={input} value={f.azimuth_deg} onChange={num("azimuth_deg")} /></Field>
              </div>}
              {hasWind && <div className="grid gap-3 md:grid-cols-3">
                <Field label="Turbine model"><select className={input} value={f.turbine_type ?? ""} onChange={(e) => set("turbine_type", e.target.value)}>{opts.data.turbine_types.map((t) => <option key={t}>{t}</option>)}</select></Field>
                <Field label="Number of turbines"><input type="number" className={input} value={f.n_turbines ?? ""} onChange={num("n_turbines")} /></Field>
                <Field label="Hub height (m)"><input type="number" className={input} value={f.hub_height_m} onChange={num("hub_height_m")} /></Field>
              </div>}
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Battery power (MW)" hint="0 if there is no battery"><input type="number" className={input} value={f.battery_mw} onChange={num("battery_mw")} /></Field>
                <Field label="Battery energy (MWh)"><input type="number" className={input} value={f.battery_mwh} onChange={num("battery_mwh")} /></Field>
              </div>
              <p className="text-xs text-muted">Forecasts are scaled from the trained reference plant at once. If your plant is far away or uses different equipment, Settings offers a retrain for your exact plant.</p>
            </>)}
            {step === 3 && (<>
              <CardTitle>WhatsApp alerts</CardTitle>
              <p className="text-sm text-muted">Each person must agree to receive WhatsApp messages from the plant (WhatsApp policy). Numbers with country code, e.g. +919812345678.</p>
              {f.contacts.map((c, i) => (
                <div key={i} className="grid gap-2 rounded-lg border border-border p-3 md:grid-cols-4">
                  <Field label="Name"><input className={input} value={c.name} onChange={(e) => setContact(i, { name: e.target.value })} /></Field>
                  <Field label="Role"><select className={input} value={c.role} onChange={(e) => setContact(i, { role: e.target.value })}><option>operator</option><option>manager</option><option>qca</option></select></Field>
                  <Field label="WhatsApp number"><input className={input} value={c.whatsapp} onChange={(e) => setContact(i, { whatsapp: e.target.value.trim() })} /></Field>
                  <Field label="Alerts from"><select className={input} value={c.min_severity} onChange={(e) => setContact(i, { min_severity: e.target.value as Contact["min_severity"] })}><option value="info">info</option><option value="warning">warning</option><option value="critical">critical only</option></select></Field>
                  <label className="flex items-center gap-2 text-sm md:col-span-2"><input type="checkbox" checked={c.opt_in} onChange={(e) => setContact(i, { opt_in: e.target.checked })} /> This person agreed to receive Vidyut messages on WhatsApp</label>
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={c.receive_revisions} onChange={(e) => setContact(i, { receive_revisions: e.target.checked })} /> Revision requests</label>
                  <Button onClick={() => set("contacts", f.contacts.filter((_, j) => j !== i))}>Remove</Button>
                </div>
              ))}
              <Button onClick={() => set("contacts", [...f.contacts, { name: "", role: "operator", whatsapp: "+91", opt_in: false, min_severity: "warning", receive_revisions: true, receive_reports: true }])}>+ Add contact</Button>
            </>)}
            {step === 4 && (<>
              <CardTitle>Review</CardTitle>
              <dl className="grid grid-cols-2 gap-1 text-sm">
                <dt className="text-muted">Plant</dt><dd>{f.plant_name}, {f.district} ({f.state})</dd>
                <dt className="text-muted">Type</dt><dd>{TYPES.find((t) => t.value === f.plant_type)?.label}</dd>
                <dt className="text-muted">Rules</dt><dd>{prof?.name}</dd>
                <dt className="text-muted">Capacity</dt><dd>{[hasSolar && `Solar ${f.solar_ac_mw} MW AC`, hasWind && `Wind ${f.n_turbines} × ${f.turbine_type}`].filter(Boolean).join(" · ")}</dd>
                <dt className="text-muted">Battery</dt><dd>{f.battery_mw} MW / {f.battery_mwh} MWh</dd>
                <dt className="text-muted">WhatsApp contacts</dt><dd>{f.contacts.length} ({f.contacts.filter((c) => c.opt_in).length} opted in)</dd>
              </dl>
              {errors.length > 0 && <ul className="list-disc pl-5 text-sm text-bad">{errors.map((e) => <li key={e}>{e}</li>)}</ul>}
              {apply.error && <p className="text-sm text-bad">{(apply.error as Error).message}</p>}
              {started && job.data && (
                <div aria-live="polite" className="space-y-1 text-sm">
                  <div>{job.data.state === "failed" ? <span className="text-bad">Setup failed: {job.data.error}</span> : <>{job.data.step || "Starting"}… {job.data.progress}%</>}</div>
                  <div className="h-2 rounded bg-border"><div className="h-2 rounded bg-hybrid" style={{ width: `${job.data.progress}%` }} /></div>
                </div>
              )}
            </>)}
            <div className="flex justify-between pt-2">
              <Button disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
              {step < STEPS.length - 1 ? <Button active onClick={() => setStep(step + 1)}>Next</Button>
                : <Button active disabled={errors.length > 0 || apply.isPending || started} onClick={save}>Save & start</Button>}
            </div>
          </Card>
        )}
      </QueryState>
    </div>
  );
}
````

---

### 14.6 Settings  ·  Depends on: 14.1

#### T14.6.1 — `frontend/src/app/settings/page.tsx`  ✅ Tested
Plant summary + "Edit plant setup"; **Forecast models for this plant** card (matched / approximate / retrain
required, scale factors, distance, notes, "Retrain for this plant" with progress or a GitHub Actions link); rule
profile in force with its sources; WhatsApp provider status, "Send test message", contacts table.
**FILE: `frontend/src/app/settings/page.tsx`** — ✅ Tested

````tsx
"use client";
/** Settings: plant summary, rule profile (with sources), WhatsApp provider status, contacts and test message. */
import Link from "next/link";
import { Badge, Button, Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useContacts, useNotifyStatus, useProfiles, useRetrain, useSetupJob, useSetupStatus, useTestWhatsApp } from "@/hooks/workflow";

export default function SettingsPage() {
  const st = useSetupStatus();
  const prof = useProfiles();
  const contacts = useContacts();
  const ns = useNotifyStatus();
  const test = useTestWhatsApp();
  const retrain = useRetrain();
  const job = useSetupJob(retrain.isSuccess);
  const m = st.data?.mapping;
  const j = job.data ?? retrain.data;
  const p = prof.data?.active;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Settings</h1>
        <Link className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-border/60" href="/setup">Edit plant setup</Link>
      </div>
      <Card>
        <CardTitle>Plant</CardTitle>
        <QueryState isLoading={st.isLoading} error={st.error} refetch={st.refetch} height="h-16">
          <p className="text-sm">{st.data?.plant_name} · {st.data?.plant_type} · {st.data?.state}{!st.data?.configured && <Badge tone="warn" className="ml-2">using defaults — run setup</Badge>}</p>
        </QueryState>
      </Card>
      {m && (
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="mr-auto mb-0">Forecast models for this plant</CardTitle>
            <Badge tone={m.missing.length ? "bad" : m.approximate ? "warn" : "good"}>
              {m.missing.length ? "retrain required" : m.approximate ? "approximate (scaled)" : "matched"}
            </Badge>
            {st.data?.retrain_mode !== "off" && (
              <Button disabled={retrain.isPending || j?.state === "running"} onClick={() => retrain.mutate()}>Retrain for this plant</Button>
            )}
          </div>
          <p className="mt-2 text-sm">Scale factors: {Object.entries(m.factors).map(([k, v]) => `${k} × ${v.toFixed(2)}`).join(" · ") || "—"} · {m.distance_km} km from the reference site</p>
          {m.notes.length > 0 && <ul className="mt-1 list-disc pl-5 text-sm text-muted">{m.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          {j && (
            <p className="mt-2 text-sm" aria-live="polite">
              {j.state === "dispatched"
                ? <>Running on GitHub Actions — <a className="underline" href={j.url} target="_blank" rel="noreferrer">follow progress</a>. The API redeploys itself when done.</>
                : <>{j.step} {j.progress}% {j.error}</>}
            </p>
          )}
          {retrain.error && <p className="mt-2 text-sm text-bad">{(retrain.error as Error).message}</p>}
        </Card>
      )}
      <Card>
        <CardTitle>Deviation rules in use</CardTitle>
        <QueryState isLoading={prof.isLoading} error={prof.error} refetch={prof.refetch} height="h-24">
          {p && (
            <div className="space-y-1 text-sm">
              <div className="flex flex-wrap items-center gap-2"><b>{p.name}</b><Badge tone={p.status === "verified" ? "good" : "warn"}>{p.status.replaceAll("_", " ")}</Badge></div>
              <p className="text-muted">{prof.data?.reason}</p>
              <p>Tolerance solar ±{p.tolerance_pct.solar}% · wind ±{p.tolerance_pct.wind}% · hybrid ±{p.tolerance_pct.hybrid}% · revisions effective from block {p.revisions.effective_from_block}</p>
              <p className="text-muted">{p.notes}</p>
              <ul className="list-disc pl-5 text-xs text-muted">{p.sources.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
        </QueryState>
      </Card>
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="mr-auto mb-0">WhatsApp</CardTitle>
          {ns.data && <Badge tone={ns.data.configured ? "good" : "bad"}>{ns.data.provider}{ns.data.sandbox ? " sandbox" : ""}{ns.data.configured ? "" : " — not configured"}</Badge>}
          <Button disabled={test.isPending} onClick={() => test.mutate(undefined)}>Send test message</Button>
        </div>
        {ns.data?.sandbox && <p className="mt-2 text-xs text-muted">Twilio sandbox: each phone must first send the “join &lt;code&gt;” message to +1 415 523 8886.</p>}
        {test.data && <ul className="mt-2 text-sm">{test.data.map((r) => <li key={r.to} className={r.ok ? "text-good" : "text-bad"}>{r.to}: {r.ok ? "sent" : r.detail}</li>)}</ul>}
        {test.error && <p className="mt-2 text-sm text-bad">{(test.error as Error).message}</p>}
        <QueryState isLoading={contacts.isLoading} error={contacts.error} refetch={contacts.refetch} empty={!contacts.data?.length} height="h-16">
          <table className="mt-3 w-full text-sm"><thead className="text-left text-muted"><tr><th>Name</th><th>Role</th><th>Number</th><th>Opted in</th><th>Alerts from</th></tr></thead>
            <tbody>{contacts.data?.map((c) => <tr key={c.whatsapp}><td>{c.name}</td><td>{c.role}</td><td className="tabular-nums">{c.whatsapp}</td><td>{c.opt_in ? "yes" : "no"}</td><td>{c.min_severity}</td></tr>)}</tbody></table>
        </QueryState>
      </Card>
    </div>
  );
}
````

---

### 14.7 App shell  ·  Depends on: 14.5

#### T14.7.1 — `frontend/src/components/shell/AppShell.tsx`  ✅ Tested
First open: while `/setup/status` says `configured: false`, every page redirects to `/setup`. The sidebar shows the
plant name and type; the header shows "Approximate forecast — retrain recommended" (links to Settings) when the
mapping has notes.
**FILE: `frontend/src/components/shell/AppShell.tsx`** — ✅ Tested

````tsx
"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useHealth, useLiveUpdates } from "@/hooks/api";
import { usePlant } from "@/hooks/plant";
import { useSetupStatus } from "@/hooks/workflow";
import { getApiBaseConfigError, RAW_API_BASE } from "@/lib/api/client";
import type { AlertOut } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { toIST } from "@/lib/format";
import { Badge, Spinner } from "../ui/primitives";
import { NAV } from "./nav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const health = useHealth();
  const [toast, setToast] = useState<AlertOut | null>(null);
  const onAlert = useCallback((a: AlertOut) => { if (a.severity !== "info") setToast(a); }, []);
  useLiveUpdates(onAlert);
  const mode = health.data?.mode?.toUpperCase();
  const plant = usePlant();
  const setup = useSetupStatus();
  const router = useRouter();
  useEffect(() => {   // first open (Phase 16): send the user to the setup wizard until a plant is saved
    if (setup.data && !setup.data.configured && path !== "/setup") router.replace("/setup");
  }, [setup.data, path, router]);

  // Fail loudly if NEXT_PUBLIC_API_BASE is missing or misconfigured in production builds
  const configError = getApiBaseConfigError();
  if (configError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg p-6 text-text">
        <div className="w-full max-w-lg space-y-4 rounded-2xl border border-bad/50 bg-panel p-6 shadow-xl">
          <div className="flex items-center gap-3 text-lg font-semibold text-bad">
            <span className="text-2xl">⚠️</span>
            Configuration Error: NEXT_PUBLIC_API_BASE
          </div>
          <p className="text-sm text-text/80">{configError}</p>
          <div className="space-y-2 rounded-lg bg-border/40 p-3 text-xs text-muted">
            <p className="font-semibold text-text">How to resolve on Vercel:</p>
            <ol className="list-decimal space-y-1 pl-4">
              <li>Open your project on Vercel → <strong>Settings</strong> → <strong>Environment Variables</strong>.</li>
              <li>Add variable <code className="font-mono text-text">NEXT_PUBLIC_API_BASE</code> with your Render service URL (e.g. <code className="font-mono text-text">https://terra-api.onrender.com</code>).</li>
              <li>Trigger a redeploy (Next.js statically bakes this variable into client bundles during build).</li>
            </ol>
            {RAW_API_BASE && (
              <p className="mt-2 text-muted">
                Current build value: <code className="font-mono text-text">{RAW_API_BASE}</code>
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Waking up indicator in header
  const isWakingUp = health.failureCount > 0 && !health.data;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-border bg-panel md:w-56 md:border-r md:border-b-0">
        <div className="px-4 py-4">
          <div className="text-lg font-bold tracking-tight">Vidyut</div>
          <div className="text-xs text-muted">{plant.ready ? `${plant.name} · ${plant.totalLabel}` : "Loading plant…"}</div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href}
              aria-current={path === n.href ? "page" : undefined}
              className={cn("whitespace-nowrap rounded-lg px-3 py-2 text-sm", path === n.href ? "bg-text text-bg" : "text-muted hover:bg-border/60 hover:text-text")}>
              {n.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3 md:px-6">
          <div className="text-sm text-muted">
            {isWakingUp ? (
              <div className="flex items-center gap-2 font-medium text-amber-500" role="status" aria-live="polite">
                <Spinner className="h-4 w-4" />
                <span>The API is waking up (free hosting sleeps when idle). Retrying automatically… attempt {health.failureCount}</span>
              </div>
            ) : health.data?.latest_issue_time_utc ? (
              <>Forecast issued {toIST(health.data.latest_issue_time_utc)}</>
            ) : (
              "Waiting for first forecast…"
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {health.data?.mode === "live" && health.data.latest_issue_time_utc &&
              // eslint-disable-next-line react-hooks/purity
              Date.now() - new Date(health.data.latest_issue_time_utc).getTime() > 3 * 3600_000 && (
                <Badge tone="warn">Data stale since {toIST(health.data.latest_issue_time_utc)}</Badge>
            )}
            {plant.approximate && (
              <Link href="/settings" title={plant.notes.join(" ")}><Badge tone="warn">Approximate forecast — retrain recommended</Badge></Link>
            )}
            {mode && <Badge tone={mode === "LIVE" ? "good" : "hybrid"} aria-label={`mode ${mode}`}>● {mode}</Badge>}
          </div>
        </header>
        <main className="flex-1 px-4 py-5 md:px-6">{children}</main>
        <footer className="border-t border-border px-4 py-3 text-xs text-muted md:px-6">
          Weather data by <a className="underline" href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a> (CC BY 4.0) ·
          Plant: Vidyut virtual digital twin at a real location, calibrated on real data · Times in IST
        </footer>
      </div>
      {toast && (
        <div role="status" className="fixed right-4 bottom-4 max-w-sm rounded-xl border border-border bg-panel p-4 shadow-lg">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Badge tone={toast.severity === "critical" ? "bad" : "warn"}>{toast.type.replaceAll("_", " ")}</Badge>
              <p className="mt-2 text-sm">{toast.message}</p>
              <p className="mt-1 text-xs text-muted">{toIST(toast.start_utc)} → {toIST(toast.end_utc)}</p>
            </div>
            <button aria-label="Dismiss" className="text-muted" onClick={() => setToast(null)}>✕</button>
          </div>
        </div>
      )}
    </div>
  );
}
````

---

### 14.8 Frontend checks  ·  Depends on: 14.1–14.7

#### T14.8.1 — Static checks  📝
```bash
make types                                   # after any backend schema change
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```
Build output lists 15 routes including `/revisions`, `/reports`, `/settings`, `/setup`.

#### T14.8.2 — Browser walk-through (fresh database)  📝
API with `VIDYUT_DB_URL=sqlite:///./walk.db VIDYUT_JOB_TOKEN=t VIDYUT_REPLAY_AUTOACCEPT_DAYAHEAD=true`, then
`npm run dev`:
1. Open `/` → you land on `/setup`. Choose **Solar only**, 20 MW AC / 25 MWp, contracted supply 12 MW, add a contact
   with opt-in, Save → progress bar → Control Room titled "Solar forecast …", sidebar "… · Solar".
2. Run 9 ticks (`curl -X POST -H "X-Job-Token: t" localhost:8000/jobs/tick`) — 6 virtual hours each, so the virtual clock passes the end of 11 Apr (IST).
3. **Revisions & Log**: "Rev 0 by auto (replay)", revision counter `0 / 16`, event log with refresh and WhatsApp rows.
4. **Deviation Shield**: only "Solar" rows and one "Download solar CSV"; move "Penalty harshness" to 2× → expected ₹
   rises; open the block table and click a midday block → the Charge Explanation fills in.
5. **Daily Report**: a finished day is selected; Download PDF opens a 1–2 page PDF.
6. **Settings**: "matched" (or "approximate" if you changed tilt/location); "Send test message" → sent (console).
7. Browser console: no errors.

---

## PHASE 15 — WhatsApp alerts for the operator (Day 4)

Goal: warnings, critical alerts and revision requests reach the operator's phone on WhatsApp, and the operator can
answer a revision request from the phone. All code exists since Phase 13 (`services/notify.py`,
`api/routes/notify.py`); this phase is accounts, configuration, templates and testing.

### How WhatsApp messaging works (read once)

Nobody can send WhatsApp messages from a normal phone number by API. A business sends through the **WhatsApp
Business Platform**, either directly (Meta's **Cloud API**) or through a provider such as **Twilio**. Three rules
shape the design:

1. **Opt-in.** You may only message people who agreed to receive messages from you. The wizard's contact step has
   an explicit "agreed to receive Vidyut messages" checkbox; only opted-in contacts are messaged.
2. **24-hour customer-service window.** After a person messages your number, you may send them free-form text for
   24 hours. Outside that window, a business-initiated message must be a **pre-approved template** (a fixed text
   with numbered variables, category "utility" for alerts).
3. **Webhooks.** Replies arrive as HTTP POSTs from the provider to your public API (`/webhooks/twilio` or
   `/webhooks/meta`). Vidyut checks the signature, finds the contact by number, and treats `YES <code>` /
   `NO <code>` as a decision on the pending recommendation whose id ends with `<code>`.

```
Vidyut API ──POST (REST)──► Twilio / Meta ──► operator's WhatsApp
     ▲                                              │ "YES 3f9a1c"
     └────── POST /webhooks/<provider> ◄────────────┘   → decide() → Rev n → reply "ACCEPTED …"
```

| | **Twilio Sandbox** (use for the hackathon) | **Meta Cloud API** (use for a real plant) |
|---|---|---|
| Setup time | 10 minutes, free trial | 1–3 hours (Meta business account, app, phone number); template approval minutes–hours |
| Who can receive | only phones that sent the sandbox "join <code>" message | anyone who opted in |
| Message type | free-form text inside the 24 h window (re-join/send "hi" to reopen) | templates `vidyut_alert`, `vidyut_revision`; free text only inside 24 h |
| Cost | free on trial | per template message (India utility ≈ ₹0.12 at the time of writing — check Meta's pricing page); replies within the window are free |
| Vidyut setting | `VIDYUT_NOTIFY_PROVIDER=twilio` | `VIDYUT_NOTIFY_PROVIDER=meta` |

Messages Vidyut sends (from `notify.py`):
```
⚠️ Vidyut WARNING — Low Generation
Solar likely below 2.1 MW (78% chance)
11 Apr 13:30–16:30 IST
https://<your-app>/alerts

📝 Vidyut revision recommended (REV-2026-04-11-02-3f9a1c)
revise blocks 44–96: expected deviation charges fall from ₹2,140 to ₹610
Expected saving ₹1,530. From block 44.
Reply YES 3f9a1c to accept or NO 3f9a1c to reject, or open https://<your-app>/revisions
```
Policy built in: quiet hours 22:00–06:00 IST for non-critical messages (`notifications.quiet_hours_ist`), each
alert / recommendation sent once, minimum severity per contact, and the master switch `notifications.enabled`.

---

### 15.1 Twilio WhatsApp Sandbox (hackathon)  ·  Owner: Dev A  ·  Depends on: Phase 13

#### T15.1.1 — Create the account and open the sandbox  📝
1. Sign up at twilio.com (trial is enough). Console → **Messaging → Try it out → Send a WhatsApp message**.
2. Note the sandbox number (`+1 415 523 8886`) and your join phrase (`join <two-words>`).
3. Console → Account → API keys & tokens: copy **Account SID** and **Auth Token**.

#### T15.1.2 — Join from every phone that should receive messages  📝
From each phone's WhatsApp, send `join <two-words>` to +1 415 523 8886. Twilio replies "You are all set". Add the
same numbers in the setup wizard (step 4) with the opt-in box ticked.

#### T15.1.3 — Make the API reachable for replies  📝
- Deployed: the Render URL is public — use it.
- Local: run a tunnel, e.g. `cloudflared tunnel --url http://localhost:8000` (or `ngrok http 8000`), and use the
  printed `https://…` URL.
Set `VIDYUT_PUBLIC_API_URL` to exactly that base URL (no trailing slash): Twilio signs the full webhook URL and
Vidyut recomputes the signature from this value.

#### T15.1.4 — Configure Vidyut  📝
Render → Environment (or `backend/.env` locally):
```bash
VIDYUT_NOTIFY_PROVIDER=twilio
VIDYUT_TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
VIDYUT_TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
VIDYUT_TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
VIDYUT_PUBLIC_API_URL=https://<your-api>.onrender.com
VIDYUT_PUBLIC_APP_URL=https://<your-app>.vercel.app
```

#### T15.1.5 — Point the sandbox at the webhook  📝
Twilio console → Messaging → Try it out → WhatsApp sandbox settings → **When a message comes in**:
`https://<your-api>.onrender.com/webhooks/twilio`, method **POST** → Save.

#### T15.1.6 — Test end to end  🧩 Spec (needs your Twilio account)
1. Vidyut → Settings → **Send test message** → the phone receives "✅ Vidyut test message …". The Settings page
   shows `twilio sandbox` in green.
2. Force a recommendation (Phase 13 demo tip), run a tick → the phone receives the revision message.
3. Reply `NO <code>` → WhatsApp answers "Vidyut: REV-… REJECTED"; the Revisions page shows it rejected by
   "Asha (WhatsApp)". Run another tick → new recommendation → reply `YES <code>` → Rev n appears.
4. Reply `hello` → "Vidyut: reply YES <code> or NO <code> …". A number that is not a contact gets no answer.
If step 3 gets no answer: check Render logs for `403 bad signature` (wrong `VIDYUT_PUBLIC_API_URL`) or a cold start
longer than Twilio's 15 s timeout (keep the API warm with the existing UptimeRobot ping on `/health`).

**Demo-day rule:** the sandbox window is 24 h. On the morning of the demo, send any message (e.g. "hi") from each
demo phone to the sandbox number; re-send the `join` phrase if Twilio says you left.

---

### 15.2 Meta WhatsApp Cloud API (production path, optional)  ·  Depends on: 15.1 working

#### T15.2.1 — App and number  📝
developers.facebook.com → My Apps → Create app (type **Business**) → add product **WhatsApp**. The API Setup page
gives a test phone number, its **Phone number ID**, and a temporary token; add up to 5 recipient numbers for
testing. For production: verify the business, add your own number, and create a **System user** token with
`whatsapp_business_messaging` permission (temporary tokens expire in 24 h). App settings → Basic → **App secret**.

#### T15.2.2 — Create the two templates  📝
WhatsApp Manager → Message templates → Create → category **Utility**, language **English (en)**. Variables are
`{{1}}`, `{{2}}`, `{{3}}` — the order must match what `notify.py` sends:

`vidyut_alert` — body:
```
Vidyut plant alert: {{1}}. {{2}}. Time: {{3}}. Open the Vidyut dashboard for details.
```
samples: `WARNING Low Generation` · `Solar likely below 2.1 MW (78% chance)` · `11 Apr 13:30 IST`

`vidyut_revision` — body:
```
Vidyut revision request (code {{1}}): {{2}}. Expected saving {{3}}. To accept, reply YES followed by the code; to reject, reply NO followed by the code.
```
samples: `3f9a1c` · `revise blocks 44-96: expected deviation charges fall from Rs 2,140 to Rs 610` · `Rs 1,530`

Template variables may not contain line breaks — the values Vidyut sends are single-line.

#### T15.2.3 — Configure Vidyut  📝
```bash
VIDYUT_NOTIFY_PROVIDER=meta
VIDYUT_META_TOKEN=<system user token>
VIDYUT_META_PHONE_NUMBER_ID=<phone number id>
VIDYUT_META_APP_SECRET=<app secret>
VIDYUT_META_VERIFY_TOKEN=<any random string you choose>
VIDYUT_META_GRAPH_VERSION=v25.0
```

#### T15.2.4 — Webhook  📝
App → WhatsApp → Configuration → Webhook: Callback URL `https://<your-api>/webhooks/meta`, Verify token = the same
random string → **Verify and save** (Meta calls `GET /webhooks/meta?hub.challenge=…`; Vidyut echoes it). Then
subscribe to the **messages** field.

#### T15.2.5 — Test  🧩 Spec (needs a Meta app)
Same steps as T15.1.6. Replies inside the 24 h window are answered with free text (`send_text_meta`).

---

### 15.3 Safety and compliance checklist  ·  Depends on: 15.1

#### T15.3.1 — Go through the checklist  📝
- [ ] Only opted-in contacts receive messages (`Contact.opt_in`); keep a note of *how* each person agreed.
- [ ] Opting out: untick the contact in the setup wizard (step 4) and save. (Twilio and Meta also block senders
      that users block or report — keep message volume low and useful.)
- [ ] Secrets only in Render/`.env`, never in git; `webhook_verify_signatures` stays `true` in production.
- [ ] A WhatsApp `YES` is a decision by a known operator: the event log stores who decided and via which channel.
- [ ] Messages say "recommended"; the schedule still goes to the SLDC through the QCA.

---

## PHASE 16 — Production: artifacts, hourly refresh, environment, retrain (Day 5)

Goal: the deployed Vidyut (Render free + Neon + Vercel) runs the whole workflow: fresh runs every hour, state in
Neon, new artifacts delivered by a lock file, optional one-click retrain on GitHub Actions.

Memory budget on Render free (512 MB), measured on the reference: one forecast run peaks at ~315 MB, a full
`vidyut evaluate` at ~645 MB. Therefore the API never runs `evaluate_all`: rule changes use the light
`retune_dsm` (T13.3.6/T16.0.1) and full retraining runs on GitHub Actions (16.5) or a laptop — never on Render.
Keep `VIDYUT_RETRAIN_MODE=off` or `github` there.

---

### 16.0 Light re-tune for rule changes  ·  Owner: Dev A  ·  Depends on: 13.3

#### T16.0.1 — `evaluate_dsm` + `retune_dsm` in `ml/vidyut/pipelines/evaluate.py`  ✅ Tested
The DSM block of `evaluate_all` moves into `evaluate_dsm(preds, cfg, rho)` (same logic); the new
`retune_dsm(cfg)` re-uses saved backtests and the saved copula, re-tunes the schedule level for the operator's
current rule profile and PPA rate, updates `results.json["dsm"]` and saves a new engines version. The final
`evaluate.py` (T12.5.5) already contains both functions — if you implemented 12.5 from an older copy, replace the
file with the T12.5.5 version now. In `backend/app/services/setup.py::start_refresh` the re-tune step calls
`retune_dsm(reference_config())` (already so in T13.3.6).
Check: change the state to Gujarat in the wizard → event log shows the setup event, `/dsm/profiles` →
`gujarat_gerc_2019`, `/dsm/summary` → `profile.id == "gujarat_gerc_2019"` and new `chosen_level`.

---

### 16.1 New artifact bundle with replay data  ·  Depends on: Phases 10–13

Why: the deployed API now needs (a) migrated pickles, (b) a run that has `blocks.parquet`, (c) the replay history
`dataset.parquet` (ticks and daily reports read it), (d) the reference snapshot. And Render must re-download
artifacts whenever they change — a Docker layer keyed on an `ARG` default is cached; a copied lock file is not.

#### T16.1.1 — `scripts/make_deploy_bundle.py`  ✅ Tested
Adds `replay/dataset.parquet` and `models/reference_config.yaml` to the zip (zip ≈ 23 MB).
**FILE: `scripts/make_deploy_bundle.py`** — ✅ Tested

````python
#!/usr/bin/env python3
"""Create a deployment bundle of model and forecast artifacts needed at runtime.

Outputs:
  dist/vidyut-artifacts-<UTC timestamp>.zip
  dist/vidyut-artifacts-<UTC timestamp>.zip.sha256

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
        ("solar", "bundle"),
        ("wind", "bundle"),
        ("hybrid", "engines"),
    ]
    for source, subkind in model_targets:
        model_latest = artifacts_dir / "models" / source / subkind / "LATEST"
        if not model_latest.is_file():
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

    # 5. Replay history (Phase 14): the backend replays the test period and builds daily reports from it.
    #    Stored under replay/ and moved to data/processed/ by the Dockerfile.
    dataset = Path(os.environ.get("VIDYUT_DATA_DIR", artifacts_dir.parent / "data")) / "processed" / "dataset.parquet"
    if dataset.is_file():
        files_to_bundle.append((dataset, "replay/dataset.parquet"))
    else:
        print(f"WARNING: {dataset} not found - replay ticks and daily reports will not work in the deployment")

    # 6. Reference-plant snapshot written by `vidyut train` (Phase 11), if present
    ref = artifacts_dir / "models" / "reference_config.yaml"
    if ref.is_file():
        files_to_bundle.append((ref, "models/reference_config.yaml"))

    # Validate against forbidden tokens
    for file_path, arcname in files_to_bundle:
        check_forbidden(file_path)
        check_forbidden(Path(arcname))

    return files_to_bundle


def create_bundle(artifacts_dir: Path, dist_dir: Path, custom_zip_name: str | None = None) -> tuple[Path, Path, str]:
    files = collect_runtime_files(artifacts_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_name = custom_zip_name or f"vidyut-artifacts-{timestamp}.zip"
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
    parser = argparse.ArgumentParser(description="Create deployment bundle for Vidyut runtime artifacts.")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Path to artifacts directory (defaults to VIDYUT_ARTIFACTS_DIR env var or ./artifacts)",
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
        env_val = os.environ.get("VIDYUT_ARTIFACTS_DIR")
        artifacts_dir = Path(env_val) if env_val else Path("artifacts")

    try:
        create_bundle(artifacts_dir, args.dist_dir, args.name)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
````

#### T16.1.2 — `deploy/artifacts.lock`  ✅ Tested
**FILE: `deploy/artifacts.lock`** — ✅ Tested

````bash
# Runtime artifact bundle used by backend/Dockerfile (sourced by /bin/sh: KEY="value", no spaces around =).
# Update after `make bundle` + publishing a release, or let .github/workflows/retrain.yml rewrite it.
ARTIFACT_URL="https://github.com/OVERxPOWERED/AGNITIA-TERRA06/releases/download/artifacts-20261009/terra-artifacts-20261009T024331Z.zip"
ARTIFACT_SHA256="265ce1e12dc8a6f1284aab958f19e4c049ec2cb30a9503a010b27e419713ec50"
````

#### T16.1.3 — `backend/Dockerfile`  ✅ Tested (download/unpack step run as a shell script; no Docker daemon in the planning sandbox)
**FILE: `backend/Dockerfile`** — ✅ Tested

````dockerfile
# Build from the repo root:  docker build -f backend/Dockerfile -t vidyut-api .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VIDYUT_REPO_ROOT=/app

# System dependencies: libgomp1 for LightGBM, curl/unzip/ca-certificates for release asset fetch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/vidyut ml/vidyut
RUN pip install --no-cache-dir -e ./ml

COPY backend backend
RUN pip install --no-cache-dir -e ./backend

COPY config config
COPY docs docs

# Artifact delivery (Phase 18): deploy/artifacts.lock names the release asset + checksum. Changing the lock
# file (by hand after `make bundle`, or automatically by .github/workflows/retrain.yml) changes this layer,
# so Render re-downloads the artifacts on the next deploy instead of reusing a cached layer.
COPY deploy/artifacts.lock deploy/artifacts.lock
RUN set -e; . ./deploy/artifacts.lock; \
    echo "Downloading runtime artifacts from ${ARTIFACT_URL}..."; \
    curl -fL --retry 5 -o /tmp/artifacts.zip "$ARTIFACT_URL"; \
    echo "${ARTIFACT_SHA256}  /tmp/artifacts.zip" | sha256sum -c -; \
    mkdir -p /app/artifacts /app/data/processed; \
    unzip -q /tmp/artifacts.zip -d /app/artifacts; \
    rm -f /tmp/artifacts.zip; \
    if [ -f /app/artifacts/replay/dataset.parquet ]; then mv /app/artifacts/replay/dataset.parquet /app/data/processed/; fi; \
    echo "Artifacts installed into /app/artifacts."

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
````

#### T16.1.4 — `.dockerignore`: never ship a local plant overlay  ✅ Tested
Append:
```
# Operator plant setup lives in the database in production (Phase 16)
config/plant.yaml
```

#### T16.1.5 — Build, publish, point the lock at it  📝
```bash
rm -f config/plant.yaml                    # bundle the REFERENCE plant
vidyut migrate-artifacts
vidyut forecast --mode replay              # run with blocks.parquet
python scripts/make_deploy_bundle.py       # dist/vidyut-artifacts-<ts>.zip (+ .sha256)
TAG=artifacts-$(date -u +%Y%m%d)
gh release create $TAG dist/vidyut-artifacts-*.zip --title $TAG --notes "Vidyut artifacts (Phase 16)"
```
Edit `deploy/artifacts.lock`: `ARTIFACT_URL="https://github.com/OVERxPOWERED/AGNITIA-TERRA06/releases/download/<TAG>/<zip name>"`
and `ARTIFACT_SHA256="<first word of the .sha256 file>"`. Commit + push → Render rebuilds.
Check (Render logs): `a.zip: OK` / "Artifacts installed"; then `curl <api>/health` → ok and
`curl <api>/dsm/simulate -X POST -H 'Content-Type: application/json' -d '{}'` → 200.

---

### 16.2 Render environment  ·  Depends on: 16.1

#### T16.2.1 — `render.yaml`  ✅ Tested (YAML validated)
**FILE: `render.yaml`** — ✅ Tested

````yaml
services:
  - type: web
    name: terra-api
    runtime: docker
    plan: free
    region: singapore
    dockerfilePath: backend/Dockerfile
    dockerContext: .
    healthCheckPath: /health
    envVars:
      - key: VIDYUT_MODE
        value: replay
      - key: VIDYUT_SCHEDULER_ENABLED
        value: "false"
      - key: VIDYUT_CORS_ORIGINS
        sync: false
      - key: VIDYUT_DB_URL
        sync: false
      # Phase 14-17 (set the secret values in the Render dashboard; sync: false = not stored in git)
      - key: VIDYUT_JOB_TOKEN              # same value as the GitHub secret used by .github/workflows/tick.yml
        sync: false
      - key: VIDYUT_REPLAY_AUTOACCEPT_DAYAHEAD
        value: "false"
      - key: VIDYUT_RETRAIN_MODE           # local | github | off  (free tier: github or off)
        value: "off"
      - key: VIDYUT_GITHUB_TOKEN           # only for retrain_mode=github: fine-grained PAT, Actions read/write
        sync: false
      - key: VIDYUT_PUBLIC_APP_URL         # e.g. https://vidyut.vercel.app (links in WhatsApp messages)
        sync: false
      - key: VIDYUT_PUBLIC_API_URL         # this service's URL (Twilio signs the webhook URL)
        sync: false
      - key: VIDYUT_NOTIFY_PROVIDER        # console | twilio | meta
        value: console
      - key: VIDYUT_TWILIO_ACCOUNT_SID
        sync: false
      - key: VIDYUT_TWILIO_AUTH_TOKEN
        sync: false
      - key: VIDYUT_META_TOKEN
        sync: false
      - key: VIDYUT_META_PHONE_NUMBER_ID
        sync: false
      - key: VIDYUT_META_APP_SECRET
        sync: false
      - key: VIDYUT_META_VERIFY_TOKEN
        sync: false
````

#### T16.2.2 — Set the values in the Render dashboard  📝
| Variable | Value |
|---|---|
| `VIDYUT_JOB_TOKEN` | a long random string (`python -c "import secrets;print(secrets.token_urlsafe(32))"`) |
| `VIDYUT_PUBLIC_APP_URL` / `VIDYUT_PUBLIC_API_URL` | your Vercel URL / your Render URL (no trailing slash) |
| `VIDYUT_RETRAIN_MODE` | `off` (or `github` after 16.5) |
| `VIDYUT_REPLAY_AUTOACCEPT_DAYAHEAD` | `true` only for an unattended demo; `false` to accept by hand |
| WhatsApp variables | from Phase 15 |
Neon needs nothing: new tables are created at start-up. Check: `/setup/status` returns JSON; after the wizard,
restart the service (Render → Manual deploy) and `/site` still shows your plant (restored from `AppState`).

---

### 16.3 Hourly refresh from GitHub Actions  ·  Depends on: 16.2

#### T16.3.1 — `.github/workflows/tick.yml`  ✅ Tested (YAML validated)
**FILE: `.github/workflows/tick.yml`** — ✅ Tested

````yaml
# Hourly forecast refresh for the deployed API (Phase 14).
# Render free instances sleep after ~15 idle minutes, so an in-process scheduler never fires; this job
# wakes the API and asks it to produce one run (day-ahead proposal, revision check, WhatsApp alerts).
# Secrets (repo Settings -> Secrets and variables -> Actions):
#   VIDYUT_API_URL    e.g. https://terra-api.onrender.com   (no trailing slash)
#   VIDYUT_JOB_TOKEN  same value as the VIDYUT_JOB_TOKEN env var on Render
name: tick
on:
  schedule:
    - cron: "7 * * * *"          # every hour at :07 (GitHub may delay scheduled jobs by a few minutes)
  workflow_dispatch: {}
concurrency:
  group: tick
  cancel-in-progress: false
jobs:
  tick:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Wake the API (cold start can take ~60 s)
        run: |
          for i in $(seq 1 12); do
            if curl -fsS "${{ secrets.VIDYUT_API_URL }}/health" > /dev/null; then exit 0; fi
            sleep 10
          done
          echo "API did not wake up" && exit 1
      - name: Produce one forecast run
        run: |
          curl -fsS -X POST -H "X-Job-Token: ${{ secrets.VIDYUT_JOB_TOKEN }}" \
            --max-time 300 "${{ secrets.VIDYUT_API_URL }}/jobs/tick"
````

#### T16.3.2 — Secrets and first run  📝
GitHub → repo → Settings → Secrets and variables → Actions → New repository secret: `VIDYUT_API_URL`,
`VIDYUT_JOB_TOKEN` (same as Render). Actions tab → **tick** → Run workflow.
Check: job green; `/events?kind=refresh` has a new row; Revisions page shows the new refresh. Each tick advances
the replay clock by `VIDYUT_REPLAY_STEP_HOURS` (6 h), so one real day = 6 virtual days; set it to `1` for a slower
demo. GitHub may delay scheduled runs by 5–15 min — fine.

---

### 16.4 CI  ·  Depends on: 13.5

#### T16.4.1 — Keep CI green  📝
`.github/workflows/ci.yml` needs no structural change (the rename already switched it to `vidyut …`). It now also
runs `tests/test_workflow.py`, which uses the synthetic dataset CI builds; `build-dataset --synthetic` no longer
needs the Mendeley files (T12.5.4). Check: the PR for Phase 13 has a green `python` and `frontend` job.

---

### 16.5 One-click retrain on GitHub Actions (stretch)  ·  Depends on: 16.1

#### T16.5.1 — `.github/workflows/retrain.yml`  🧩 Spec (YAML validated; every step is a command verified locally)
Writes `config/plant.yaml` from the dispatch input, fetches real weather for the plant's location (Open-Meteo is
reachable from GitHub runners), trains, evaluates, bundles, publishes a release and rewrites
`deploy/artifacts.lock`; that push redeploys Render. Expect 20–40 min (weather download dominates).
**FILE: `.github/workflows/retrain.yml`** — 🧩 Spec

````yaml
# Retrain all models for the operator's plant (Phase 16.5, stretch). Dispatched by the API
# (POST /setup/retrain with VIDYUT_RETRAIN_MODE=github) or by hand from the Actions tab.
# Steps: write config/plant.yaml -> fetch real weather for the plant location -> build twin dataset -> frame ->
# train -> evaluate -> forecast -> bundle -> GitHub release -> rewrite deploy/artifacts.lock and push,
# which makes Render rebuild the API with the new artifacts.
# Needs: repo Settings -> Actions -> General -> Workflow permissions = "Read and write".
name: retrain
on:
  workflow_dispatch:
    inputs:
      plant_yaml_b64:
        description: "base64 of config/plant.yaml (empty = retrain the reference plant)"
        required: false
        default: ""
permissions:
  contents: write
concurrency:
  group: retrain
  cancel-in-progress: false
jobs:
  retrain:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -e "ml[dev,tune]" -e "backend[dev]"
      - name: Plant configuration
        if: ${{ inputs.plant_yaml_b64 != '' }}
        run: echo "${{ inputs.plant_yaml_b64 }}" | base64 -d > config/plant.yaml && cat config/plant.yaml
      - name: Pipeline
        env:
          VIDYUT_LOG_LEVEL: WARNING
        run: |
          vidyut fetch-weather
          vidyut build-dataset
          vidyut frame
          vidyut train
          vidyut evaluate
          vidyut forecast --mode replay
      - name: Bundle
        id: bundle
        run: |
          python scripts/make_deploy_bundle.py --dist-dir dist
          ZIP=$(ls dist/*.zip | head -1)
          echo "zip=$ZIP" >> "$GITHUB_OUTPUT"
          echo "sha=$(sha256sum "$ZIP" | cut -d' ' -f1)" >> "$GITHUB_OUTPUT"
          echo "tag=artifacts-$(date -u +%Y%m%dT%H%M%S)" >> "$GITHUB_OUTPUT"
      - name: Release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "${{ steps.bundle.outputs.tag }}" "${{ steps.bundle.outputs.zip }}" --title "${{ steps.bundle.outputs.tag }}" --notes "Retrained artifacts (workflow run ${{ github.run_id }})"
      - name: Point the deployment at the new artifacts
        run: |
          NAME=$(basename "${{ steps.bundle.outputs.zip }}")
          cat > deploy/artifacts.lock <<LOCK
          # Written by .github/workflows/retrain.yml run ${{ github.run_id }}
          ARTIFACT_URL="https://github.com/${{ github.repository }}/releases/download/${{ steps.bundle.outputs.tag }}/$NAME"
          ARTIFACT_SHA256="${{ steps.bundle.outputs.sha }}"
          LOCK
          sed -i 's/^ *//' deploy/artifacts.lock
          git config user.name "vidyut-bot"
          git config user.email "actions@users.noreply.github.com"
          git add deploy/artifacts.lock
          git commit -m "deploy: artifacts ${{ steps.bundle.outputs.tag }}"
          git push
````

#### T16.5.2 — Enable it  📝
1. Repo → Settings → Actions → General → Workflow permissions → **Read and write**.
2. GitHub → Settings → Developer settings → Fine-grained token: repository = this repo, permission **Actions: Read
   and write** → Render `VIDYUT_GITHUB_TOKEN`; set `VIDYUT_RETRAIN_MODE=github`.
3. Settings page → **Retrain for this plant** → "Running on GitHub Actions — follow progress".
Check: the workflow finishes, a new `artifacts-…` release exists, `deploy/artifacts.lock` changed, Render redeploys,
Settings shows "matched". Note: the run trains with `config/plant.yaml` as the new reference, so the badge clears.
Licence note: Open-Meteo's free API is for non-commercial use; a commercial deployment needs their paid plan.

---

## PHASE 17 — Integration, docs and demo (Day 5–6)

Goal: everything works together on the deployed site, the documents describe the new product, and the demo
tells one story: *a plant engineer sets up their plant, Vidyut warns about a costly deviation, the operator
accepts a revision from WhatsApp, and next morning the report shows the rupees saved.*

---

### 17.1 End-to-end checks  ·  Owner: both  ·  Depends on: Phases 10–16

#### T17.1.1 — Local full run  📝
```bash
make lint && make test                      # ML 65 passed, backend 35 passed
cd frontend && npm run build && cd ..
```

#### T17.1.2 — Three plant types on the deployed site  📝
For each of Solar only / Wind only / Solar + wind: run the wizard → wait for the refresh job → Control Room,
Forecast, Deviation Shield, What-if, Revisions, Daily Report show only that plant's series, no console errors.
Finish with the plant you will demo.

#### T17.1.3 — Restart survival  📝
Render → Manual deploy (wipes the disk). After it is live: no redirect to `/setup`, same plant, same contacts,
Revisions shows the same versions and log, the replay clock continues (`/schedule/today` → `now_utc`).

#### T17.1.4 — WhatsApp rehearsal  📝
Phase 15.1.6 steps on the deployed site with both team phones.

---

### 17.2 Documentation  ·  Owner: Dev B  ·  Depends on: 17.1

#### T17.2.1 — Update the narrative docs  📝
- `README.md`: new feature list (§A), screenshots of Revisions & Log, Deviation Shield simulator, Daily Report,
  Setup wizard; "How Vidyut handles solar-only / wind-only / hybrid plants" (decision B1 in 5 lines).
- `DEV.md`: new modules (Phase 13 tree), the API table (§D), workflow diagram (§C), memory budget (Phase 16).
- `docs/deployment.md`: lock-file delivery (16.1), Render variables (16.2), tick cron (16.3), WhatsApp (15).
- `docs/business-case.md`: revision savings and the report as the QCA's bill-check tool.
- `.agent/context/architecture.md`, `api-contract.md`, `india-grid-regulations.md` (rule profiles table from
  Phase 12), `decisions.md` (ADR-017 rename, ADR-018 reference→plant scaling, ADR-019 DB-persisted operator state,
  ADR-020 external tick, ADR-021 light re-tune on free tier).
- `.agent/memory/handoff.md`: current state.

#### T17.2.2 — Judge Q&A additions (EXPLAIN.md or pitch notes)  📝
Prepare one-paragraph answers for: How do you support a solar-only plant without retraining? (B1) · Is the
schedule submitted automatically? (No — QCA/SLDC; Vidyut recommends, operator decides, every decision logged.)
· Where do the penalty numbers come from? (rule profiles; status badge; MP bands unverified, Gujarat verified.)
· Why WhatsApp? (operators are in the field; reply YES/NO works without opening a laptop; opt-in + templates.)
· What does the simulator prove? (penalty-aware P-level beats P50 under each state's rules; harsher rules →
bigger value of good forecasts.) · What happens on free hosting? (cron tick, DB-persisted state, memory budget.)

#### T17.2.3 — Find out who reads the report  📝
Ask one real person (a QCA, a plant engineer, a faculty contact in the power sector) what they check in a daily
deviation report. Adjust the PDF headings in `ml/vidyut/eval/pdf.py` if needed and mention it in the pitch.

---

### 17.3 Demo  ·  Owner: Dev B  ·  Depends on: 17.1

#### T17.3.1 — Demo script (6 minutes)  📝
1. (0:00) Fresh browser on the site → setup wizard. Pick **Solar + wind**, Madhya Pradesh → profile badge
   "MPERC — unverified bands"; switch to Gujarat → "verified". Add your phone. Save → progress → Control Room.
2. (1:30) Control Room: plant total with band, trust ribbon. "Plant type changes are instant — scaled models."
3. (2:15) Deviation Shield: simulator — harshness 2×, tolerance 3 %, P40 vs P50; click a block → charge explained.
4. (3:15) Trigger a tick (Actions → tick → Run) or show the pre-staged recommendation → phone buzzes → reply
   `YES <code>` → Revisions & Log shows Rev 1 "accepted by … (WhatsApp)", highlighted triggers, explanation.
5. (4:30) Daily Report for a finished day → "saved by revisions" → Download PDF.
6. (5:15) Settings: mapping card (approximate → retrain button), WhatsApp test. Close on impact numbers.
Pre-stage: run ticks up to the demo day, keep `revision.shift_trigger_pct: 2.0` for the demo plant, send "hi" to
the Twilio sandbox that morning, warm the API 5 minutes before.

#### T17.3.2 — Fallback  📝
Record a 3-minute screen video of the full flow the day before; keep it on both laptops.

---
