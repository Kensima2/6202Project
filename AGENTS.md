# AGENTS.md — Virtual Mini-Foundry (7-mask)

## Project overview

Educational **semiconductor process co-design simulator** (teaching proxies, NOT a TCAD-accurate flow). Students/AI act as a virtual fab team: lithography defines CD → etch transfers pattern → CVD fills gaps → implant+anneal sets junctions → metallization+CMP builds interconnects → device proxy maps outputs to Vt/Ioff/Ron.

**This is also an AI contest testbed**: agents are evaluated on how well they understand, run, and extend these models. Baseline work must use **parameters already exposed in configs**; code changes beyond that are labeled "extensions".

Two packages, each with its own README:
- `01_lithography/` — Topic 1 lithography (imaging, RET, resist, process window). See `01_lithography/README.md`.
- `02_process_stages/` — the full 7-mask chain (etch / CVD / implant / met-CMP / device). See `02_process_stages/README.md`.
- `configs/` — all JSON configs + `CONFIG_GUIDE.md` (detailed parameter guide, **written in Chinese**).
- `Project Tutorial/` — instructor docs (`.docx`), including Q&A on scope/mask requirements.

## Environment

- Python 3.10+ required; deps: `numpy`, `matplotlib`, `pillow`, `gdstk` (GDS only); `scipy`/`tqdm` optional. See `INSTALL.md`.
- **Use the workspace interpreter**: `c:\6202Project\.venv\Scripts\python.exe` (Python 3.14.7, has numpy/matplotlib/PIL/gdstk).
  The system `python` on this machine has **no numpy** — importing any module fails.
- `01_lithography` code is **numpy-only** (FFT-based imaging, no SciPy dependency) — keep it that way when editing.

## Canonical commands

```bash
# 1. Standalone litho (run from 01_lithography/ so outputs land in 01_lithography/outputs/)
cd 01_lithography
python run_project.py --config config.json                  # 1D line/space default
python run_project.py --config config_2d_contact.json      # 2D contact sweep (slower)

# 2. Quick baseline demo (no config)
cd 01_lithography && python photolithography_baseline.py

# 3. Full 7-mask pipeline (takes minutes, writes outputs/<timestamp>_<runname>/)
cd 02_process_stages
python run_7mask_pipeline.py --flow ../configs/process_flow.json --runname TEAM01

# 4. GDS -> per-layer masks
python gds_router/gds_to_masks.py --gds gds/basic.gds --layer_map configs/layer_map.json \
       --outdir masks --N 1024 --top_cell ""

# 5. Notebook (root): run.ipynb runs all stages individually from repo root
```

There is **no test suite**. Validation = run the pipeline/runner, then check outputs exist and JSON metrics are sane.

## Data flow & output contract

```
gds/basic.gds ──gds_router/gds_to_masks.py──> masks/*.npy + masks/grid_meta.json
                                                    │
              run_7mask_pipeline.py (scheduler, runs from 02_process_stages/)
                    │
  stage1 POLY litho │ copies configs/litho_config_pipeline.json -> 01_lithography/config.json,
                    │ runs run_project.py; copies resist.npy -> stage1_poly_litho/
  stage2 etch       │ stage2_etch.py  -> summary.json, etched_openings.npy
  stage4 implant    │ stage4_implant_thermal_multimask.py -> device_inputs.json, metrics_stage4.json
  stage5 met+CMP    │ stage5_metallization_cmp_multimask.py -> metrics_stage5.json
  stage6 device     │ stage6_device.py -> metrics_stage6.json (Vt_proxy, Ioff_proxy, Ron_proxy)
```

- All stage outputs land in `outputs/<timestamp>_<runname>/<stage>/`; `pipeline_outputs.json` summarizes paths.
- **Stage 3 CVD is NOT called by the pipeline** (`stage3_cvd.py` exists but is only used in the notebook path).
- Notebook track uses the **single-mask variant** scripts (`stage4_thermal_implant.py`, `stage5_metallization_cmp.py`) and a **different, root-level output layout** (`outputs/stageX/`, not `outputs/<timestamp>_.../`). Keep both tracks in mind before "fixing" paths.

## Critical pitfalls

