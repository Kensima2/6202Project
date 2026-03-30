"""
opc.py
Optical Proximity Correction (OPC) helpers (teaching-focused, code-first).

We provide two lightweight OPC flavors:
1) 1D "mask bias" OPC: search a mask bias (nm) to hit target CD at nominal conditions.
2) 2D morphological OPC: apply dilate/erode to bitmap mask; optionally iterate with a simple loop.

No SciPy dependency: morphology is implemented using numpy neighborhood max/min.

Students can extend:
- Model-based OPC: gradient-free optimization of pixel mask
- Assist features / serifs (in 2D)
- Multi-objective OPC across dose/defocus, not just a single point
"""

from __future__ import annotations
import numpy as np

def _binary_dilate(img: np.ndarray, radius_px: int = 1) -> np.ndarray:
    """Square-kernel dilation, 4/8-neighborhood approx via max over shifts."""
    r = int(radius_px)
    if r <= 0:
        return img.copy()
    pad = np.pad(img, ((r,r),(r,r)), mode="edge")
    acc = np.zeros_like(img, dtype=np.uint8)
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            acc = np.maximum(acc, pad[r+dy:r+dy+img.shape[0], r+dx:r+dx+img.shape[1]])
    return acc

def _binary_erode(img: np.ndarray, radius_px: int = 1) -> np.ndarray:
    """Square-kernel erosion via min over shifts."""
    r = int(radius_px)
    if r <= 0:
        return img.copy()
    pad = np.pad(img, ((r,r),(r,r)), mode="edge")
    acc = np.ones_like(img, dtype=np.uint8)
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            acc = np.minimum(acc, pad[r+dy:r+dy+img.shape[0], r+dx:r+dx+img.shape[1]])
    return acc

def apply_mask_bias_1d(x_nm: np.ndarray, pitch_nm: float, duty_cycle: float, bias_nm: float) -> float:
    """
    Convert bias (nm) into an effective duty cycle for 1D line/space.
    Positive bias means wider line.
    """
    line_w = pitch_nm * duty_cycle + 2.0 * bias_nm
    line_w = np.clip(line_w, 0.0, pitch_nm)
    return float(line_w / pitch_nm)

def find_bias_for_target_cd(sim_fn, target_cd_nm: float, pitch_nm: float, duty_cycle: float,
                           bias_range_nm: tuple[float,float]=(-60.0, 60.0),
                           n_iter: int = 18) -> tuple[float, float]:
    """
    Binary search-like on bias to hit target CD.
    sim_fn(duty_cycle)->cd_nm must simulate at nominal dose/defocus.

    Returns (bias_nm, achieved_cd_nm)
    """
    lo, hi = map(float, bias_range_nm)
    best = (0.0, float("inf"))
    for _ in range(int(n_iter)):
        mid = 0.5*(lo+hi)
        duty_mid = apply_mask_bias_1d(None, pitch_nm, duty_cycle, mid)  # x_nm not needed here
        cd = float(sim_fn(duty_mid))
        err = abs(cd - target_cd_nm)
        if err < best[1]:
            best = (mid, err)
            best_cd = cd
        # Decide direction: if cd too small, increase bias (widen line)
        if cd < target_cd_nm:
            lo = mid
        else:
            hi = mid
    return float(best[0]), float(best_cd)

def opc_morphology_2d(mask_bin: np.ndarray, steps: int = 1, radius_px: int = 1, mode: str = "dilate") -> np.ndarray:
    """
    Apply repeated dilation/erosion to a 2D binary mask.
    mode: 'dilate' or 'erode'
    """
    out = mask_bin.astype(np.uint8)
    for _ in range(int(steps)):
        if mode == "dilate":
            out = _binary_dilate(out, radius_px=radius_px)
        elif mode == "erode":
            out = _binary_erode(out, radius_px=radius_px)
        else:
            raise ValueError("mode must be 'dilate' or 'erode'")
    return out
