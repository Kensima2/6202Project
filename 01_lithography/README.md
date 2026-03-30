# Photolithography Project (Formal Version)

This package is the **official course project** starter for the Photolithography module.
It is designed to be **open-source friendly** and **code-first**:
students start from a working baseline and then extend it to demonstrate deeper understanding.

## 0) Install
```bash
python -m pip install -r requirements.txt
```

## 1) Quick run (baseline demo)
```bash
python photolithography_baseline.py
```
You should see:
- mask / aerial image / developed resist (demo case)
- dose–defocus process window map
- CD vs dose and CD vs defocus slices

## 2) Project driver (recommended for submission)
Use the project runner to reproduce your final figures and metrics:
```bash
python run_project.py --config config.json
```

## 3) What you will modify
You **must** implement at least **one** item from each category:

### A. Imaging / RET (choose ≥1)
- Annular vs dipole illumination (deterministic sampling)
- Phase-shift mask (PSM) model
- Illumination optimization (maximize process window area)

### B. Resist / Process (choose ≥1)
- Resist contrast curve (instead of a hard threshold)
- PEB diffusion as a separate step (not just blur on intensity)
- Simple LER model and its impact on yield

### C. Metrics / Manufacturability (choose ≥1)
- NILS (normalized image log slope) at edge
- Window area metric and “best-center” point
- CD uniformity vs defocus/dose

## 4) Deliverables
- Code: your modified scripts + config (reproducible run)
- Figures: required plots listed in `REPORT_TEMPLATE.md`
- Report: max 6 pages (PDF), follow `REPORT_TEMPLATE.md` structure

## 5) Suggested workflow
1) Reproduce baseline results
2) Add one imaging/RET feature
3) Add one resist/process feature
4) Add one manufacturability metric
5) Sweep parameters and defend your recipe choices

## 2D Demo Added (New)
The official runner now **always exports both**:
- a **1D line/space** demo plot: `outputs/demo_1d_mask_image_resist.png`
- a **2D contact** demo set: `outputs/demo_2d_mask.png`, `outputs/demo_2d_aerial.png`, `outputs/demo_2d_resist.png`

If you want to run a **full process-window sweep in 2D contact mode**, use:
```bash
python run_project.py --config config_2d_contact.json
```
(Note: 2D sweeps can be slower.)

## 2D CD extraction (updated)
For 2D contact patterns, the baseline now uses a more manufacturing-relevant proxy:
- Restrict to the **center pitch cell**
- Find the **largest connected component** (4-connectivity)
- Report **equivalent circular diameter**: d_eq = 2*sqrt(area/pi)

This avoids over-counting when multiple resist islands appear.

## Industrial-grade 2D contact metrics (New)
When running 2D contact mode, the baseline now reports (at the nominal center point):
- **CD_fit_nm**: circle-fit CD from boundary points (least-squares)
- **circle_center_nm**: fitted center offset (nm)
- **EPE** (edge placement error) summary vs target CD
- **CDU proxy** across multiple pitch cells in the simulated field (mean/std of CD_fit)
- **NILS(2D) proxy**: median |∇ln I| on boundary (1/nm)

The runner also exports an overlay figure:
- `outputs/demo_2d_resist_circlefit.png`


## Spin coating simulation added (Photoresist thickness)
The runner now includes a teaching spin-coating model that outputs:
- `outputs/spin_thickness_vs_rpm.png`
- `outputs/spin_thickness_radial_profile.png`
- `outputs/spin_thickness_map.png`

It also demonstrates a **process-to-litho coupling**:
- thickness influences an effective **PEB blur** and **develop threshold** (configurable in `config.json`)

Tune:
- `config.json -> spin_coating`
- `config.json -> resist_coupling`


## Creative upgrade directions (students extend baseline code)
Your team should choose **one primary track** (deep) + **one secondary track** (light):