1. **Interpreter** — always use `.venv` (see Environment).
2. **CWD sensitivity**: `run_project.py` resolves outputs/masks relative to CWD (`outputs/stage1_poly_litho`, `masks/klayout_mask.png`). Run it from `01_lithography/` for consistent paths. (The notebook's stage-2 cell reads `01_lithography/outputs/stage1_poly_litho/resist.npy`, so a root-level run of `run_project.py` writes to the *root* `outputs/` — mismatch.)
3. **Pipeline overwrites `01_lithography/config.json`** on every run (copies `configs/litho_config_pipeline.json`). Edit `configs/litho_config_pipeline.json` (not `01_lithography/config.json`) for pipeline-affecting changes.
4. **Config schema mismatch**: `run_project.py` requires `dose_sweep: {start, stop, num}` and `defocus_sweep_nm: {start, stop, num}` plus `dose0`, `sim_pitches`, `dx_nm`. `configs/litho_config_scan.json` uses the OLD `dose_list`/`defocus_list_nm` keys — it does not work with `run_project.py` as-is.
5. **Interface gaps in the multimask pipeline** (stage6 silently falls back to defaults): stage4 multimask writes `xj_nm`/`Neff_proxy`/`activation_proxy` but **not** `peak_cm3`/`sheet_resistance_ohm_per_sq`; stage5 multimask writes `t_post_cmp_nm_proxy` but **not** `copper_mean_um` → stage6 uses defaults (Na=1e18 cm⁻³, Rs=1e3 Ω/sq, cu=0.2 µm). Check JSON keys before assuming a process-to-device coupling actually feeds through.
6. **Mask conventions**: masks are `uint8` 0/1. Litho `resist.npy` is float where **1 = resist remains**; etch `etched_openings.npy` where **1 = open/etched**. Use `common_utils.ensure_binary()` / `mask_ops` helpers rather than ad-hoc thresholds.
7. **CLI arg**: `run_project.py --outdir` (the notebook comment says `--output_dir` — outdated).
8. `configs/layer_map.json` maps V1 to GDS `(99, 0)`; `masks/grid_meta.json` documents bbox/N/top_cell for the current rasterization.

## Where to extend (grading links)

- Rubric: `01_lithography/GRADING_RUBRIC.md` (100 pts: reproducibility 20, baseline 20, imaging/RET 20, resist/process 20, manufacturability metric 20, +10 bonus, +5 spin-coating).
- Report: `REPORT_TEMPLATE.md` (max 6 pages) — required plots must be reproduced by one command.
- Three required extension categories (pick ≥1 each):
  - **A. Imaging/RET**: `illumination.py` (annular/dipole sampling), `psm.py` (phase-shift mask), `opc.py` (bias/morphology), `smo.py` (grid-search source-mask optimization).
  - **B. Resist/process**: contrast curve, separate PEB diffusion on photoacid, LER/yield (extend `photolithography_baseline.py` `develop()` / `simulate_one()`); spin coating coupling via `spin_coating.py` + `resist_coupling` config.
  - **C. Metrics**: `metrics.py` (`window_area`, `nils_1d`, `cd_sensitivity`, EPE/CDU summaries).
- `01_lithography` runner pattern: `run_project.py` sets **module globals** in `photolithography_baseline.py` (e.g. `TARGET_CD_NM`, `PATTERN`, `PSM_ENABLED`) from config — new knobs typically follow this global-variable pattern.

## Conventions

- Physics is intentionally simplified; models are teaching proxies (see module docstrings for "what it models" and "students can extend" notes).
- Config-driven, JSON-based; one-command reproducibility is graded (20 pts).
- Figures saved as PNG (dpi=200) into each stage's output dir; `01_lithography/outputs/` contains demo figures (`demo_1d_*`, `demo_2d_*`, `process_window.png`, `cd_vs_dose/defocus.png`, `spin_*`, `ret_*`).
- Stage JSON metric files have explicit stage-specific names (e.g., `metrics_stage4.json`, `metrics_stage5.json`, `metrics_stage6.json`; stage2 uses `summary.json`); the standalone single-mask variants write plain `metrics.json`.
- Star imports: stage scripts run from their own directory with plain `import common_utils` — keep the 7-mask pipeline's CWD assumptions intact.
