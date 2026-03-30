
# stage6_device.py
"""Stage 6 — Simplified Device Metrics (Teaching Proxy)

Goal: connect *process* knobs to *device* figures of merit in a lightweight way.

Uses:
  - Stage 2 (etch) summary: lateral_bias_um -> impacts Leff/CD
  - Stage 4 implant/thermal metrics: junction_depth, sheet_resistance, activation
  - Stage 5 metallization/CMP metrics: copper thickness -> interconnect resistance proxy

Outputs:
  - metrics.json: Vt_proxy, Ioff_proxy, Ron_proxy, interconnect_R_proxy

Students can extend:
  - replace proxies with more physics-based compact models
  - add Monte Carlo variability (CD sigma, dose sigma, CMP non-uniformity)
  - compare trade-offs (leakage vs Vt vs speed)
"""

from __future__ import annotations
import argparse, os
import numpy as np
from common_utils import load_json, save_json

def vt_proxy(Leff_nm: float, tox_nm: float, Na_proxy_cm3: float) -> float:
    # toy: shorter Leff increases Vt roll-off (lower Vt), higher Na increases Vt
    Vt0 = 0.45
    rolloff = -0.10 * (50.0 / max(Leff_nm, 10.0))
    doping = 0.08 * np.log10(max(Na_proxy_cm3, 1e14) / 1e15)
    tox = 0.03 * (tox_nm - 2.0)
    return float(Vt0 + rolloff + doping + tox)

def ioff_proxy(Vt: float, Leff_nm: float, temp_C: float = 25.0) -> float:
    # toy: exponential in -Vt and Leff; higher T increases leakage
    kT_scale = np.exp((temp_C - 25.0)/60.0)
    return float(kT_scale * np.exp(-Vt/0.12) * np.exp(-Leff_nm/35.0))

def ron_proxy(sheet_R_ohm_sq: float, Leff_nm: float, W_um: float = 1.0) -> float:
    # toy: channel resistance scales with Rs * (L/W)
    L_um = Leff_nm * 1e-3
    return float(sheet_R_ohm_sq * (L_um / max(W_um, 1e-3)))

def interconnect_R_proxy(cu_thickness_um: float, line_L_um: float = 100.0, line_W_um: float = 1.0) -> float:
    # toy: R ~ rho * L/(W*t); rho is fixed proxy
    rho = 1.7e-8  # ohm*m for Cu (approx)
    L = line_L_um * 1e-6
    W = line_W_um * 1e-6
    t = max(cu_thickness_um, 1e-6) * 1e-6
    return float(rho * L / (W * t))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="out_stage6_device")
    ap.add_argument("--etch_summary", required=True, help="Stage2 summary.json")
    ap.add_argument("--implant_metrics", required=True, help="Stage4 metrics.json")
    ap.add_argument("--cmp_metrics", required=True, help="Stage5 metrics.json")

    ap.add_argument("--cd_nom_nm", type=float, default=200.0, help="Nominal CD from litho (nm)")
    ap.add_argument("--tox_nm", type=float, default=2.0)
    ap.add_argument("--temp_C", type=float, default=25.0)
    ap.add_argument("--W_um", type=float, default=1.0)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    etch = load_json(args.etch_summary)
    imp = load_json(args.implant_metrics)
    cmpm = load_json(args.cmp_metrics)

    # Leff: nominal CD minus 2x lateral bias (etched opening grows)
    lateral_bias_nm = 1e3 * float(etch.get("lateral_bias_um", 0.0))
    Leff_nm = max(20.0, args.cd_nom_nm - 2.0 * lateral_bias_nm)

    Na_proxy = float(imp.get("peak_cm3", 1e18))
    Rs = float(imp.get("sheet_resistance_ohm_per_sq", 1e3))
    cu_mean = float(cmpm.get("copper_mean_um", 0.2))

    Vt = vt_proxy(Leff_nm, args.tox_nm, Na_proxy)
    Ioff = ioff_proxy(Vt, Leff_nm, args.temp_C)
    Ron = ron_proxy(Rs, Leff_nm, W_um=args.W_um)
    Rint = interconnect_R_proxy(cu_mean)

    out = dict(
        Leff_nm=Leff_nm,
        lateral_bias_nm=lateral_bias_nm,
        tox_nm=args.tox_nm,
        Na_proxy_peak_cm3=Na_proxy,
        sheet_R_ohm_per_sq=Rs,
        cu_mean_um=cu_mean,
        Vt_proxy_V=Vt,
        Ioff_proxy_A=Ioff,
        Ron_proxy_ohm=Ron,
        interconnect_R_proxy_ohm=Rint,
    )
    save_json(os.path.join(args.outdir, "metrics.json"), out)
    print("Stage 6 finished. Outputs:", args.outdir)
    print("Vt:", Vt, "Ioff:", Ioff, "Ron:", Ron, "Rint:", Rint)

if __name__ == "__main__":
    main()
