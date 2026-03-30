#!/usr/bin/env python
from __future__ import annotations
import argparse, json, shutil, subprocess, time
from pathlib import Path
import numpy as np
from mask_ops import apply_bias_nm, apply_overlay_nm
from datetime import datetime

def load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def run_cmd(cmd: list[str], cwd: Path | None = None):
    print("[CMD]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)

def ensure_masks(flow: dict, root: Path):
    g = flow.get("gds_input", {})
    if not g.get("enabled", False):
        return
    gds_path = root / g.get("gds_path", "gds/standard_cell.gds")
    layer_map = root / "configs" / "layer_map.json"
    outdir = root / g.get("out_mask_dir", "masks")
    outdir.mkdir(parents=True, exist_ok=True)
    if not layer_map.exists():
        raise FileNotFoundError("configs/layer_map.json not found. Copy configs/layer_map_example.json to layer_map.json and edit.")
    run_cmd([
        "python", "gds_router/gds_to_masks.py",
        "--gds", str(gds_path),
        "--layer_map", str(layer_map),
        "--outdir", str(outdir),
        "--N", str(int(g.get("grid_size", 1024))),
        "--top_cell", str(g.get("top_cell",""))
    ], cwd=root)

def load_mask(root: Path, name: str) -> np.ndarray:
    p = root / "masks" / f"{name}.npy"
    if not p.exists():
        raise FileNotFoundError(f"Mask not found: {p}")
    return np.load(p).astype(np.uint8)

def apply_simple(mask: np.ndarray, cfg: dict, dx_nm: float) -> np.ndarray:
    m = apply_bias_nm(mask, float(cfg.get("bias_nm", 0.0)), dx_nm)
    ov = float(cfg.get("overlay_nm", 0.0))
    if ov != 0.0:
        m = apply_overlay_nm(m, ov, 0.0, dx_nm)
    return m

def run_poly_litho(root: Path, flow: dict, outdir: Path) -> Path:
    litho_dir = root / "01_lithography"
    litho_cfg_path = root / flow["mask_strategy"]["POLY"].get("litho_config", "configs/litho_config.json")
    shutil.copy2(litho_cfg_path, litho_dir/"config.json")

    # Ensure POLY.png exists for the KLayout-to-mask converter in the litho project.
    poly_png = root/"masks"/"POLY.png"
    if not poly_png.exists():
        from PIL import Image
        m = load_mask(root, "POLY")
        Image.fromarray((m*255).astype(np.uint8)).save(poly_png)

    # Run lithography project
    run_cmd(["python", "run_project.py", "--config", "config.json"], cwd=litho_dir)
    # ===== COPY resist.npy into pipeline stage1 directory =====
    # run_project.py writes to 01_lithography/outputs/stage1_poly_litho
    src_resist = litho_dir / "outputs" / "stage1_poly_litho" / "resist.npy"
    dst_resist = outdir / "resist.npy"

    if not src_resist.exists():
        raise FileNotFoundError(
            f"Stage1 litho did not produce resist.npy at {src_resist}"
        )

    shutil.copy2(src_resist, dst_resist)
    # ==========================================================

    # Minimal poly summary (Leff extraction can be improved later; keep a stable interface now)
    poly_summary = outdir / "poly_summary.json"
    # Try to locate any summary in litho outputs; if none, use default.
    cand = list((litho_dir/"outputs").glob("**/*summary*.json"))
    if cand:
        shutil.copy2(cand[0], poly_summary)
    else:
        save_json(poly_summary, {"Leff_nm": 180.0, "note": "Default Leff used. (Instructor can enable Leff extraction in litho stage.)"})
    return poly_summary

def main():
    ap = argparse.ArgumentParser(description="7-mask Virtual Mini-Foundry runner")
    ap.add_argument("--flow", default="configs/process_flow.json")
    ap.add_argument("--runname", default="team_run")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    run_name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_team_run"
    outroot = root / "outputs" / run_name
    outroot.mkdir(parents=True, exist_ok=True)
    flow = load_json((root/args.flow).resolve())

    dx_nm = float(flow["stage_params"]["dx_nm"])

    ts = time.strftime("%Y%m%d_%H%M%S")
    outroot = root/"outputs"/f"{ts}_{args.runname}"
    outroot.mkdir(parents=True, exist_ok=True)

    ensure_masks(flow, root)

    outroot = root / "outputs" / run_name
    outroot.mkdir(parents=True, exist_ok=True)

    # ===== 明确声明所有 stage 输出目录 =====
    poly_out = outroot / "stage1_poly_litho"
    poly_out.mkdir(parents=True, exist_ok=True)

    s2_out = outroot / "stage2_etch"
    s2_out.mkdir(parents=True, exist_ok=True)

    s4_out = outroot / "stage4_implant_thermal"
    s4_out.mkdir(parents=True, exist_ok=True)

    s5_out = outroot / "stage5_metallization_cmp"
    s5_out.mkdir(parents=True, exist_ok=True)

    s6_out = outroot / "stage6_device"
    s6_out.mkdir(parents=True, exist_ok=True)
    # =======================================


    # Prepare masks (except POLY)
    strat = flow["mask_strategy"]
    prepared = {}
    for name in flow["mask_layers"]:
        if name == "POLY":
            continue
        m = load_mask(root, name)
        mode = strat.get(name, {}).get("mode", "ideal")
        if mode == "ideal":
            prepared[name] = m
        elif mode == "simple_litho":
            prepared[name] = apply_simple(m, strat[name], dx_nm)
        else:
            prepared[name] = m

    # Stage1 litho
    poly_out = outroot/"stage1_poly_litho"
    poly_out.mkdir(exist_ok=True)
    poly_summary = run_poly_litho(root, flow, poly_out)

    # Save prepared masks to tmp
    tmp = outroot/"_tmp_masks"; tmp.mkdir(exist_ok=True)
    for n in ["ACTIVE","NIMP","PIMP","CONT","M1","V1"]:
        np.save(tmp/f"{n}.npy", prepared[n])

    # poly_out / "resist.npy"  # TODO: unclear purpose, likely dead code

    # Stage2 etch
    s2p = flow["stage_params"]["etch"]
    s2_out = outroot / "stage2_etch"
    s2_out.mkdir(parents=True, exist_ok=True)
    run_cmd([
        "python", "stage2_etch.py",
        "--resist", str(poly_out / "resist.npy"),
        "--outdir", str(s2_out),
        "--pixel_um", str(s2p.get("pixel_um", 0.02)),
        "--base_rate_Apm", str(s2p.get("base_rate_Apm", 5000.0)),
        "--film_thickness_A", str(s2p.get("film_thickness_A", 3000.0)),
        "--pressure_mTorr", str(s2p.get("pressure_mTorr", 15.0)),
        "--rf_power_W", str(s2p.get("rf_power_W", 400.0)),
        "--magnetic_field_mT", str(s2p.get("magnetic_field_mT", 50.0)),
    ], cwd=root / "02_process_stages")

    # Stage4 implant+thermal
    s4p = flow["stage_params"]["implant_thermal"]
    s4_out = outroot/"stage4_implant_thermal"
    run_cmd([
        "python","stage4_implant_thermal_multimask.py",
        "--active_npy", str(tmp/"ACTIVE.npy"),
        "--nimp_npy", str(tmp/"NIMP.npy"),
        "--pimp_npy", str(tmp/"PIMP.npy"),
        "--poly_summary_json", str(poly_summary),
        "--outdir", str(s4_out),
        "--dx_nm", str(dx_nm),
        "--implant_dose_cm2", str(s4p["implant_dose_cm2"]),
        "--implant_energy_keV", str(s4p["implant_energy_keV"]),
        "--tilt_deg", str(s4p["tilt_deg"]),
        "--channeling", str(int(bool(s4p["channeling"]))),
        "--screen_oxide_nm", str(s4p["screen_oxide_nm"]),
        "--anneal_mode", str(s4p["anneal_mode"]),
        "--T_C", str(s4p["T_C"]),
        "--t_s", str(s4p["t_s"]),
    ], cwd=root/"02_process_stages")

    # Stage5 metallization+CMP
    s5p = flow["stage_params"]["met_cmp"]
    s5_out = outroot/"stage5_metallization_cmp"
    run_cmd([
        "python","stage5_metallization_cmp_multimask.py",
        "--cont_npy", str(tmp/"CONT.npy"),
        "--m1_npy", str(tmp/"M1.npy"),
        "--v1_npy", str(tmp/"V1.npy"),
        "--outdir", str(s5_out),
        "--overburden_nm", str(s5p["overburden_nm"]),
        "--target_overburden_nm", str(s5p["target_overburden_nm"]),
        "--pattern_density_window", str(s5p["pattern_density_window"]),
    ], cwd=root/"02_process_stages")

    # Stage6 device
    s6p = flow["stage_params"]["device"]
    s6_out = outroot / "stage6_device"
    s6_out.mkdir(parents=True, exist_ok=True)
    run_cmd([
        "python", "stage6_device.py",
        "--etch_summary", str(s2_out / "summary.json"),
        "--implant_metrics", str(s4_out / "metrics_stage4.json"),
        "--cmp_metrics", str(s5_out / "metrics_stage5.json"),
        "--outdir", str(s6_out),
        "--tox_nm", str(s6p.get("tox_nm", 2.0)),
        "--W_um", str(s6p.get("W_nm", 1000.0) * 1e-3),
    ], cwd=root / "02_process_stages")

    save_json(outroot/"pipeline_outputs.json", {
        "poly_summary": str(poly_summary),
        "device_inputs": str(s4_out/"device_inputs.json"),
        "metal_metrics": str(s5_out/"metrics_stage5.json"),
        "device_metrics": str(s6_out/"metrics_stage6.json"),
    })
    print("✅ Done. Outputs:", outroot)

if __name__ == "__main__":
    main()
