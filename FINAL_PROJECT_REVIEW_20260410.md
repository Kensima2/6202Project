# Final Project Review (Notebook Full Run + Pipeline Consistency)

Date: 2026-04-10

## 1) User request closure status
- Restored deleted historical team-run folders for comparison:
  - outputs/20260121_184904_team_run
  - outputs/20260121_185921_team_run
  - outputs/20260121_190303_team_run
- Re-ran the full notebook workflow end-to-end, including:
  - Stage 1 lithography
  - Stage 2/3/4/5/6 one-by-one chain
  - Stage 16 integrated run_7mask_pipeline invocation
- New integrated run generated:
  - outputs/20260410_132451_team_run

## 2) README-based flow review (01 + 02)
From 01_lithography/README.md:
- Stage 1 is a full photolithography module with process-window/CD behavior driven by run_project.py config.
- Lithography recipe differences (NA/sigma/PEB/RET/target CD) can significantly change resist/open-area and therefore downstream process behavior.

From 02_process_stages/README.md:
- The teaching chain is modular.
- The integrated 7-mask path uses multimask Stage 4/5 modules and skips Stage 3 CVD in the current integrated flow implementation.

Conclusion:
- The process pipeline starts with lithography, and Stage 1 settings are a first-order driver for all later stages.
- One-by-one and integrated runs are not automatically numerically identical unless both flow topology and interface schemas are aligned.

## 3) One-by-one vs integrated comparison (current run)
### One-by-one (notebook stage cells)
- Stage1 window_area_dose_nm: 125.90
- Stage2 open_area: 0.27083334
- Stage2 avg_rate_Apm: 1931.4451
- Stage6 Vt_proxy_V: 0.8695661
- Stage6 Ioff_proxy_A: 5.936818e-06
- Stage6 Ron_proxy_ohm: 2.438286

### Integrated run_7mask_pipeline (outputs/20260410_132451_team_run)
- Stage1 poly_summary Leff_nm: 180.0 (default placeholder from poly_summary)
- Stage2 open_area: 0.76666665
- Stage2 avg_rate_Apm: 1320.1633
- Stage6 Vt_proxy_V: 0.6751632
- Stage6 Ioff_proxy_A: 2.999999e-05
- Stage6 Ron_proxy_ohm: 139.64864

## 4) Why they are currently different
1. Stage 1 lithography config mismatch:
   - Notebook Stage 1 uses configs/lithography_config.json.
   - Integrated pipeline copies configs/litho_config_pipeline.json into 01_lithography/config.json before running run_project.py.
   - These configs have very different CD target and optical/process settings, so resist/open-area diverge early.

2. Flow topology mismatch:
   - Notebook one-by-one path includes Stage 3 CVD and uses standalone Stage 4/5 scripts.
   - Integrated pipeline uses multimask Stage 4/5 and does not use Stage 3 in the same way.

3. Stage schema mismatch into Stage 6:
   - Integrated Stage 6 consumed metrics_stage4.json / metrics_stage5.json where expected keys do not fully map to standalone Stage 6 feature names.
   - Stage 6 fell back to internal defaults (e.g., Na_proxy_peak_cm3=1e18, sheet_R=1000, cu_mean=0.2), strongly changing Vt/Ioff/Ron.

## 5) Code consistency findings to fix next
### High priority
- run_7mask_pipeline.py writes pipeline_outputs.json with device_metrics -> stage6_device/metrics_stage6.json,
  but stage6_device.py writes stage6_device/metrics.json.

### High priority
- run_7mask_pipeline.py defines runname multiple times and finally reverts to a hard-coded timestamp_team_run path,
  which can override the user-provided --runname intention.

## 6) Pass/readiness judgment
- Functional status: PASS for executable workflow (full notebook runs without stopping errors).
- Scientific consistency status: NOT YET PASS for "one-by-one equals integrated" criterion.
- Root cause is structural/config/schema mismatch, starting from lithography settings and propagating downstream.

## 7) Immediate alignment plan
1. Use the same lithography config for both flows (or explicitly document why not).
2. Unify Stage 4/5 metric key contracts consumed by stage6_device.py.
3. Fix pipeline output index filename (metrics.json vs metrics_stage6.json).
4. Clean runname handling so each invocation maps to one deterministic output folder.

## 8) Suggested next prompts (Autopilot style)
1. Refactor run_7mask_pipeline.py to remove duplicate outroot assignment and make --runname authoritative; add a unit test that asserts output folder name contains the exact runname.
2. Add a strict JSON-schema validator before Stage 6 that rejects missing keys instead of silently defaulting Na/sheet_R/cu_mean.
3. Create a cross-flow harmonization layer that maps multimask Stage 4/5 metrics into the exact fields expected by stage6_device.py, with an explicit provenance log.
4. Add a lithography parity check utility that compares notebook Stage 1 config against process_flow POLY litho_config and fails if key knobs differ beyond tolerance.
5. Generate a comparison report script that outputs one-by-one vs integrated deltas for Stage2/4/5/6 and flags deviations above threshold.
