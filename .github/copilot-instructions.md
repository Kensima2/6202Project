# Project Guidelines

## Scope

This repository is a teaching-oriented Virtual Mini-Foundry flow.
Default execution and verification entrypoint is the notebook `run.ipynb`.
When users ask to run, validate, or tune the project, prefer notebook-equivalent stage commands and output paths.

## Source-of-Truth Workflow

Treat `run.ipynb` as the operational contract for stage order and CLI flags.

Standard order:
1. Stage 1 lithography: `python 01_lithography/run_project.py --config configs/lithography_config.json`
2. Stage 2 etch: `python 02_process_stages/stage2_etch.py --resist outputs/stage1_poly_litho/resist.npy ...`
3. Stage 3 CVD: `python 02_process_stages/stage3_cvd.py --openings outputs/stage2_etch/etched_openings.npy ...`
4. Stage 4 implant/thermal: `python 02_process_stages/stage4_thermal_implant.py ...`
5. Stage 5 metallization/CMP: `python 02_process_stages/stage5_metallization_cmp.py ...`
6. Stage 6 device proxy: `python 02_process_stages/stage6_device.py ...`
7. Full flow option: `python 02_process_stages/run_7mask_pipeline.py --flow configs/process_flow.json --runname <name>`

If notebook code and standalone docs conflict, follow notebook behavior first, then update docs/configs for consistency.

## Python Call Graph

Primary command relationships:

- `run.ipynb` -> `01_lithography/run_project.py`
	- `run_project.py` -> `photolithography_baseline.py`
	- Optional RET path: `opc.py`, `psm.py`, `smo.py`, `illumination.py`, `spin_coating.py`, `metrics.py`

- `run.ipynb` -> `02_process_stages/stage2_etch.py`
- `run.ipynb` -> `02_process_stages/stage3_cvd.py`
- `run.ipynb` -> `02_process_stages/stage4_thermal_implant.py`
- `run.ipynb` -> `02_process_stages/stage5_metallization_cmp.py`
- `run.ipynb` -> `02_process_stages/stage6_device.py`

- `02_process_stages/run_7mask_pipeline.py` orchestrates:
	- `gds_router/gds_to_masks.py`
	- `01_lithography/run_project.py`
	- `stage2_etch.py` -> `stage3_cvd.py` -> `stage4_thermal_implant.py` -> `stage5_metallization_cmp.py` -> `stage6_device.py`

## Config Mapping (Do Not Guess)

Use these exact mappings when changing params:

- `configs/lithography_config.json`
	- Used by `01_lithography/run_project.py` in notebook Stage 1.

- `configs/litho_config_pipeline.json`
	- Used by `run_7mask_pipeline.py` for pipeline Stage 1 lithography.

- `configs/process_flow.json`
	- Used by `run_7mask_pipeline.py` for stage params and mask strategy.
	- Stage param roots:
		- `stage_params.etch`
		- `stage_params.cvd`
		- `stage_params.implant_thermal`
		- `stage_params.met_cmp`
		- `stage_params.device`

- `configs/notebook_tuned_params.json`
	- Notebook-aligned tuned values reference; keep synchronized with Stage 2-6 notebook cells when asked.

- `configs/layer_map.json`
	- Used by `gds_router/gds_to_masks.py` when `gds_input.enabled` is true.

## Output Contract (Critical)

Never change output filenames lightly; downstream stages depend on these names.

- Stage 1 -> `outputs/stage1_poly_litho/resist.npy`, `metrics.json`
- Stage 2 -> `outputs/stage2_etch/etched_openings.npy`, `summary.json`, rate/topology plots
- Stage 3 -> `outputs/stage3_cvd/depth_map_um.npy`, `dielectric_thickness_map_um.npy`, `void_map.npy`, `summary.json`
- Stage 4 -> `outputs/stage4_implant_thermal/metrics.json` + dopant/depth arrays
- Stage 5 -> `outputs/stage5_metallization_cmp/metrics.json` + CMP arrays/plots
- Stage 6 -> `outputs/stage6_device/metrics.json`

Pipeline output:
- `outputs/<timestamp>_<runname>/pipeline_outputs.json`
- `outputs/<timestamp>_<runname>/stage{1..6}_*`

If renaming output directories (for example to `outputs/final_team_run`), update path references in `pipeline_outputs.json` accordingly.

## Editing and Validation Rules

- Prefer parameter edits in notebook cells and configs before changing stage physics code.
- Keep CLI argument names and path conventions stable across notebook and pipeline.
- After Stage 2-6 changes, run a parity check when requested:
	- one run via `run_7mask_pipeline.py`
	- one run stage-by-stage via notebook-equivalent commands
	- compare key JSON files and key `.npy` hashes
- Treat mismatches as regressions until explained or fixed.

## Project Conventions

- Unit suffixes are required in variable names: `_nm`, `_um`, `_A`, `_cm2`, `_keV`, `_mTorr`.
- NumPy + matplotlib only by default; do not add SciPy unless explicitly requested.
- Preserve teaching readability over micro-optimizations.
- Avoid hard-coded absolute paths in source code.

## Pitfalls

- Missing Stage 2 input for Stage 3: ensure `outputs/stage2_etch/etched_openings.npy` exists.
- Inconsistent notebook vs config values: sync `run.ipynb` Stage cells with `process_flow.json`/`notebook_tuned_params.json` when tuning is finalized.
- Stale outputs causing confusion: clear stage output directories before rerun when comparing experiments.

## Reference Docs (Link, Do Not Duplicate)

- Root overview: `README.md`
- Lithography package details: `01_lithography/README.md`
- Process chain details: `02_process_stages/README.md`
- Tutorial package:
	- `Project Tutorial/Code_framework.docx`
	- `Project Tutorial/Environment_Setup.docx`
	- `Project Tutorial/KLayout_Python_ClosedLoop_Guide.docx`
	- `Project Tutorial/Virtual_MiniFoundry_Code_Annotation_Guide.docx`

## Suggested Custom Skill

If asked to automate recurring validation, create and use a skill that:
- reruns pipeline and one-by-one chains,
- checks parity for key outputs,
- standardizes output folder finalization (`final_team_run`),
- updates `pipeline_outputs.json` paths after renaming.
