# AGENTS.md — Virtual Mini-Foundry (7-mask)

## 1. Directories

- `01_lithography/` — Topic 1 lithography: imaging, RET (PSM/OPC/SMO), resist, process window. Runner: `run_project.py`.
- `02_process_stages/` — 7-mask process chain: etch (`stage2_etch.py`), CVD (`stage3_cvd.py`), implant/anneal (`stage4_*`), metallization+CMP (`stage5_*`), device proxy (`stage6_device.py`). Scheduler: `run_7mask_pipeline.py`.
- `configs/` — JSON configs (`process_flow.json`, `litho_config_pipeline.json`, `layer_map.json`) + `CONFIG_GUIDE.md` (Chinese).
- `gds/`, `gds_router/`, `masks/` — GDS input, GDS→mask converter, generated masks.
- `Project Tutorial/` — instructor `.docx` docs (scope Q&A, env setup, annotation).
- Root: `run.ipynb` (per-stage runs), `REPORT_TEMPLATE.md`, `INSTALL.md`, `GRADING_RUBRIC.md`.

## 2. Goals

- **Achieve equal or better results than the current outputs in `outputs/`** (which contain other teams' runs). Benchmark = stage JSON metrics from those runs (e.g. `window_area_dose_nm`, `Vt_proxy_V`, `Ioff_proxy_A`, `Ron_proxy_ohm`, `interconnect_R_proxy_ohm`, stage4/5 metrics) and required plots.
- Teach semiconductor process co-design with simplified proxies (litho → etch → CVD → implant/anneal → met+CMP → device Vt/Ioff/Ron).
- Contested AI testbed: baseline work uses only parameters already exposed in configs; code changes beyond that are labeled "extensions".
- One-command reproducibility of required plots/metrics (graded 20 pts).

## 3. Rules / Verifications

- **Interpreter**: always `c:\6202Project\.venv\Scripts\python.exe` — system `python` has NO numpy. Verify: `import numpy, matplotlib, PIL, gdstk` succeeds.
- **Run locations**: `run_project.py` from `01_lithography/` (CWD-sensitive); pipeline from `02_process_stages/`; GDS converter from repo root.
- **Configs**: edit `configs/litho_config_pipeline.json` (pipeline overwrites `01_lithography/config.json`); `run_project.py` needs `dose_sweep:{start,stop,num}` + `defocus_sweep_nm:{start,stop,num}` (old `dose_list` keys break).
- **Interface gaps**: stage4/stage5 multimask JSONs lack `peak_cm3`, `sheet_resistance_ohm_per_sq`, `copper_mean_um` → stage6 uses defaults. Check JSON keys before assuming coupling.
- **Mask conventions**: uint8 0/1; `resist.npy` 1=resist remains; `etched_openings.npy` 1=open. Use `common_utils.ensure_binary()`/`mask_ops`.