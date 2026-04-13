
# stage3_cvd.py
"""Stage 3 — CVD / Dielectric Thin Films (Teaching Proxy)

This stage turns an etched pattern into a deposited dielectric profile.

Lecture-aligned concepts we expose as knobs:
  - Conformality / step coverage (high for O3-TEOS, ALD; moderate PECVD; low PVD)
  - Two CVD regions:
      * surface-reaction-limited (more sensitive to temperature)
      * mass-transport-limited (less sensitive; common for uniformity)
  - Gap fill challenges: high aspect ratio trenches/vias
  - HDP-CVD idea: in-situ dep/etch/dep (simultaneous sputter + deposition) to avoid voids

Simplifying assumptions:
  - We represent topography as a 2D "depth map" (no full 3D).
  - Deposition grows thickness on exposed surfaces; we approximate via repeated dilation.
  - HDP-CVD is approximated as: (deposit) then (directional sputter/etch of corners) then (deposit)

Inputs:
  - etched_openings.npy from Stage 2 (1=open etched region)
  - params (thickness, conformality, HDP cycles)

Outputs:
  - dielectric_thickness_map.npy  (thickness on top, in um)
  - gap_fill_void_map.npy         (1=void risk areas)
  - summary.json

Students can extend:
  - add temperature dependence (Arrhenius) in surface-reaction-limited regime
  - implement more accurate ray/angle deposition for step coverage
  - multi-layer stacks (oxide + nitride + ARC, etc.)

"""

from __future__ import annotations
import argparse, os
import numpy as np
import matplotlib.pyplot as plt
from common_utils import save_json


def _dilate(binmap: np.ndarray, steps: int) -> np.ndarray:
    cur = binmap.astype(np.uint8)
    for _ in range(max(0, steps)):
        p = np.pad(cur, 1, mode="edge")
        cur = np.maximum.reduce([
            p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:],
            p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]
        ]).astype(np.uint8)
    return cur


