#!/usr/bin/env python
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np

def save_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def local_density(mask: np.ndarray, win: int) -> np.ndarray:
    m = mask.astype(np.float32)
    H,W = m.shape
    pad = win//2
    mp = np.pad(m, ((pad,pad),(pad,pad)), mode="constant")
    ii = np.zeros((mp.shape[0] + 1, mp.shape[1] + 1), dtype=np.float32)
    ii[1:, 1:] = np.cumsum(np.cumsum(mp, axis=0), axis=1)

    def S(y0, x0, y1, x1):
        return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]

    out = np.zeros((H,W), dtype=np.float32)
    area = float(win*win)
    for y in range(H):
        y0=y; y1=y+win
        for x in range(W):
            x0=x; x1=x+win
            out[y,x]=S(y0,x0,y1,x1)/area
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cont_npy", required=True)
    ap.add_argument("--m1_npy", required=True)
    ap.add_argument("--v1_npy", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--overburden_nm", type=float, default=300.0)
    ap.add_argument("--target_overburden_nm", type=float, default=0.0)
    ap.add_argument("--pattern_density_window", type=int, default=31)
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    cont = np.load(args.cont_npy).astype(np.uint8)
    m1 = np.load(args.m1_npy).astype(np.uint8)
    v1 = np.load(args.v1_npy).astype(np.uint8)

    dens_m1 = local_density(m1, args.pattern_density_window)
    dens_v1 = local_density(v1, args.pattern_density_window)

    dishing = float((1.0 - dens_m1).mean() * 0.8)
    erosion = float(dens_m1.mean() * 0.9)

    removed = max(0.0, args.overburden_nm - args.target_overburden_nm)
    t_post = args.overburden_nm - removed * (0.6 + 0.2*erosion + 0.2*dishing)
    t_post = float(max(0.0, t_post))

    via_penalty = float(1.0 + 0.8*(1.0 - dens_v1.mean()))
    R_proxy = float(via_penalty * (1.0 / max(t_post, 1e-6)))

    metrics = {
        "m1_density_mean": float(dens_m1.mean()),
        "v1_density_mean": float(dens_v1.mean()),
        "dishing_proxy": dishing,
        "erosion_proxy": erosion,
        "t_post_cmp_nm_proxy": t_post,
        "R_interconnect_proxy": R_proxy,
        "areas": {"cont_px": int(cont.sum()), "m1_px": int(m1.sum()), "v1_px": int(v1.sum())}
    }
    save_json(outdir/"metrics_stage5.json", metrics)
    np.save(outdir/"density_m1.npy", dens_m1)
    np.save(outdir/"density_v1.npy", dens_v1)

if __name__ == "__main__":
    main()
