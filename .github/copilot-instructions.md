# Project Guidelines

## Domain

Photolithography simulator for semiconductor manufacturing education. Simulates the optical lithography pipeline: GDS mask → aerial image (scalar diffraction) → resist development → CD extraction → process window analysis. Students extend a working baseline with RET techniques, resist models, and manufacturability metrics.

## Architecture

Focus area: `01_lithography/`. Entry point: `01_lithography/run_project.py`.

| Module | Role |
|--------|------|
| `photolithography_baseline.py` | Core physics: mask building, aerial imaging (partial coherence), resist develop, CD extraction |
| `spin_coating.py` | Thickness simulation (Meyerhofer model + radial non-uniformity) |
| `opc.py` | Optical Proximity Correction (mask bias, morphological ops) |
| `psm.py` | Phase Shift Mask (complex transmission with phase shifts) |
| `smo.py` | Source-Mask Optimization (grid search over illumination + bias) |
| `illumination.py` | Deterministic source sampling (annular, dipole) |
| `mask_import.py` | KLayout PNG → mask `.npy` converter |
| `metrics.py` | Process window area, NILS (1D), CD sensitivity |

**Data flow**: `run_project.py` loads config → loops over dose/defocus pairs → calls `photolithography_baseline.simulate_one()` (which applies OPC/PSM if enabled → computes aerial image → develops resist → extracts CD) → aggregates into process window → saves figures + `metrics.json`.

The `02_process_stages/` pipeline (`run_7mask_pipeline.py`) calls `01_lithography` as its first stage, but for lithography development work focus on `run_project.py` directly.

## Config

**Only config used for lithography**: `configs/lithography_config.json`  
See `configs/CONFIG_GUIDE.md` for full key documentation.

Key sections:
- `target_cd_nm`, `cd_tol_nm` — CD target ± tolerance (defines pass/fail)
- `pattern`, `pitch_nm`, `duty_cycle` — mask geometry (`line_space_1d` or `contact_2d`)
- `wavelength_nm`, `na`, `sigma_in/out`, `n_source_samples` — optical system
- `dose_sweep`, `defocus_sweep_nm` — sweep ranges for process window
- `ret.psm`, `ret.opc` — Resolution Enhancement controls
- `spin_coating`, `resist_coupling` — optional thickness coupling

## Build and Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run lithography simulation (primary workflow)
cd 01_lithography
python run_project.py --config ../configs/lithography_config.json --outdir ../outputs/stage1_poly_litho

# Quick standalone baseline demo
python photolithography_baseline.py

# 2D contact simulation (slower)
python run_project.py --config ../configs/config_2d_contact.json
```

## Outputs

`outputs/` stores simulation results. Existing contents are stale — safe to overwrite or clear.  
Each run produces: demo PNGs, process window plots, CD-vs-dose/defocus curves, and `metrics.json`.

## Conventions

- **Unit suffixes in names**: `_nm` (nanometers), `_Pa_s` (viscosity), `_rad` (radians), `_px` (pixels)
- **No SciPy by design**: morphological ops, Gaussian blur, circle fitting are all hand-rolled via NumPy/FFT for portability. Do not introduce scipy dependencies unless explicitly asked.
- **Global knobs pattern**: `photolithography_baseline.py` has module-level variables (`TARGET_CD_NM`, `WAVELENGTH_NM`, `NA`, etc.) that `run_project.py` overwrites from config at runtime.
- **Student extension points**: marked with `# Students can extend:` comments in code.
- **Type hints**: functions use `def foo(x: float) -> np.ndarray:` style.

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| CD extraction returns 0 | Threshold too high / no resist remaining | Lower `develop_threshold` or increase `peb_blur_nm` |
| Simulation very slow | Large `n_source_samples` (41+) × many sweep points | Reduce to ~12 for iteration, increase for final runs |
| Process window all-red (fail) | CD target unreachable at given parameters | Relax `cd_tol_nm` or adjust `peb_blur_nm` |
| 2D contact CD is None | Too few boundary pixels for circle fit | Increase resolution (`dx_nm`) or `sim_pitches` |
| Memory overflow on 2D | Fine grid + large `sim_pitches` | Use coarser `dx_nm` or fewer pitches |

## Grading (reference)

See `01_lithography/GRADING_RUBRIC.md` for full details: Reproducibility (20), Baseline (20), Imaging/RET extension (20), Resist/process extension (20), Manufacturability metric (20), Bonus (+10/+5).

## Tutorial Docs

`Project Tutorial/` contains `.docx` guides: Code_framework, Environment_Setup, KLayout_Python_ClosedLoop_Guide, Virtual_MiniFoundry_Code_Annotation_Guide.
