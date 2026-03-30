
# stage5_metallization_cmp.py
"""Stage 5 — Metallization + CMP (Teaching Proxy)

Aligns with Metallization & CMP lecture topics:
  - PVD vs CVD/ALD barrier/liner conformality
  - Cu damascene: barrier/liner + seed + electroplating (ECD) + CMP
  - CMP issues: dishing (wide lines), erosion (dense patterns), selectivity

Representation:
  - 2D maps (um): depth_map_um (trenches/vias depth), and a binary 'features' map
  - We build a 'filled height' after plating, then apply CMP removal down to a stop height.

Inputs:
  - depth_map_um.npy from Stage 3 (or you can reuse Stage 2 depth assumptions)
  - optional openings.npy to define where trenches exist

Outputs:
  - metal_thickness_after_cmp_um.npy
  - cmp_topography_um.npy
  - metrics.json

Students can extend:
  - different CMP models (Preston equation; pressure + velocity dependence)
  - multi-step CMP (bulk + barrier + polish)
  - pattern-density dependent erosion more realistically
"""

from __future__ import annotations
import argparse, os
import numpy as np
import matplotlib.pyplot as plt
from common_utils import save_json

def local_density(binmap: np.ndarray, radius_px: int = 25) -> np.ndarray:
    """Compute local pattern density via box filter."""
    k = 2*radius_px+1
    p = np.pad(binmap.astype(np.float32), radius_px, mode="edge")
    # integral image for fast box sum
    ii = p.cumsum(0).cumsum(1)
    def boxsum(y0,x0,y1,x1):
        return ii[y1,x1]-ii[y0,x1]-ii[y1,x0]+ii[y0,x0]
    H,W = binmap.shape
    out = np.zeros((H,W), dtype=np.float32)
    for y in range(H):
        y0=y; y1=y+k
        for x in range(W):
            x0=x; x1=x+k
            out[y,x]=boxsum(y0,x0,y1,x1)
    out /= (k*k)
    return out

def simulate_damascene(depth_map_um: np.ndarray,
                       features: np.ndarray,
                       barrier_thickness_nm: float,
                       seed_thickness_nm: float,
                       overburden_um: float,
                       cmp_target_overburden_um: float,
                       dishing_strength: float,
                       erosion_strength: float) -> dict:
    """Return copper thickness after CMP and topography."""
    features = (features > 0.5).astype(np.uint8)
    depth = np.maximum(depth_map_um, 0.0).astype(np.float32)

    barrier_um = barrier_thickness_nm * 1e-3
    seed_um = seed_thickness_nm * 1e-3

    # Effective available trench depth after barrier/liner
    eff_depth = np.maximum(depth - 2*barrier_um, 0.0)

    # Plating fill: assume full fill plus overburden above field
    # height reference: field = 0, trench bottom = -eff_depth
    field = np.zeros_like(eff_depth)
    plated_height = field + overburden_um  # above field everywhere
    plated_height[features>0] = overburden_um  # still above; trench filled to field and beyond
    # after fill, copper exists in trenches (thickness = eff_depth) plus overburden
    # store copper thickness as (overburden + eff_depth in trenches)
    copper_thickness = np.full_like(eff_depth, overburden_um, dtype=np.float32)
    copper_thickness[features>0] += eff_depth[features>0]
    copper_thickness += seed_um  # seed adds everywhere

    # CMP removal: remove down to cmp_target_overburden above field
    remove = max(overburden_um - cmp_target_overburden_um, 0.0)
    copper_after = np.maximum(copper_thickness - remove, 0.0)

    # Pattern dependent effects:
    # - dishing: in wide areas, copper in trenches is reduced more
    # - erosion: in dense areas, field is reduced (over-polish)
    density = local_density(features, radius_px=18)  # 0..1

    # wide-area indicator: low density but feature present -> more dishing
    dishing = dishing_strength * (1.0 - density) * features
    copper_after = np.maximum(copper_after - dishing, 0.0)

    # erosion reduces copper on field in dense areas
    erosion = erosion_strength * density * (1 - features)
    copper_after = np.maximum(copper_after - erosion, 0.0)

    # Topography proxy: higher copper means higher surface after CMP
    topo = copper_after.copy()

    metrics = dict(
        barrier_thickness_nm=barrier_thickness_nm,
        seed_thickness_nm=seed_thickness_nm,
        overburden_um=overburden_um,
        cmp_target_overburden_um=cmp_target_overburden_um,
        mean_density=float(density.mean()),
        dishing_strength_um=dishing_strength,
        erosion_strength_um=erosion_strength,
        topo_range_um=float(topo.max()-topo.min()),
        copper_mean_um=float(copper_after.mean()),
    )
    return dict(copper_after_um=copper_after, topo_um=topo, density=density, metrics=metrics)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth_map", required=True, help="depth_map_um.npy from Stage 3")
    ap.add_argument("--features", required=True, help="etched_openings.npy (or openings) as feature map")
    ap.add_argument("--outdir", default="out_stage5_metallization_cmp")

    ap.add_argument("--barrier_nm", type=float, default=10.0)
    ap.add_argument("--seed_nm", type=float, default=50.0)

    ap.add_argument("--overburden_um", type=float, default=0.8)
    ap.add_argument("--cmp_target_overburden_um", type=float, default=0.05)

    ap.add_argument("--dishing_strength_um", type=float, default=0.15)
    ap.add_argument("--erosion_strength_um", type=float, default=0.08)

    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    depth = np.load(args.depth_map)
    feat = np.load(args.features)
    out = simulate_damascene(depth, feat,
                             barrier_thickness_nm=args.barrier_nm,
                             seed_thickness_nm=args.seed_nm,
                             overburden_um=args.overburden_um,
                             cmp_target_overburden_um=args.cmp_target_overburden_um,
                             dishing_strength=args.dishing_strength_um,
                             erosion_strength=args.erosion_strength_um)

    np.save(os.path.join(args.outdir, "metal_thickness_after_cmp_um.npy"), out["copper_after_um"])
    np.save(os.path.join(args.outdir, "cmp_topography_um.npy"), out["topo_um"])
    np.save(os.path.join(args.outdir, "pattern_density.npy"), out["density"])
    save_json(os.path.join(args.outdir, "metrics.json"), out["metrics"])

    def imsave(arr, name, title):
        plt.figure(figsize=(5,4))
        plt.imshow(arr, origin="lower")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(os.path.join(args.outdir, name), dpi=200)
        plt.close()

    imsave(out["density"], "pattern_density.png", "Local pattern density")
    imsave(out["copper_after_um"], "copper_after_cmp.png", "Cu thickness after CMP (um)")
    imsave(out["topo_um"], "cmp_topography.png", "CMP topography proxy (um)")

    print("Stage 5 finished. Outputs:", args.outdir)
    print("Topography range (um):", out["metrics"]["topo_range_um"])

if __name__ == "__main__":
    main()