### Track 1 — Process realism (spin/bake/develop)
- Replace hard threshold with a **contrast curve** (e.g., sigmoid), calibrate to hit target CD
- Model **soft-bake / PEB** as diffusion on *photoacid* (separate state variable)
- Include **edge bead removal (EBR)** and show impact on CDU / yield proxies

### Track 2 — Imaging / RET
- Implement deterministic **annular / dipole / quadrupole** illumination and compare process window area
- Add **PSM** (phase-shift mask) for 1D and quantify NILS/window improvements
- Build a simple **optimizer** to maximize process window under CD tolerance

### Track 3 — 2D manufacturability
- Extend 2D contact to measure **EPE** at multiple angles (not only radial error)
- Compute **CDU heatmaps** vs (dose, defocus) and link to yield
- Add a simple **overlay error** / mask bias and quantify correction

### Track 4 — Stochastic effects (LER / noise / yield)
- Add photon shot-noise or resist noise → simulate **LER distribution**
- Define a pass/fail criterion and compute **yield vs process conditions**
- Compare which knob improves yield most (illumination vs PEB vs threshold)

### Track 5 — More complex targets
- Import a small **GDS** (optional via KLayout) and simulate multiple features in one run
- Mix patterns: line/space + contact + jogs, and propose a unified recipe



## RET (PSM / OPC / SMO) added (New)
This project now includes code-first demos for:
- **Phase Shift Mask (PSM)**: complex mask transmission (0 / pi phase regions)
- **Optical Proximity Correction (OPC)**: simple 1D bias + 2D morphology bias
- **Source-Mask Optimization (SMO)**: grid-search over illumination + mask bias to maximize process window area

Enable in `config.json`:
```json
"ret": {
  "psm": {"enabled": true, "phase_rad": 3.14159, "region": "spaces"},
  "opc": {"enabled": true, "mask_bias_nm": 20.0},
  "smo": {"enabled": true, "sigma_out_list": [0.3,0.5,0.7,0.9], "bias_nm_list": [-40,-20,0,20,40]}
}
```

### Custom mask exploration (advanced)
In `photolithography_baseline.py`, you can set:
- `CUSTOM_MASK_PATH` to a `.npy` file containing your own mask bitmap (1D or 2D)
- `CUSTOM_MASK_SCALE` to explore gray-tone / attenuated masks

This is intentionally simple so teams can create *creative* mask shapes (serifs, assist features, odd shapes).


## KLayout workflow (New): draw a 2D mask and simulate it
This project supports a simple pipeline to let students create masks in **KLayout** and run 2D simulations.

### Option A (recommended): Export PNG from KLayout and auto-import
1) Draw your mask in KLayout (GDS). Use a single layer for the mask.
2) Export an image:
   - File -> Export -> Image...
   - Use a square resolution (e.g., 1024x1024)
   - Prefer high contrast (black/white). If anti-aliasing happens, we will threshold it.
3) Put the PNG at `masks/klayout_mask.png` (or change `config.json -> klayout_mask.png_path`)
4) In `config.json`, set:
```json
"pattern": "contact_2d",
"klayout_mask": {
  "enabled": true,
  "auto_convert_on_run": true,
  "png_path": "masks/klayout_mask.png",
  "out_npy_path": "masks/custom_mask.npy",
  "size": 512,
  "threshold": 0.5,
  "invert": false
}
```
5) Run:
```bash
python run_project.py --config config.json
```
Outputs will include:
- `outputs/klayout_mask_import_preview.png`
- 2D aerial/resist plots using your imported mask

### Option B: Manual conversion (CLI)
```bash
python tools/klayout_png_to_npy.py --png masks/klayout_mask.png --out masks/custom_mask.npy --size 512 --threshold 0.5
```
Then set `photolithography_baseline.py -> CUSTOM_MASK_PATH = "masks/custom_mask.npy"` (advanced).

### Notes
- 1D demos remain unchanged.
- For best results, export PNG with minimal anti-aliasing.
- You can explore OPC/PSM/SMO on your custom shape (creative projects).
