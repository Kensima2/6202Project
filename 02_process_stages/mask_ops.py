from __future__ import annotations
import numpy as np

def shift(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(mask)
    H, W = mask.shape
    xs0 = max(0, -dx); xs1 = min(W, W - dx)
    ys0 = max(0, -dy); ys1 = min(H, H - dy)
    out[ys0+dy:ys1+dy, xs0+dx:xs1+dx] = mask[ys0:ys1, xs0:xs1]
    return out

def dilate(mask: np.ndarray, r: int) -> np.ndarray:
    if r <= 0: 
        return mask.copy().astype(np.uint8)
    m = mask.astype(np.uint8)
    H, W = m.shape
    out = np.zeros_like(m)
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if dx*dx + dy*dy > r*r:
                continue
            ys0 = max(0, -dy); ys1 = min(H, H - dy)
            xs0 = max(0, -dx); xs1 = min(W, W - dx)
            out[ys0+dy:ys1+dy, xs0+dx:xs1+dx] |= m[ys0:ys1, xs0:xs1]
    return out

def erode(mask: np.ndarray, r: int) -> np.ndarray:
    if r <= 0: 
        return mask.copy().astype(np.uint8)
    m = mask.astype(np.uint8)
    H, W = m.shape
    out = np.ones_like(m)
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if dx*dx + dy*dy > r*r:
                continue
            shifted = np.zeros_like(m)
            ys0 = max(0, -dy); ys1 = min(H, H - dy)
            xs0 = max(0, -dx); xs1 = min(W, W - dx)
            shifted[ys0+dy:ys1+dy, xs0+dx:xs1+dx] = m[ys0:ys1, xs0:xs1]
            out &= shifted
    return out

def apply_bias_nm(mask: np.ndarray, bias_nm: float, dx_nm: float) -> np.ndarray:
    r = int(round(abs(bias_nm) / max(dx_nm, 1e-9)))
    return dilate(mask, r) if bias_nm >= 0 else erode(mask, r)

def apply_overlay_nm(mask: np.ndarray, ox_nm: float, oy_nm: float, dx_nm: float) -> np.ndarray:
    dx = int(round(ox_nm / max(dx_nm, 1e-9)))
    dy = int(round(oy_nm / max(dx_nm, 1e-9)))
    return shift(mask, dx, dy)
