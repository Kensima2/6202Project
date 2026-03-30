
# Virtual Mini-Foundry: Process–Device Co-Design (Basic Code)

This repository is a **teaching sandbox** (not a foundry-accurate TCAD flow).
It is designed to support MSc student teams with limited coding background.

## What students will do
Teams play a *virtual fab team* and co-design:
1) **Lithography** defines critical dimension (CD)
2) **Etch** transfers pattern and introduces bias / profile effects
3) **CVD** deposits dielectrics and explores step coverage / gap fill
4) **Ion implantation + thermal anneal** sets junction depth and sheet resistance
5) **Metallization + CMP** creates interconnect and explores dishing/erosion
6) **Device proxy** maps process outputs to Vt / leakage / resistance

The code is intentionally modular so students can:
- tweak recipe knobs
- extend models (better physics)
- add optimization loops (OPC/SMO is in the litho pack; this mini-fab extends to the process chain)

## Recommended environment (easy mode)
- Python 3.10+ (Anaconda / Miniconda OK)
- numpy, matplotlib

Install:
```bash
pip install numpy matplotlib
```

## File overview
- `litho_stage_basic.py`, `illumination_models.py`: lithography baseline
- `stage2_etch.py`: etch with anisotropy + loading + selectivity proxy
- `stage3_cvd.py`: dielectric CVD step coverage + (optional) HDP dep/etch/dep
- `stage4_thermal_implant.py`: implant + anneal/diffusion + activation
- `stage5_metallization_cmp.py`: Cu damascene + CMP (dishing/erosion proxy)
- `stage6_device.py`: compact device proxies
- `plasma_basics_utils.py`: helper functions linked to plasma lecture knobs

## Minimal run (example)
1) Lithography produces a resist image (from your litho baseline package).
   Suppose you have `out_litho/resist_developed.npy`.

2) Etch:
```bash
python stage2_etch.py --resist out_litho/resist_developed.npy --outdir out_stage2
```

3) CVD:
```bash
python stage3_cvd.py --openings out_stage2/etched_openings.npy --outdir out_stage3
```

4) Implant + thermal:
```bash
python stage4_thermal_implant.py --outdir out_stage4 --dopant B --dose_cm2 1e15 --energy_keV 20 \
  --anneal_method rta --anneal_T_C 1050 --anneal_time_s 10 --channeling
```

5) Metallization + CMP:
```bash
python stage5_metallization_cmp.py --depth_map out_stage3/depth_map_um.npy --features out_stage2/etched_openings.npy --outdir out_stage5
```

6) Device proxy:
```bash
python stage6_device.py --etch_summary out_stage2/summary.json --implant_metrics out_stage4/metrics.json --cmp_metrics out_stage5/metrics.json --outdir out_stage6
```

## Where students should modify (suggested)
- `stage2_etch.py`: micro-loading model and anisotropy-to-bias mapping
- `stage3_cvd.py`: implement angle-dependent deposition; add ALD vs PECVD vs LPCVD choices
- `stage4_thermal_implant.py`: replace toy Rp/ΔRp model; implement 2D diffusion
- `stage5_metallization_cmp.py`: improve CMP with Preston equation and selectivity
- `stage6_device.py`: replace proxies with a better compact model

---
© Teaching code for educational use.
