#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def run_cmd(cmd: list[str], cwd: Path | None = None):
    print("[CMD]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def ensure_masks(flow: dict, root: Path):
    g = flow.get("gds_input", {})
    if not g.get("enabled", False):
        return

    gds_path = root / g.get("gds_path", "gds/basic.gds")
    layer_map = root / "configs" / "layer_map.json"
    outdir = root / g.get("out_mask_dir", "masks")
    outdir.mkdir(parents=True, exist_ok=True)

    if not layer_map.exists():
        raise FileNotFoundError(
            "configs/layer_map.json not found. Copy configs/layer_map_example.json first."
        )

    run_cmd(
        [
            "python",
            "gds_router/gds_to_masks.py",
            "--gds",
            str(gds_path),
            "--layer_map",
            str(layer_map),
            "--outdir",
            str(outdir),
            "--N",
            str(int(g.get("grid_size", 1024))),
            "--top_cell",
            str(g.get("top_cell", "")),
        ],
        cwd=root,
    )


def run_stage1_litho(root: Path, flow: dict, stage1_out: Path):
    litho_cfg = flow["mask_strategy"]["POLY"].get("litho_config", "configs/lithography_config.json")
    run_cmd(
        [
            "python",
            "01_lithography/run_project.py",
            "--config",
            litho_cfg,
        ],
        cwd=root,
    )

    src = root / "outputs" / "stage1_poly_litho"
    resist = src / "resist.npy"
    if not resist.exists():
        raise FileNotFoundError(f"Stage 1 did not produce resist file at {resist}")

    shutil.copy2(resist, stage1_out / "resist.npy")
    metrics = src / "metrics.json"
    if metrics.exists():
        shutil.copy2(metrics, stage1_out / "metrics.json")


def main():
    ap = argparse.ArgumentParser(description="Run Stage 1-6 flow in one command")
    ap.add_argument("--flow", default="configs/process_flow.json")
    ap.add_argument("--runname", default="team_run")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    flow = load_json((root / args.flow).resolve())

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outroot = root / "outputs" / f"{ts}_{args.runname}"
    outroot.mkdir(parents=True, exist_ok=True)

    ensure_masks(flow, root)

    s1_out = outroot / "stage1_poly_litho"
    s2_out = outroot / "stage2_etch"
    s3_out = outroot / "stage3_cvd"
    s4_out = outroot / "stage4_implant_thermal"
    s5_out = outroot / "stage5_metallization_cmp"
    s6_out = outroot / "stage6_device"
    for p in [s1_out, s2_out, s3_out, s4_out, s5_out, s6_out]:
        p.mkdir(parents=True, exist_ok=True)

    run_stage1_litho(root, flow, s1_out)

    s2p = flow["stage_params"]["etch"]
    run_cmd(
        [
            "python",
            "stage2_etch.py",
            "--resist",
            str(s1_out / "resist.npy"),
            "--outdir",
            str(s2_out),
            "--pixel_um",
            str(s2p["pixel_um"]),
            "--base_rate_Apm",
            str(s2p["base_rate_Apm"]),
            "--film_thickness_A",
            str(s2p["film_thickness_A"]),
            "--pressure_mTorr",
            str(s2p["pressure_mTorr"]),
            "--rf_power_W",
            str(s2p["rf_power_W"]),
            "--magnetic_field_mT",
            str(s2p["magnetic_field_mT"]),
        ],
        cwd=root / "02_process_stages",
    )

    s3p = flow["stage_params"]["cvd"]
    run_cmd(
        [
            "python",
            "stage3_cvd.py",
            "--openings",
            str(s2_out / "etched_openings.npy"),
            "--outdir",
            str(s3_out),
            "--pixel_um",
            str(s3p["pixel_um"]),
            "--trench_depth_um",
            str(s3p["trench_depth_um"]),
            "--target_thickness_um",
            str(s3p["target_thickness_um"]),
            "--conformality",
            str(s3p["conformality"]),
            "--regime",
            str(s3p["regime"]),
            "--temperature_C",
            str(s3p["temperature_C"]),
            "--hdp_cycles",
            str(s3p["hdp_cycles"]),
            "--hdp_sputter_frac",
            str(s3p["hdp_sputter_frac"]),
        ],
        cwd=root / "02_process_stages",
    )

    s4p = flow["stage_params"]["implant_thermal"]
    s4_cmd = [
        "python",
        "stage4_thermal_implant.py",
        "--outdir",
        str(s4_out),
        "--dopant",
        str(s4p["dopant"]),
        "--dose_cm2",
        str(s4p["dose_cm2"]),
        "--energy_keV",
        str(s4p["energy_keV"]),
        "--anneal_method",
        str(s4p["anneal_method"]),
        "--anneal_T_C",
        str(s4p["anneal_T_C"]),
        "--anneal_time_s",
        str(s4p["anneal_time_s"]),
        "--tilt_deg",
        str(s4p["tilt_deg"]),
        "--screen_oxide_nm",
        str(s4p["screen_oxide_nm"]),
    ]
    if bool(s4p.get("channeling", False)):
        s4_cmd.append("--channeling")
    if bool(s4p.get("pre_amorphous", False)):
        s4_cmd.append("--pre_amorphous")
    run_cmd(s4_cmd, cwd=root / "02_process_stages")

    s5p = flow["stage_params"]["met_cmp"]
    run_cmd(
        [
            "python",
            "stage5_metallization_cmp.py",
            "--depth_map",
            str(s3_out / "depth_map_um.npy"),
            "--features",
            str(s2_out / "etched_openings.npy"),
            "--outdir",
            str(s5_out),
            "--barrier_nm",
            str(s5p["barrier_nm"]),
            "--seed_nm",
            str(s5p["seed_nm"]),
            "--overburden_um",
            str(s5p["overburden_um"]),
            "--cmp_target_overburden_um",
            str(s5p["cmp_target_overburden_um"]),
            "--dishing_strength_um",
            str(s5p["dishing_strength_um"]),
            "--erosion_strength_um",
            str(s5p["erosion_strength_um"]),
        ],
        cwd=root / "02_process_stages",
    )

    s6p = flow["stage_params"]["device"]
    run_cmd(
        [
            "python",
            "stage6_device.py",
            "--etch_summary",
            str(s2_out / "summary.json"),
            "--implant_metrics",
            str(s4_out / "metrics.json"),
            "--cmp_metrics",
            str(s5_out / "metrics.json"),
            "--outdir",
            str(s6_out),
            "--cd_nom_nm",
            str(s6p["cd_nom_nm"]),
            "--tox_nm",
            str(s6p["tox_nm"]),
            "--temp_C",
            str(s6p["temp_C"]),
            "--W_um",
            str(s6p["W_um"]),
        ],
        cwd=root / "02_process_stages",
    )

    save_json(
        outroot / "pipeline_outputs.json",
        {
            "stage1_resist": str(s1_out / "resist.npy"),
            "stage2_summary": str(s2_out / "summary.json"),
            "stage3_summary": str(s3_out / "summary.json"),
            "stage4_metrics": str(s4_out / "metrics.json"),
            "stage5_metrics": str(s5_out / "metrics.json"),
            "stage6_metrics": str(s6_out / "metrics.json"),
        },
    )
    print("Done. Outputs:", outroot)


if __name__ == "__main__":
    main()
