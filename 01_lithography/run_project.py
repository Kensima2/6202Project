"""
run_project.py
Official project runner: loads config, sweeps dose/defocus, computes CD and window metrics,
and saves key figures. Students should run this for reproducible submission.

Usage:
    python run_project.py --config config.json
"""

from __future__ import annotations
import argparse, json, os, shutil
import numpy as np
import matplotlib.pyplot as plt

# Import baseline functions by loading from the baseline file
import photolithography_baseline as litho
import spin_coating as spin
import opc
import smo
import mask_import
from PIL import Image
from metrics import window_area


def reset_output_dir(outdir: str) -> None:
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)

def main(cfg_path: str, outdir_override: str | None = None):
    cfg = json.load(open(cfg_path, "r", encoding="utf-8"))

    # Apply config to baseline globals (simple approach for teaching)
    litho.TARGET_CD_NM = float(cfg["target_cd_nm"])
    litho.CD_TOL_NM = float(cfg["cd_tol_nm"])

    litho.PATTERN = cfg["pattern"]
    litho.PITCH_NM = float(cfg["pitch_nm"])
    litho.DUTY_CYCLE = float(cfg["duty_cycle"])
    litho.MASK_TONE = cfg["mask_tone"]

    litho.RESIST_TYPE = cfg["resist_type"]
    litho.DEVELOP_THRESHOLD = float(cfg["develop_threshold"])
    litho.PEB_BLUR_NM = float(cfg["peb_blur_nm"])

    litho.WAVELENGTH_NM = float(cfg["wavelength_nm"])
    litho.NA = float(cfg["na"])
    litho.SIGMA_IN = float(cfg["sigma_in"])
    litho.SIGMA_OUT = float(cfg["sigma_out"])
    litho.N_SOURCE_SAMPLES = int(cfg["n_source_samples"])

    # --- RET (PSM / OPC / SMO) config ---
    ret = cfg.get("ret", {})

    # PSM settings (affect demo + sweep)
    psm_cfg = ret.get("psm", {})
    litho.PSM_ENABLED = bool(psm_cfg.get("enabled", False))
    litho.PSM_PHASE_RAD = float(psm_cfg.get("phase_rad", np.pi))
    litho.PSM_REGION = str(psm_cfg.get("region", "spaces"))

    # OPC settings (affect demo + sweep)
    opc_cfg = ret.get("opc", {})
    litho.OPC_MASK_BIAS_NM = float(opc_cfg.get("mask_bias_nm", 0.0)) if bool(opc_cfg.get("enabled", False)) else 0.0

    # (SMO is run as an extra analysis block later; it should NOT change the main sweep unless students choose to.)

    ds = cfg["dose_sweep"]
    fs = cfg["defocus_sweep_nm"]
    litho.DOSE_LIST = np.linspace(ds["start"], ds["stop"], ds["num"])
    litho.DEFOCUS_LIST_NM = np.linspace(fs["start"], fs["stop"], fs["num"])

    litho.DX_NM = float(cfg["dx_nm"])
    litho.SIM_PITCHES = int(cfg["sim_pitches"])

    if outdir_override is not None:
        outdir = outdir_override
    else:
        outdir = os.path.join("outputs", "stage1_poly_litho")

    reset_output_dir(outdir)

    # # 0.2) Optional: KLayout mask pipeline (PNG -> NPY -> 2D simulation) [COMMENTED OUT - using 1D only]
    # km = cfg.get("klayout_mask", {})
    # if bool(km.get("enabled", False)) and bool(km.get("auto_convert_on_run", True)):
    #     png_path = str(km.get("png_path", "masks/klayout_mask.png"))
    #     out_npy = str(km.get("out_npy_path", "masks/custom_mask.npy"))
    #     if os.path.exists(png_path):
    #         img = np.array(Image.open(png_path).convert("RGBA"))[:, :, :3]
    #         m = mask_import.png_to_mask_npy(
    #             img,
    #             out_n=int(km.get("size", 512)),
    #             threshold=float(km.get("threshold", 0.5)),
    #             invert=bool(km.get("invert", False)),
    #         )
    #         os.makedirs(os.path.dirname(out_npy) or ".", exist_ok=True)
    #         np.save(out_npy, m)
    #         # Inject into baseline for 2D pattern runs only (keeps 1D intact)
    #         if cfg.get("pattern", "line_space_1d") != "line_space_1d":
    #             litho.CUSTOM_MASK_PATH = out_npy
    #         # Export a quick visualization
    #         plt.figure()
    #         plt.imshow(m, origin="lower")
    #         plt.title("Imported KLayout mask (binary)")
    #         plt.tight_layout()
    #         plt.savefig(os.path.join(outdir, "klayout_mask_import_preview.png"), dpi=200)
    #         plt.close()
    #     else:
    #         print(f"[WARN] KLayout PNG not found: {png_path}. Disable klayout_mask or provide the file.")

    # 0.5) Spin-coating (photoresist thickness) simulation + coupling to litho
    # This connects Photolithography II (process flow) to litho window: thickness -> PEB/threshold sensitivity.
    spin_cfg = cfg.get("spin_coating", {})
    coup = cfg.get("resist_coupling", {})

    if spin_cfg.get("enabled", False):
        h0_nm = spin.thickness_meyerhofer_nm(
            viscosity_pa_s=spin_cfg.get("viscosity_pa_s", 0.03),
            density_kg_m3=spin_cfg.get("density_kg_m3", 1000),
            solids_fraction=spin_cfg.get("solids_fraction", 0.25),
            rpm=spin_cfg.get("rpm", 3000),
            spin_time_s=spin_cfg.get("spin_time_s", 30),
            k=spin_cfg.get("k", 1.0),
        )

        # Export spin thickness vs rpm curve (for education)
        rpms = np.array([1000, 1500, 2000, 2500, 3000, 3500, 4000], dtype=float)
        hs = np.array([spin.thickness_meyerhofer_nm(
            viscosity_pa_s=spin_cfg.get("viscosity_pa_s", 0.03),
            density_kg_m3=spin_cfg.get("density_kg_m3", 1000),
            solids_fraction=spin_cfg.get("solids_fraction", 0.25),
            rpm=r, spin_time_s=spin_cfg.get("spin_time_s", 30),
            k=spin_cfg.get("k", 1.0),
        ) for r in rpms])

        plt.figure()
        plt.plot(rpms, hs)
        plt.xlabel("Spin speed (rpm)")
        plt.ylabel("Thickness (nm)")
        plt.title("Spin coating thickness vs rpm (teaching model)")
        plt.grid(True, which="both")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "spin_thickness_vs_rpm.png"), dpi=200)
        plt.close()

        # Export radial profile
        Rw = float(spin_cfg.get("wafer_radius_mm", 75.0))
        rr = np.linspace(0, Rw, 301)
        prof = spin.radial_thickness_profile_nm(
            h0_nm=h0_nm, r_mm=rr, wafer_radius_mm=Rw,
            nonuniformity_pct=spin_cfg.get("nonuniformity_pct", 2.0),
            edge_bead_nm=spin_cfg.get("edge_bead_nm", 80.0),
            edge_bead_width_mm=spin_cfg.get("edge_bead_width_mm", 2.0),
        )
        plt.figure()
        plt.plot(rr, prof)
        plt.xlabel("Radius (mm)")
        plt.ylabel("Thickness (nm)")
        plt.title(f"Spin coating radial thickness (h0≈{h0_nm:.1f} nm)")
        plt.grid(True, which="both")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "spin_thickness_radial_profile.png"), dpi=200)
        plt.close()

        # Export 2D thickness map (for visualization)
        Xmm, Ymm, Hnm = spin.thickness_map_nm(
            h0_nm=h0_nm,
            wafer_radius_mm=Rw,
            grid_n=251,
            nonuniformity_pct=spin_cfg.get("nonuniformity_pct", 2.0),
            edge_bead_nm=spin_cfg.get("edge_bead_nm", 80.0),
            edge_bead_width_mm=spin_cfg.get("edge_bead_width_mm", 2.0),
        )
        plt.figure()
        plt.imshow(Hnm, origin="lower", extent=[-Rw, Rw, -Rw, Rw])
        plt.xlabel("x (mm)"); plt.ylabel("y (mm)")
        plt.title("Spin coating thickness map (nm)")
        plt.colorbar(label="nm")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "spin_thickness_map.png"), dpi=200)
        plt.close()

        # --- Couple thickness to litho knobs (teaching proxy, tunable) ---
        base_t = float(coup.get("base_thickness_nm", 300.0))
        power = float(coup.get("peb_blur_scale_power", 0.5))
        shift = float(coup.get("threshold_shift_per_100nm", 0.02))

        t_ratio = max(1e-6, h0_nm / max(1e-6, base_t))
        litho.PEB_BLUR_NM = float(litho.PEB_BLUR_NM) * (t_ratio ** power)
        litho.DEVELOP_THRESHOLD = float(litho.DEVELOP_THRESHOLD) + ((h0_nm - base_t) / 100.0) * shift

        # clamp threshold to [0,1]
        litho.DEVELOP_THRESHOLD = float(np.clip(litho.DEVELOP_THRESHOLD, 0.05, 0.95))

        # Record spin results into cfg for downstream metrics.json
        cfg["_spin_results"] = {"h0_nm": float(h0_nm), "t_ratio": float(t_ratio)}
    else:
        cfg["_spin_results"] = None


    # 1) Demo figures (1D + 2D)
    # We always export:
    #   - a 1D line/space demo
    #   - a 2D contact demo
    # so students can visually connect concepts across dimensions.

    _pattern_cfg = litho.PATTERN

    # ---- 1D demo (line/space) ----
    litho.PATTERN = "line_space_1d"
    r1 = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=1)
    x = r1["x_nm"]
    plt.figure()
    plt.plot(x, r1["mask"][0], label="Mask (binary)")
    plt.plot(x, r1["I"][0], label="Aerial image (norm)")
    plt.plot(x, r1["R"][0], label="Resist remain (binary)")
    plt.ylim(-0.2, 1.2)
    plt.xlabel("x (nm)")
    plt.title(f"Demo 1D (Line/Space) | CD≈{r1['cd_nm']:.1f} nm")
    plt.legend(); plt.grid(True, which="both")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "demo_1d_mask_image_resist.png"), dpi=200)
    plt.close()
    # ===== EXPORT RESIST FOR DOWNSTREAM ETCH =====
    # Use nominal 1D resist as process input
    resist_out = r1["R"].astype(np.float32)

    # For 1D, expand to 2D (etch expects 2D map)
    if resist_out.ndim == 2:
        pass
    elif resist_out.ndim == 1:
        resist_out = np.tile(resist_out[None, :], (resist_out.shape[0], 1))

    np.save(os.path.join(outdir, "resist.npy"), resist_out)
    # ============================================

    # # ---- 2D demo (contact) [COMMENTED OUT - using 1D only] ----
    # litho.PATTERN = "contact_2d"
    # r2 = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=1)
    # for name, img in [("mask", r2["mask"]), ("aerial", r2["I"]), ("resist", r2["R"])]:
    #     plt.figure()
    #     plt.imshow(img, origin="lower")
    #     if name == "resist":
    #         plt.title(f"Demo 2D (Contact) - {name} | CD(circle-eq)≈{r2['cd_nm']:.1f} nm")
    #     else:
    #         plt.title(f"Demo 2D (Contact) - {name}")
    #     plt.colorbar()
    #     plt.tight_layout()
    #     plt.savefig(os.path.join(outdir, f"demo_2d_{name}.png"), dpi=200)
    #     plt.close()

    # # Optional overlay: fitted circle on resist (2D contact) for visual inspection
    # if r2.get("cd_fit_nm") is not None:
    #     dx = float(r2["x_nm"][1] - r2["x_nm"][0])
    #     dy = dx  # square pixels in our setup
    #     cd_fit = float(r2["cd_fit_nm"])
    #     cx_nm, cy_nm = r2.get("circle_center_nm", [0.0, 0.0])
    #     r_nm = cd_fit / 2.0

    #     # Build local coordinate axes in nm for the image
    #     ny, nx = r2["R"].shape
    #     xs = (np.arange(nx) - nx/2.0) * dx
    #     ys = (np.arange(ny) - ny/2.0) * dy
    #     X, Y = np.meshgrid(xs, ys)

    #     # Circle mask for overlay
    #     circle = (X - cx_nm)**2 + (Y - cy_nm)**2
    #     plt.figure()
    #     plt.imshow(r2["R"], origin="lower")
    #     plt.contour(circle, levels=[r_nm**2], colors="w", linewidths=1.2)
    #     plt.title(f"Demo 2D Resist + Fitted Circle | CD_fit≈{cd_fit:.1f} nm, center=({cx_nm:.1f},{cy_nm:.1f}) nm")
    #     plt.tight_layout()
    #     plt.savefig(os.path.join(outdir, "demo_2d_resist_circlefit.png"), dpi=200)
    #     plt.close()
    litho.PATTERN = _pattern_cfg


    # 1.5) RET demonstrations (PSM / OPC) - side-by-side comparisons (optional)
    # These are designed so students can quickly see *what RET does* and then modify code creatively.

    # --- PSM comparison (1D) ---
    if ret.get("psm", {}).get("enabled", False):
        # Save current settings
        _psm_on = litho.PSM_ENABLED
        _bias = litho.OPC_MASK_BIAS_NM

        # Force 1D for this comparison plot
        _pattern_cfg2 = litho.PATTERN
        litho.PATTERN = "line_space_1d"

        # Baseline (no PSM)
        litho.PSM_ENABLED = False
        litho.OPC_MASK_BIAS_NM = 0.0
        r_base = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=10)

        # With PSM
        litho.PSM_ENABLED = True
        r_psm = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=10)

        x = r_base["x_nm"]
        plt.figure()
        plt.plot(x, r_base["I"][0], label="Aerial (baseline)")
        plt.plot(x, r_psm["I"][0], label="Aerial (PSM)")
        plt.xlabel("x (nm)"); plt.ylabel("Normalized intensity")
        plt.title("PSM demo (1D): aerial image comparison")
        plt.grid(True, which="both"); plt.legend(); plt.tight_layout()
        plt.savefig(os.path.join(outdir, "ret_psm_aerial_compare_1d.png"), dpi=200)
        plt.close()

        # Restore
        litho.PSM_ENABLED = _psm_on
        litho.OPC_MASK_BIAS_NM = _bias
        litho.PATTERN = _pattern_cfg2

    # --- OPC bias demo (1D): CD before/after bias ---
    if ret.get("opc", {}).get("enabled", False) and litho.PATTERN == "line_space_1d":
        _b = litho.OPC_MASK_BIAS_NM
        litho.OPC_MASK_BIAS_NM = 0.0
        r0 = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=11)
        litho.OPC_MASK_BIAS_NM = _b
        r1 = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=11)

        x = r0["x_nm"]
        plt.figure()
        plt.plot(x, r0["R"][0], label=f"Resist (no OPC) CD≈{r0['cd_nm']:.1f}nm")
        plt.plot(x, r1["R"][0], label=f"Resist (OPC bias={_b:.1f}nm) CD≈{r1['cd_nm']:.1f}nm")
        plt.xlabel("x (nm)"); plt.ylabel("Resist remain (binary)")
        plt.title("OPC demo (1D): developed resist (before/after)")
        plt.grid(True, which="both"); plt.legend(); plt.tight_layout()
        plt.savefig(os.path.join(outdir, "ret_opc_resist_compare_1d.png"), dpi=200)
        plt.close()

        litho.OPC_MASK_BIAS_NM = _b

    # # 1.6) SMO (source-mask optimization) demonstration (optional) [COMMENTED OUT - using 1D only]
    # smo_cfg = ret.get("smo", {})
    # if bool(smo_cfg.get("enabled", False)):
    #     sigma_out_list = np.array(smo_cfg.get("sigma_out_list", [0.3, 0.5, 0.7, 0.9]), dtype=float)
    #     bias_nm_list = np.array(smo_cfg.get("bias_nm_list", [-40, -20, 0, 20, 40]), dtype=float)
    #     sigma_in = float(smo_cfg.get("sigma_in", litho.SIGMA_IN))

    #     # define evaluator for window area with current cfg sweeps
    #     def eval_area(si, so, bias_nm):
    #         # set params
    #         litho.SIGMA_IN = float(si)
    #         litho.SIGMA_OUT = float(so)
    #         litho.OPC_MASK_BIAS_NM = float(bias_nm)

    #         # compute pass map quickly
    #         cds = np.zeros((len(litho.DEFOCUS_LIST_NM), len(litho.DOSE_LIST)), dtype=float)
    #         for ii, f in enumerate(litho.DEFOCUS_LIST_NM):
    #             for jj, d in enumerate(litho.DOSE_LIST):
    #                 cds[ii, jj] = litho.simulate_one(dose_rel=float(d), defocus_nm=float(f), seed=0)["cd_nm"]
    #         pass_map = np.abs(cds - litho.TARGET_CD_NM) <= litho.CD_TOL_NM
    #         # window area metric
    #         dd = float(litho.DOSE_LIST[1] - litho.DOSE_LIST[0])
    #         df = float(litho.DEFOCUS_LIST_NM[1] - litho.DEFOCUS_LIST_NM[0])
    #         return float(pass_map.sum()) * dd * df

    #     res = smo.grid_search_smo(eval_area, sigma_out_list=sigma_out_list, bias_nm_list=bias_nm_list, sigma_in=sigma_in)
    #     scores = res["scores"]

    #     plt.figure()
    #     plt.imshow(scores, origin="lower", aspect="auto",
    #                extent=[bias_nm_list.min(), bias_nm_list.max(), sigma_out_list.min(), sigma_out_list.max()])
    #     plt.xlabel("Mask bias (nm)")
    #     plt.ylabel("Sigma_out")
    #     plt.title(f"SMO demo: window area heatmap | best so={res['best_sigma_out']}, bias={res['best_bias_nm']}")
    #     plt.colorbar(label="Window area (dose·nm)")
    #     plt.tight_layout()
    #     plt.savefig(os.path.join(outdir, "ret_smo_window_area_heatmap.png"), dpi=200)
    #     plt.close()

    #     # restore to config settings after SMO demo
    #     litho.SIGMA_IN = float(cfg["sigma_in"])
    #     litho.SIGMA_OUT = float(cfg["sigma_out"])
    #     litho.OPC_MASK_BIAS_NM = float(opc_cfg.get("mask_bias_nm", 0.0)) if bool(opc_cfg.get("enabled", False)) else 0.0
    
    # 2) Process window sweep
    dose = litho.DOSE_LIST
    defocus = litho.DEFOCUS_LIST_NM
    cds = np.zeros((len(defocus), len(dose)), dtype=float)
    for i, f in enumerate(defocus):
        for j, d in enumerate(dose):
            cds[i, j] = litho.simulate_one(dose_rel=float(d), defocus_nm=float(f), seed=0)["cd_nm"]

    pass_map = np.abs(cds - litho.TARGET_CD_NM) <= litho.CD_TOL_NM
    area = window_area(pass_map, dose, defocus)

    D, F = np.meshgrid(dose, defocus)
    plt.figure()
    plt.contourf(D, F, pass_map.astype(int), levels=[-0.5, 0.5, 1.5])
    plt.xlabel("Relative Dose")
    plt.ylabel("Defocus (nm)")
    plt.title(f"Process Window (Area≈{area:.1f} dose·nm)")
    plt.colorbar(label="Pass(1)/Fail(0)")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "process_window.png"), dpi=200)
    plt.close()

    # 3) Slices
    f0 = int(np.argmin(np.abs(defocus - 0.0)))
    plt.figure()
    plt.plot(dose, cds[f0, :])
    plt.axhline(litho.TARGET_CD_NM + litho.CD_TOL_NM, linestyle="--")
    plt.axhline(litho.TARGET_CD_NM - litho.CD_TOL_NM, linestyle="--")
    plt.xlabel("Relative Dose"); plt.ylabel("CD (nm)")
    plt.title("CD vs Dose @ Defocus≈0")
    plt.grid(True, which="both"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "cd_vs_dose.png"), dpi=200)
    plt.close()

    d0 = int(np.argmin(np.abs(dose - 1.0)))
    plt.figure()
    plt.plot(defocus, cds[:, d0])
    plt.axhline(litho.TARGET_CD_NM + litho.CD_TOL_NM, linestyle="--")
    plt.axhline(litho.TARGET_CD_NM - litho.CD_TOL_NM, linestyle="--")
    plt.xlabel("Defocus (nm)"); plt.ylabel("CD (nm)")
    plt.title("CD vs Defocus @ Dose≈1.0")
    plt.grid(True, which="both"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "cd_vs_defocus.png"), dpi=200)
    plt.close()

    # Save metrics
    metrics = {
        "window_area_dose_nm": area,
        "target_cd_nm": litho.TARGET_CD_NM,
        "cd_tol_nm": litho.CD_TOL_NM,
        "pattern": litho.PATTERN,
        "wavelength_nm": litho.WAVELENGTH_NM,
        "na": litho.NA,
        "sigma_in": litho.SIGMA_IN,
        "sigma_out": litho.SIGMA_OUT,
        "peb_blur_nm": litho.PEB_BLUR_NM
    }

    # Extra contact (2D) metrics at the nominal center condition (dose0, defocus0) if available [COMMENTED OUT - using 1D only]
    # r_center = litho.simulate_one(dose_rel=float(cfg.get("dose0", 1.0)), defocus_nm=0.0, seed=2)
    # for k in ["cd_fit_nm", "cd_area_circle_nm", "circle_center_nm",
    #           "epe_mean_nm", "epe_std_nm", "epe_maxabs_nm",
    #           "nils2d_median_1_per_nm", "cdu_cd_mean_nm", "cdu_cd_std_nm"]:
    #     if k in r_center and r_center[k] is not None:
    #         metrics[k] = r_center[k]

    # Record spin-coating and coupled effective knobs (if enabled)
    if cfg.get("_spin_results") is not None:
        metrics["spin_h0_nm"] = cfg["_spin_results"]["h0_nm"]
        metrics["spin_t_ratio"] = cfg["_spin_results"]["t_ratio"]
        metrics["develop_threshold_eff"] = litho.DEVELOP_THRESHOLD
        metrics["peb_blur_eff_nm"] = litho.PEB_BLUR_NM

    with open(os.path.join(outdir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"[OK] Outputs saved to ./{outdir}")
    print(f"[Metric] Window area ≈ {area:.2f} (dose·nm)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--outdir", default=None, help="pipeline output dir (e.g. outputs/<run_name>/stage1_poly_litho)")
    args = ap.parse_args()
    main(args.config, args.outdir)

