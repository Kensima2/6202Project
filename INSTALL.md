# Virtual Mini-Foundry (7-mask) - Install & Quick Run

## 1) Python environment (recommended)
- Install Python 3.10+ (Anaconda/Miniconda recommended)
- Create env:
  - conda create -n minifab python=3.10
  - conda activate minifab
- Install dependencies:
  - pip install -r requirements.txt

## 2) Optional: KLayout (mask editing)
- Install KLayout (GUI) to draw/edit masks.
- Export masks either as:
  - GDS (recommended, multi-layer), then use `gds_router/gds_to_masks.py`
  - OR a single PNG mask for lithography demo (already supported in 01_lithography)

## 3) Prepare your inputs
- Put your Cadence-exported GDS here:
  - `gds/standard_cell.gds`
- Edit `configs/layer_map.json` to map each logical layer name to (layer, datatype)
  - Example is provided in `configs/layer_map_example.json`

## 4) Run the 7-mask pipeline
From the project root:
- cd 02_process_stages
- python run_7mask_pipeline.py --flow ../configs/process_flow.json --runname TEAM01

Outputs:
- `outputs/<timestamp>_TEAM01/`
  - stage1_poly_litho/
  - stage4_implant_thermal/
  - stage5_metallization_cmp/
  - stage6_device/
  - pipeline_outputs.json

## Notes
This is a teaching model. The physics is simplified on purpose; the goal is to learn *relationships*, *trade-offs* and *workflow discipline*.
