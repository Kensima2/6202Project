
# litho_stage_basic.py
from __future__ import annotations
import os, json
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

import photolithography_baseline as litho
import mask_import

def load_config(cfg_path="config.json"):
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def setup_litho_parameters(cfg):
    litho.PATTERN = cfg.get("pattern", "contact_2d")
    litho.LAMBDA_NM = cfg.get("wavelength_nm", litho.LAMBDA_NM)
    litho.NA = cfg.get("na", litho.NA)
    litho.SIGMA_IN = cfg.get("sigma_in", litho.SIGMA_IN)
    litho.SIGMA_OUT = cfg.get("sigma_out", litho.SIGMA_OUT)
    litho.N_SOURCE_SAMPLES = cfg.get("n_source_samples", litho.N_SOURCE_SAMPLES)
    litho.DOSE_LIST = np.array(cfg.get("dose_list", litho.DOSE_LIST), dtype=float)
    litho.DEFOCUS_LIST_NM = np.array(cfg.get("defocus_list_nm", litho.DEFOCUS_LIST_NM), dtype=float)
    litho.TARGET_CD_NM = cfg.get("target_cd_nm", litho.TARGET_CD_NM)
    litho.CD_TOL_NM = cfg.get("cd_tol_nm", litho.CD_TOL_NM)

def load_klayout_mask(cfg, outdir):
    km = cfg.get("klayout_mask", {})
    if not km.get("enabled", False):
        return
    png_path = km.get("png_path", "masks/klayout_mask.png")
    img = np.array(Image.open(png_path).convert("RGB"))
    mask = mask_import.png_to_mask_npy(
        img,
        out_n=km.get("size", 512),
        threshold=km.get("threshold", 0.5),
        invert=km.get("invert", False)
    )
    os.makedirs("masks", exist_ok=True)
    npy_path = km.get("out_npy_path", "masks/custom_mask.npy")
    np.save(npy_path, mask)
    litho.CUSTOM_MASK_PATH = npy_path
    plt.figure()
    plt.imshow(mask, origin="lower")
    plt.title("Imported KLayout Mask")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "klayout_mask_preview.png"), dpi=200)
    plt.close()

def run_litho_sweep(outdir):
    cds = np.zeros((len(litho.DEFOCUS_LIST_NM), len(litho.DOSE_LIST)))
    for i, f in enumerate(litho.DEFOCUS_LIST_NM):
        for j, d in enumerate(litho.DOSE_LIST):
            res = litho.simulate_one(dose_rel=d, defocus_nm=f, seed=0)
            cds[i, j] = res.get("cd_nm", np.nan)
    pass_map = np.abs(cds - litho.TARGET_CD_NM) <= litho.CD_TOL_NM
    dd = litho.DOSE_LIST[1] - litho.DOSE_LIST[0]
    df = litho.DEFOCUS_LIST_NM[1] - litho.DEFOCUS_LIST_NM[0]
    window_area = float(pass_map.sum()) * dd * df
    plt.figure()
    plt.imshow(pass_map, origin="lower", aspect="auto")
    plt.title("Process Window")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "process_window.png"), dpi=200)
    plt.close()
    metrics = {
        "window_area_proxy": window_area,
        "cd_mean_nm": float(np.mean(cds)),
        "cd_std_nm": float(np.std(cds)),
    }
    np.save(os.path.join(outdir, "cd_map.npy"), cds)
    return metrics

def main():
    cfg = load_config()
    outdir = cfg.get("outdir", "outputs_litho_stage")
    os.makedirs(outdir, exist_ok=True)
    setup_litho_parameters(cfg)
    load_klayout_mask(cfg, outdir)
    demo = litho.simulate_one(cfg.get("dose0",1.0), cfg.get("defocus0_nm",0.0), seed=1)
    if "R" in demo:
        plt.figure()
        plt.imshow(demo["R"], origin="lower")
        plt.title("Demo Resist")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "demo_resist.png"), dpi=200)
        plt.close()
    metrics = run_litho_sweep(outdir)
    with open(os.path.join(outdir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print("Lithography stage finished.")

if __name__ == "__main__":
    main()
