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
    flow = load_json((root/args.flow).resolve())

    dx_nm = float(flow["stage_params"]["dx_nm"])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outroot = root / "outputs" / f"{ts}_{args.runname}"
    outroot.mkdir(parents=True, exist_ok=True)

    ensure_masks(flow, root)

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

    # Stage3 CVD (aligned to notebook one-by-one chain)
    s3p = flow["stage_params"].get("cvd", {})
    s3_out = outroot / "stage3_cvd"
    s3_out.mkdir(parents=True, exist_ok=True)
    s2_summary = load_json(s2_out / "summary.json")
    trench_depth_um = float(s2_summary.get("film_thickness_A", 3000.0)) / 10000.0
    run_cmd([
        "python", "stage3_cvd.py",
        "--openings", str(s2_out / "etched_openings.npy"),
        "--outdir", str(s3_out),
        "--pixel_um", str(s3p.get("pixel_um", 0.02)),
        "--trench_depth_um", str(s3p.get("trench_depth_um", trench_depth_um)),
        "--target_thickness_um", str(s3p.get("target_thickness_um", 0.5)),
        "--conformality", str(s3p.get("conformality", 0.95)),
        "--regime", str(s3p.get("regime", "mass_transport")),
        "--temperature_C", str(s3p.get("temperature_C", 400.0)),
        "--hdp_cycles", str(s3p.get("hdp_cycles", 0)),
        "--hdp_sputter_frac", str(s3p.get("hdp_sputter_frac", 0.25)),
    ], cwd=root / "02_process_stages")

    # Stage4 implant+thermal (standalone model, aligned to notebook)
    s4p = flow["stage_params"]["implant_thermal"]
    s4_out = outroot / "stage4_implant_thermal"
    s4_cmd = [
        "python", "stage4_thermal_implant.py",
        "--outdir", str(s4_out),
        "--dopant", str(s4p.get("dopant", "B")),
        "--dose_cm2", str(s4p.get("implant_dose_cm2", 2e15)),
        "--energy_keV", str(s4p.get("implant_energy_keV", 4.0)),
        "--anneal_method", str(s4p.get("anneal_method", "rta")),
        "--anneal_T_C", str(s4p.get("T_C", 1050.0)),
        "--anneal_time_s", str(s4p.get("t_s", 10.0)),
        "--tilt_deg", str(s4p.get("tilt_deg", 7.0)),
        "--screen_oxide_nm", str(s4p.get("screen_oxide_nm", 10.0)),
    ]
    if bool(s4p.get("channeling", True)):
        s4_cmd.append("--channeling")
    if bool(s4p.get("pre_amorphous", True)):
        s4_cmd.append("--pre_amorphous")
    run_cmd(s4_cmd, cwd=root / "02_process_stages")

    # Stage5 metallization+CMP (standalone model, aligned to notebook)
    s5p = flow["stage_params"]["met_cmp"]
    s5_out = outroot / "stage5_metallization_cmp"
    run_cmd([
        "python", "stage5_metallization_cmp.py",
        "--depth_map", str(s3_out / "depth_map_um.npy"),
        "--features", str(s2_out / "etched_openings.npy"),
        "--outdir", str(s5_out),
        "--barrier_nm", str(s5p.get("barrier_nm", 10.0)),
        "--seed_nm", str(s5p.get("seed_nm", 50.0)),
        "--overburden_um", str(s5p.get("overburden_um", 0.8)),
        "--cmp_target_overburden_um", str(s5p.get("cmp_target_overburden_um", 0.12)),
        "--dishing_strength_um", str(s5p.get("dishing_strength_um", 0.05)),
        "--erosion_strength_um", str(s5p.get("erosion_strength_um", 0.02)),
    ], cwd=root / "02_process_stages")

    # Stage6 device
    s6p = flow["stage_params"]["device"]
    s6_out = outroot / "stage6_device"
    s6_out.mkdir(parents=True, exist_ok=True)
    run_cmd([
        "python", "stage6_device.py",
        "--etch_summary", str(s2_out / "summary.json"),
        "--implant_metrics", str(s4_out / "metrics.json"),
        "--cmp_metrics", str(s5_out / "metrics.json"),
        "--outdir", str(s6_out),
        "--cd_nom_nm", str(s6p.get("cd_nom_nm", 200.0)),
        "--tox_nm", str(s6p.get("tox_nm", 2.0)),
        "--temp_C", str(s6p.get("temp_C", 25.0)),
        "--W_um", str(s6p.get("W_nm", 1000.0) * 1e-3),
    ], cwd=root / "02_process_stages")

    save_json(outroot/"pipeline_outputs.json", {
        "poly_summary": str(poly_summary),
        "stage2_metrics": str(s2_out/"summary.json"),
        "stage3_metrics": str(s3_out/"summary.json"),
        "implant_metrics": str(s4_out/"metrics.json"),
        "metal_metrics": str(s5_out/"metrics.json"),
        "device_metrics": str(s6_out/"metrics.json"),
    })
    print("✅ Done. Outputs:", outroot)

if __name__ == "__main__":
    main()
