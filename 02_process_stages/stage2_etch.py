
# stage2_etch.py
"""Stage 2 — Etch (Resist -> Etched Pattern + Simple Profile Metrics)

What this stage models (teaching proxies):
1) Anisotropy control:
   - Low pressure + higher ion energy -> more anisotropic (vertical) profiles
   - Higher pressure -> more isotropic / tapered

2) Loading effects (from the lecture):
   - Macro-loading: overall open-area fraction changes the available etchant
   - Micro-loading: smaller openings etch slower (transport limitation)

3) Main-etch + over-etch:
   - Main etch removes most of the film
   - Over etch clears leftover due to thickness + rate non-uniformity
   - Selectivity in over-etch controls substrate loss

Inputs:
  - A 2D developed resist map (.npy), with values 0/1 (or float in [0,1]).
    1 = resist remains (protects); 0 = open

Outputs:
  - A 2D etched-openings bitmap (1=open etched area)
  - A 2D silicon-remaining bitmap (1=protected / remains)
  - JSON summary with:
      open_area, effective_etch_rate, anisotropy_index, min_selectivity_req, etc.

Students can extend:
  - feature-size extraction more accurately
  - spatially varying plasma parameters across wafer
  - add sidewall passivation / polymer deposition mechanisms (blocking vs damaging)

"""

from __future__ import annotations
import argparse, os, json
import numpy as np
import matplotlib.pyplot as plt

from common_utils import ensure_binary, save_json, local_feature_size
from plasma_basics_utils import mean_free_path, ion_energy_eV, ion_flux_rel


def effective_etch_rate_Apm(base_rate_Apm: float,
                           open_area: float,
                           feature_size_um: np.ndarray,
                           pressure_mTorr: float,
                           rf_power_W: float,
                           magnetic_field_mT: float,
                           micro_loading_strength: float = 0.35,
                           macro_loading_strength: float = 0.25) -> np.ndarray:
    """Return a per-pixel etch rate map (Å/min) inside openings.

    - Macro-loading: if open area is large, etchant per unit open area decreases.
    - Micro-loading: small feature size etches slower.
    - Plasma knobs: ion flux and ion energy affect the overall rate.

    Note: This returns rate for the etched material (e.g., poly/oxide/silicon),
    but we use it as a scalar proxy here.
    """
    # macro: open_area ∈ (0,1]
    macro = 1.0 / (1.0 + macro_loading_strength * (open_area / max(1e-6, 0.2)))
    # micro: smaller features -> lower rate
    # normalize feature size by a reference 0.5 um
    ref = 0.5
    micro = (feature_size_um / ref) ** (1.0)  # can be changed by students
    micro = np.clip(micro, 0.15, 2.5)
    micro = 1.0 - micro_loading_strength * (1.0 / micro - 1.0)  # slow down when <ref
    micro = np.clip(micro, 0.1, 2.0)

    # plasma scaling
    E = ion_energy_eV(rf_power_W, pressure_mTorr)
    F = ion_flux_rel(magnetic_field_mT, rf_power_W)
    plasma = (0.6 + 0.02 * E) * F  # tunable proxy

    return base_rate_Apm * macro * micro * plasma


def anisotropy_index(pressure_mTorr: float, rf_power_W: float) -> float:
    """Return anisotropy index in [0,1]. 1=highly anisotropic."""
    # lower pressure -> longer MFP -> less scattering -> more anisotropic
    mfp = mean_free_path(300.0, pressure_mTorr)  # meters
    # map MFP to [0,1] with a soft saturation
    mfp_um = mfp * 1e6
    a_mfp = mfp_um / (mfp_um + 20.0)  # 20 um sets transition
    # higher power tends to increase ion-driven directionality
    a_pow = np.sqrt(max(rf_power_W, 0.0)) / (np.sqrt(max(rf_power_W, 0.0)) + 10.0)
    return float(np.clip(0.15 + 0.65 * a_mfp + 0.2 * a_pow, 0.0, 1.0))


def min_selectivity_for_overetch(film_thickness_A: float,
                                thickness_nonuni_frac: float,
                                etch_rate_nonuni_frac: float,
                                max_allowed_substrate_loss_A: float) -> float:
    """Compute minimum film-to-substrate selectivity during over-etch.

    Matches the lecture inequality: S > Δd / Δd'
    where Δd is the worst-case remaining film due to non-uniformities,
    and Δd' is allowed substrate loss.
    """
    # worst-case leftover after timed main etch
    # simple bound: film thickness uncertainty + rate uncertainty
    leftover = film_thickness_A * (thickness_nonuni_frac + etch_rate_nonuni_frac)
    return float(leftover / max(max_allowed_substrate_loss_A, 1e-9))


