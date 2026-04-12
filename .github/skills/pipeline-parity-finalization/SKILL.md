---
name: pipeline-parity-finalization
description: "Use when user asks to rerun run_7mask_pipeline, rerun stage-by-stage flow, compare outputs, keep only final_team_run outputs, and push final branch."
---

# Pipeline Parity Finalization

## Purpose

Standardize the workflow for validating parity between:
- `02_process_stages/run_7mask_pipeline.py`
- notebook-equivalent stage-by-stage execution (Stage 1 to Stage 6)

Then finalize outputs as `outputs/final_team_run`.

## Preconditions

- Run from repo root.
- Ensure configs are synchronized with `run.ipynb` stage parameters.
- Do not change stage physics unless user asks.

## Workflow

1. Run full pipeline:
   - `python 02_process_stages/run_7mask_pipeline.py --flow configs/process_flow.json --runname final_team_run`
   - Capture latest timestamped folder under `outputs/*_final_team_run`.

2. Run one-by-one chain with notebook-equivalent CLI flags:
   - Stage1: `01_lithography/run_project.py`
   - Stage2: `stage2_etch.py`
   - Stage3: `stage3_cvd.py`
   - Stage4: `stage4_thermal_implant.py`
   - Stage5: `stage5_metallization_cmp.py`
   - Stage6: `stage6_device.py`
   - Use isolated outdir: `outputs/onebyone_final_team_run`.

3. Compare outputs:
   - JSON exact equality for key summaries/metrics.
   - SHA256 hashes for key `.npy` outputs.
   - Required pass condition: all compared artifacts match.

4. If mismatch:
   - Stop and report mismatch files.
   - Fix parameter/config drift first.
   - Rerun both flows and compare again.

5. Finalize outputs:
   - Remove old `outputs/Final_team_run` and `outputs/onebyone_final_team_run`.
   - Rename latest timestamped run folder to `outputs/final_team_run`.
   - Update `outputs/final_team_run/pipeline_outputs.json` to point to `outputs/final_team_run/...` paths.

6. Review and git:
   - Review staged diff for output path validity.
   - Commit with clear message.
   - Push to `origin/final`.

## Report Template

- Pipeline rerun status
- One-by-one rerun status
- Parity result (`ALL_MATCH=True/False`)
- Final preserved output directory
- Commit SHA and push result
