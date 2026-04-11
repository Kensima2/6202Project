# Final Report (Submission Version)

Date: 2026-04-10
Project: Virtual Mini-Foundry — Lithography-led process-device flow

## 1. Objective and Spec
- Pattern: 1D line/space
- Pitch: 360 nm
- Target CD: 180 nm ±10 nm
- Key tools:
  - Lithography runner: `01_lithography/run_project.py`
  - RET: PSM + OPC
  - Resist model: finite contrast
  - Process chain: `02_process_stages` Stage2–Stage6
- Primary config: `configs/lithography_config.json`

## 2. Baseline Reproduction
Baseline outputs were generated in `outputs/stage1_poly_litho`.
Required figures:
- `demo_1d_mask_image_resist.png`
- `process_window.png`
- `cd_vs_dose.png`
- `cd_vs_defocus.png`

Key lithography metrics:
- `window_area_dose_nm`: 125.90
- `target_cd_nm`: 180 nm
- `wavelength_nm`: 193 nm
- `NA`: 0.93
- `peb_blur_nm`: 5 nm
- `resist_contrast_gamma`: 20

These results indicate a usable process window around the nominal center point and baseline CD control consistent with the target.

## 3. Imaging / RET Extension
Implemented:
- PSM enabled on spaces
- OPC bias = 40 nm

Supporting files:
- `outputs/stage1_poly_litho/ret_psm_aerial_compare_1d.png`
- `outputs/stage1_poly_litho/ret_opc_resist_compare_1d.png`

Effect summary:
- PSM improved aerial image edge shaping.
- OPC reduced resist CD variation and tightened the process window.
- The non-zero process window confirms the RET changes improved robustness under dose/defocus variation.

## 4. Resist / Process Extension
Implemented finite resist contrast using `resist_contrast_gamma = 20`.

Supporting file:
- `outputs/stage1_poly_litho/resist_contrast_compare_1d.png`

Effect summary:
- Finite contrast smooths CD response versus dose and defocus.
- The result is reduced CD sensitivity compared to a hard-threshold model, improving manufacturability.

## 5. Manufacturability Metric
Selected metrics:
- Lithography process window: `window_area_dose_nm = 125.90`
- Etch proxy: `lateral_bias_um = 0.01621`
- Etch anisotropy: `anisotropy_index = 0.93516`

The lithography recipe supports downstream manufacturability by producing a moderate open area and a stable resist profile for Stage2 etch.

## 6. Engineering Trade-offs
Observed trade-offs:
- `NA` and imaging quality versus defocus tolerance.
- RET gain versus sensitivity: stronger OPC/PSM helps edge fidelity but must be balanced to avoid over-correction.
- Lithography decision versus full-flow consistency: Stage1 changes propagate into etch loading, implant profiles, CMP behavior, and device proxies.

System-level finding:
- One-by-one notebook execution and `run_7mask_pipeline.py` are both functional, but current flows diverge because of different Stage1 config usage and differing Stage4/5 schema handling.

## 7. Conclusion
Recommended center recipe:
- Lithography: dose0 = 1.0, defocus ≈ 0 nm, NA = 0.93, sigma_in/sigma_out = 0.0/0.5, PEB blur = 5 nm, PSM + OPC enabled.
- Etch: base_rate = 5500 Å/min, pressure = 12 mTorr, RF = 500 W.
- Implant: B, dose = 2e15 cm^-2, energy = 4 keV, RTA 1050°C 10 s, pre-amorphous enabled.
- CMP: target overburden = 0.12 µm, dishing = 0.05 µm, erosion = 0.02 µm.

Final one-by-one device proxy metrics:
- `Vt_proxy_V`: 0.86957
- `Ioff_proxy_A`: 5.94×10^-6
- `Ron_proxy_ohm`: 2.4383
- `interconnect_R_proxy_ohm`: 6.9260

Next steps:
- Align lithography config between notebook and pipeline paths.
- Harmonize Stage4/Stage5 outputs for Stage6 input consistency.
- Re-run both flows under identical interface definitions for strict comparison.

## 2D Contact and Spin Coating
- 2D contact mode was not included in this run.
- Spin coating outputs were not generated for this run.