def run(resist: np.ndarray,
        pixel_um: float,
        base_rate_Apm: float,
        film_thickness_A: float,
        pressure_mTorr: float,
        rf_power_W: float,
        magnetic_field_mT: float,
        thickness_nonuni_frac: float,
        etch_rate_nonuni_frac: float,
        max_substrate_loss_A: float,
        overetch_time_factor: float = 1.15) -> dict:

    resist_bin = ensure_binary(resist, thr=0.5)
    openings = (resist_bin == 0).astype(np.float32)

    open_area = float(openings.mean())
    # feature size estimate (um) inside openings
    fs = local_feature_size(openings, pixel_um=pixel_um)  # um

    rate_map = effective_etch_rate_Apm(base_rate_Apm, open_area, fs,
                                       pressure_mTorr, rf_power_W, magnetic_field_mT)

    # Main etch time: target nominal thickness removal at nominal rate
    # Use average rate in openings to determine time
    avg_rate = float(np.mean(rate_map[openings > 0])) if open_area > 0 else base_rate_Apm
    main_time_min = film_thickness_A / max(avg_rate, 1e-6)

    # Over-etch time: factor * (worst-case leftover / avg_rate)
    leftover = film_thickness_A * (thickness_nonui_frac := thickness_nonuni_frac)  # alias for readability
    # include rate nonuniformity as well
    leftover += film_thickness_A * etch_rate_nonuni_frac
    over_time_min = overetch_time_factor * (leftover / max(avg_rate, 1e-6))

    # Toy profile: anisotropy controls lateral bias (undercut) amount
    A = anisotropy_index(pressure_mTorr, rf_power_W)
    # lateral bias (um): more isotropic -> more undercut
    lateral_bias_um = (1.0 - A) * 0.25  # 250 nm max default; students can modify

    # Convert lateral bias to pixels and apply dilation to represent undercut/opening growth
    bias_px = int(round(lateral_bias_um / max(pixel_um, 1e-9)))
    etched_openings = openings.copy()
    if bias_px > 0:
        # simple dilation using convolution-like repeated neighborhood max
        for _ in range(bias_px):
            p = np.pad(etched_openings, 1, mode="edge")
            neigh = np.maximum.reduce([
                p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:],
                p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]
            ])
            etched_openings = neigh

    silicon_remaining = 1.0 - etched_openings

    min_sel = min_selectivity_for_overetch(
        film_thickness_A, thickness_nonuni_frac, etch_rate_nonuni_frac, max_substrate_loss_A
    )

    summary = dict(
        open_area=open_area,
        pixel_um=pixel_um,
        base_rate_Apm=base_rate_Apm,
        avg_rate_Apm=avg_rate,
        film_thickness_A=film_thickness_A,
        main_time_min=main_time_min,
        overetch_time_min=over_time_min,
        anisotropy_index=A,
        pressure_mTorr=pressure_mTorr,
        rf_power_W=rf_power_W,
        magnetic_field_mT=magnetic_field_mT,
        lateral_bias_um=lateral_bias_um,
        min_selectivity_req=min_sel,
    )

    return dict(
        etched_openings=etched_openings.astype(np.float32),
        silicon_remaining=silicon_remaining.astype(np.float32),
        rate_map_Apm=rate_map.astype(np.float32),
        feature_size_um=fs.astype(np.float32),
        summary=summary,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resist", required=True, help="Input resist .npy (2D array)")
    ap.add_argument("--outdir", default="out_stage2", help="Output directory")
    ap.add_argument("--pixel_um", type=float, default=0.02, help="Pixel size (um)")

    # Etch recipe knobs (simplified)
    ap.add_argument("--base_rate_Apm", type=float, default=5000.0, help="Base etch rate (Å/min)")
    ap.add_argument("--film_thickness_A", type=float, default=3000.0, help="Film thickness to clear (Å)")
    ap.add_argument("--pressure_mTorr", type=float, default=15.0)
    ap.add_argument("--rf_power_W", type=float, default=400.0)
    ap.add_argument("--magnetic_field_mT", type=float, default=50.0)

    # Non-uniformities and selectivity target
    ap.add_argument("--thickness_nonuni_frac", type=float, default=0.015, help="e.g., 0.015=1.5%")
    ap.add_argument("--etch_rate_nonuni_frac", type=float, default=0.05, help="e.g., 0.05=5%")
    ap.add_argument("--max_substrate_loss_A", type=float, default=5.0, help="Allowed substrate loss during overetch (Å)")

    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    resist = np.load(args.resist)
    out = run(resist=resist,
              pixel_um=args.pixel_um,
              base_rate_Apm=args.base_rate_Apm,
              film_thickness_A=args.film_thickness_A,
              pressure_mTorr=args.pressure_mTorr,
              rf_power_W=args.rf_power_W,
              magnetic_field_mT=args.magnetic_field_mT,
              thickness_nonuni_frac=args.thickness_nonuni_frac,
              etch_rate_nonuni_frac=args.etch_rate_nonuni_frac,
              max_substrate_loss_A=args.max_substrate_loss_A)

    np.save(os.path.join(args.outdir, "etched_openings.npy"), out["etched_openings"])
    np.save(os.path.join(args.outdir, "silicon_remaining.npy"), out["silicon_remaining"])
    np.save(os.path.join(args.outdir, "rate_map_Apm.npy"), out["rate_map_Apm"])
    np.save(os.path.join(args.outdir, "feature_size_um.npy"), out["feature_size_um"])
    save_json(os.path.join(args.outdir, "summary.json"), out["summary"])

    def imsave(arr, name, title):
        plt.figure(figsize=(5,4))
        plt.imshow(arr, origin="lower", aspect="auto")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(os.path.join(args.outdir, name), dpi=200)
        plt.close()

    imsave((ensure_binary(resist, 0.5)==0).astype(float), "openings.png", "Openings (1=open)")
    imsave(out["etched_openings"], "etched_openings.png", "Etched openings (after bias)")
    imsave(out["rate_map_Apm"], "etch_rate_map.png", "Etch rate map (Å/min)")
    imsave(out["silicon_remaining"], "silicon_remaining.png", "Silicon remaining (1=left)")

    print("Stage 2 finished. Outputs:", args.outdir)
    print("Min selectivity required (over-etch):", out["summary"]["min_selectivity_req"])

if __name__ == "__main__":
    main()