def simulate_cvd_gapfill(openings: np.ndarray,
                         pixel_um: float,
                         trench_depth_um: float,
                         target_thickness_um: float,
                         conformality: float,
                         regime: str,
                         temperature_C: float,
                         hdp_cycles: int = 0,
                         hdp_sputter_frac: float = 0.25) -> dict:
    """Return dielectric thickness map and a void-risk map.

    conformality ∈ [0,1]: 1 => perfectly conformal (ALD-like), 0 => purely top deposition
    regime: 'mass_transport' or 'surface_reaction'
    """
    openings = (openings > 0.5).astype(np.uint8)

    # toy temperature sensitivity
    if regime == "surface_reaction":
        # higher temperature increases rate
        temp_scale = np.exp((temperature_C - 400.0) / 250.0)
    else:
        # mass transport limited -> less sensitive
        temp_scale = 1.0 + 0.2 * (temperature_C - 400.0) / 400.0
    temp_scale = float(np.clip(temp_scale, 0.5, 2.0))

    # represent etched trench as a depth map (um)
    depth = trench_depth_um * openings.astype(np.float32)

    # deposition thickness increments in pixels
    total_thick_um = target_thickness_um * temp_scale
    steps_total = int(round(total_thick_um / max(pixel_um, 1e-9)))
    steps_total = max(1, steps_total)

    # split into conformal and top components
    steps_conformal = int(round(conformality * steps_total))
    steps_top = steps_total - steps_conformal

    # Start with empty dielectric in openings
    filled = np.zeros_like(openings, dtype=np.uint8)  # 1=filled region (dielectric)

    # Conformal coat: grows inward from trench sidewalls/bottom approximated by dilating solid region
    # We model dielectric occupation by expanding "solid" (outside openings) into openings
    solid = 1 - openings
    coat = _dilate(solid, steps_conformal)
    # dielectric exists where coat has invaded openings
    filled = np.maximum(filled, (coat & openings))

    # Top deposition: deposits from top, tends to pinch-off at entrance -> void risk.
    # We approximate by dilating the opening *edges* (entrance closure) for steps_top.
    if steps_top > 0:
        # entrance closure: shrink openings by erosion-like steps, then mark closed areas as filled at the top.
        cur_open = openings.copy()
        for _ in range(steps_top):
            p = np.pad(cur_open, 1, mode="edge")
            neigh_min = np.minimum.reduce([
                p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:],
                p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]
            ])
            cur_open = neigh_min.astype(np.uint8)
        # the closed region corresponds to (openings - cur_open)
        closed = (openings & (1 - cur_open)).astype(np.uint8)
        filled = np.maximum(filled, closed)

    # HDP cycles: alternate deposit and sputter-etch to reduce voids at corners
    # We approximate by removing a fraction of 'filled' near corners, then adding conformal again.
    for _ in range(max(0, hdp_cycles)):
        # sputter removes dielectric preferentially at corners: take edge map of filled inside openings
        edges = filled.copy()
        p = np.pad(filled, 1, mode="edge")
        neigh_min = np.minimum.reduce([
            p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:],
            p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]
        ])
        edges = (filled & (1 - neigh_min)).astype(np.uint8)
        remove = (np.random.RandomState(0).rand(*edges.shape) < hdp_sputter_frac).astype(np.uint8) * edges
        filled = (filled & (1 - remove)).astype(np.uint8)

        # re-deposit conformal
        coat2 = _dilate(1 - openings, max(1, steps_conformal // max(1, hdp_cycles)))
        filled = np.maximum(filled, (coat2 & openings))

    # Void risk: openings that remain unfilled after deposition
    void = (openings & (1 - filled)).astype(np.uint8)

    thickness_map_um = (filled.astype(np.float32) * total_thick_um)

    summary = dict(
        pixel_um=pixel_um,
        trench_depth_um=trench_depth_um,
        target_thickness_um=target_thickness_um,
        effective_thickness_um=total_thick_um,
        conformality=conformality,
        regime=regime,
        temperature_C=temperature_C,
        hdp_cycles=hdp_cycles,
        void_fraction=float(void.mean()),
    )

    return dict(thickness_map_um=thickness_map_um, void_map=void.astype(np.float32), depth_map_um=depth, summary=summary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--openings", required=True, help="etched_openings.npy from Stage 2")
    ap.add_argument("--outdir", default="out_stage3_cvd")
    ap.add_argument("--pixel_um", type=float, default=0.02)

    ap.add_argument("--trench_depth_um", type=float, default=0.3)
    ap.add_argument("--target_thickness_um", type=float, default=0.5)
    ap.add_argument("--conformality", type=float, default=0.8, help="0..1")
    ap.add_argument("--regime", choices=["mass_transport","surface_reaction"], default="mass_transport")
    ap.add_argument("--temperature_C", type=float, default=400.0)

    ap.add_argument("--hdp_cycles", type=int, default=0)
    ap.add_argument("--hdp_sputter_frac", type=float, default=0.25)

    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    openings = np.load(args.openings)
    out = simulate_cvd_gapfill(openings, args.pixel_um, args.trench_depth_um, args.target_thickness_um,
                               args.conformality, args.regime, args.temperature_C,
                               hdp_cycles=args.hdp_cycles, hdp_sputter_frac=args.hdp_sputter_frac)

    np.save(os.path.join(args.outdir, "dielectric_thickness_map_um.npy"), out["thickness_map_um"])
    np.save(os.path.join(args.outdir, "void_map.npy"), out["void_map"])
    np.save(os.path.join(args.outdir, "depth_map_um.npy"), out["depth_map_um"])
    save_json(os.path.join(args.outdir, "summary.json"), out["summary"])

    def imsave(arr, name, title):
        plt.figure(figsize=(5,4))
        plt.imshow(arr, origin="lower", aspect="auto")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(os.path.join(args.outdir, name), dpi=200)
        plt.close()

    imsave(out["depth_map_um"], "depth_map.png", "Trench depth (um)")
    imsave(out["thickness_map_um"], "dielectric_thickness.png", "Dielectric thickness (um)")
    imsave(out["void_map"], "void_risk.png", "Void risk map (1=void)")

    print("Stage 3 (CVD) finished. Outputs:", args.outdir)

if __name__ == "__main__":
    main()
