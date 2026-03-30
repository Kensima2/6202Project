#!/usr/bin/env python
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np

def save_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--active_npy", required=True)
    ap.add_argument("--nimp_npy", required=True)
    ap.add_argument("--pimp_npy", required=True)
    ap.add_argument("--poly_summary_json", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--dx_nm", type=float, default=10.0)

    ap.add_argument("--implant_dose_cm2", type=float, default=1e13)
    ap.add_argument("--implant_energy_keV", type=float, default=20.0)
    ap.add_argument("--tilt_deg", type=float, default=7.0)
    ap.add_argument("--channeling", type=int, default=1)
    ap.add_argument("--screen_oxide_nm", type=float, default=0.0)
    ap.add_argument("--anneal_mode", type=str, default="RTA", choices=["Furnace","RTA"])
    ap.add_argument("--T_C", type=float, default=1000.0)
    ap.add_argument("--t_s", type=float, default=10.0)
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    active = np.load(args.active_npy).astype(np.uint8)
    nimp = np.load(args.nimp_npy).astype(np.uint8)
    pimp = np.load(args.pimp_npy).astype(np.uint8)

    nplus = (active & nimp).astype(np.uint8)
    pplus = (active & pimp).astype(np.uint8)

    Rp_nm = 2.5 * (args.implant_energy_keV ** 0.8)
    dRp_nm = 0.35 * Rp_nm

    ch = 1.0 if args.channeling else 0.0
    ch *= max(0.0, 1.0 - 0.06*abs(args.tilt_deg))
    if args.screen_oxide_nm > 0:
        ch *= math.exp(-args.screen_oxide_nm/10.0)

    Tb = (args.t_s) * math.exp((args.T_C - 900.0)/200.0)
    if args.anneal_mode == "Furnace":
        diffusion_nm = 1.2 * math.sqrt(Tb)
        activation = min(1.0, 0.55 + 0.08*math.log10(max(Tb, 1e-9)))
    else:
        diffusion_nm = 0.55 * math.sqrt(Tb)
        activation = min(1.0, 0.70 + 0.08*math.log10(max(Tb, 1e-9)))

    dose = args.implant_dose_cm2
    Neff = (dose / 1e13) * (0.75 + 0.25*activation) * (1.0 - 0.15*ch)
    xj_nm = Rp_nm + diffusion_nm + 0.35*ch*Rp_nm

    poly = json.load(open(args.poly_summary_json, "r", encoding="utf-8"))
    Leff_nm = float(poly.get("Leff_nm", 180.0))

    device_inputs = {
        "Leff_nm": Leff_nm,
        "xj_nm": float(xj_nm),
        "Neff_N_proxy": float(Neff),
        "Neff_P_proxy": float(Neff),
        "activation_proxy": float(activation),
        "dx_nm": float(args.dx_nm),
        "areas": {"active_px": int(active.sum()), "nplus_px": int(nplus.sum()), "pplus_px": int(pplus.sum())}
    }
    save_json(outdir/"device_inputs.json", device_inputs)

    metrics = {
        "Rp_nm": float(Rp_nm), "dRp_nm": float(dRp_nm), "channeling_factor": float(ch),
        "diffusion_nm": float(diffusion_nm), "activation_proxy": float(activation),
        "xj_nm": float(xj_nm), "Neff_proxy": float(Neff)
    }
    save_json(outdir/"metrics_stage4.json", metrics)
    np.save(outdir/"nplus_window.npy", nplus)
    np.save(outdir/"pplus_window.npy", pplus)

if __name__ == "__main__":
    main()
