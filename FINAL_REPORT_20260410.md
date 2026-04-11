## Final Consistency Report

Date: 2026-04-11

### Objective
Make `run-7` and `run-one-by-one` produce consistent results while keeping lithography config usage correct.

### Fixes Implemented
- `configs/litho_config_pipeline.json` synchronized to `configs/lithography_config.json`.
- `configs/process_flow.json` updated with tested one-by-one parameters:
	- Etch: `base_rate_Apm=5500`, `pressure_mTorr=12`, `rf_power_W=500`
	- CVD: `target_thickness_um=0.5`, `conformality=0.95`, `regime=mass_transport`
	- Implant: `dose=2e15`, `energy=4`, `anneal=1050C/10s`, `pre_amorphous=true`
	- CMP: `overburden_um=0.8`, `cmp_target_overburden_um=0.12`, `dishing=0.05`, `erosion=0.02`
	- Device: `cd_nom_nm=200`, `tox_nm=2.5`, `temp_C=25`, `W_nm=1200`
- `02_process_stages/run_7mask_pipeline.py` refactored to run the same Stage2-Stage6 standalone chain as one-by-one and to write actual output file paths in `pipeline_outputs.json`.

### Full Rerun Status
- Re-executed entire `run.ipynb` end-to-end successfully.
- Latest integrated run folder: `outputs/20260411_092122_clean_final`.

### Quality and Consistency Verification
Compared one-by-one outputs (`outputs/stage*`) vs latest run-7 outputs (`outputs/20260411_092122_clean_final/stage*`).

All key deltas are exactly zero (`run7 - one_by_one = 0`):
- Stage2: `open_area`, `avg_rate_Apm`, `anisotropy_index`, `lateral_bias_um`
- Stage4: `junction_depth_um`, `sheet_resistance_ohm_per_sq`, `activation_fraction`, `peak_cm3`
- Stage5: `topo_range_um`, `copper_mean_um`
- Stage6: `Vt_proxy_V`, `Ioff_proxy_A`, `Ron_proxy_ohm`, `interconnect_R_proxy_ohm`

### Conclusion
The pipeline and one-by-one flows are now fully consistent on all checked metrics, and the lithography configuration direction was corrected as requested.
