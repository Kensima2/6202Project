# common_utils.py
"""
Utility functions for the Virtual Mini-Foundry basic stages.

Design goals:
- Pure Python + NumPy (no SciPy) for maximum portability in teaching.
- Simple, readable implementations (not foundry-accurate).
"""

from __future__ import annotations
import os, json
import numpy as np

def save_json(path: str, obj: dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def load_npy(path: str) -> np.ndarray:
    return np.load(path)

def save_npy(path: str, arr: np.ndarray):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    np.save(path, arr)

def ensure_binary(a: np.ndarray, thr: float = 0.5) -> np.ndarray:
    return (a.astype(float) >= thr).astype(np.uint8)

def dilate(binary: np.ndarray, radius: int) -> np.ndarray:
    """
    Binary dilation using a disk-like neighborhood (L2 radius) with pure NumPy.
    """
    b = ensure_binary(binary)
    r = int(max(0, radius))
    if r == 0:
        return b.copy()
    h, w = b.shape
    out = np.zeros_like(b)
    ys, xs = np.ogrid[-r:r+1, -r:r+1]
    mask = (ys*ys + xs*xs) <= r*r
    offsets = np.argwhere(mask) - r
    for dy, dx in offsets:
        y0 = max(0, dy)
        y1 = min(h, h+dy)
        x0 = max(0, dx)
        x1 = min(w, w+dx)
        out[y0:y1, x0:x1] |= b[y0-dy:y1-dy, x0-dx:x1-dx]
    return out

def erode(binary: np.ndarray, radius: int) -> np.ndarray:
    """
    Binary erosion using dilation of the inverted image.
    """
    b = ensure_binary(binary)
    inv = 1 - b
    inv_d = dilate(inv, radius)
    return (1 - inv_d).astype(np.uint8)

def opening(binary: np.ndarray, radius: int) -> np.ndarray:
    return dilate(erode(binary, radius), radius)

def closing(binary: np.ndarray, radius: int) -> np.ndarray:
    return erode(dilate(binary, radius), radius)

def measure_feature_width_nm(mask_1d: np.ndarray, dx_nm: float) -> float:
    """
    A simple 1D width estimator: width of the longest contiguous "1" segment.
    """
    m = ensure_binary(mask_1d).astype(int)
    best = 0
    cur = 0
    for v in m:
        if v == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return float(best) * float(dx_nm)


def ensure_binary(arr: np.ndarray, thr: float = 0.5) -> np.ndarray:
    arr = np.asarray(arr)
    return (arr >= thr).astype(np.float32)

def local_feature_size(openings: np.ndarray, pixel_um: float) -> np.ndarray:
    """Estimate local feature size (um) inside openings using a simple distance-to-edge proxy.

    We compute distance to the nearest boundary by iterative erosion; this is a NumPy-only
    substitute for a distance transform.

    For a circular hole, 2*distance_to_edge approximates diameter.
    For arbitrary shapes, it is a local proxy.

    Returns:
        feature_size_um array, same shape.
    """
    open_bin = (openings > 0.5).astype(np.uint8)
    dist = np.zeros_like(open_bin, dtype=np.float32)
    cur = open_bin.copy()
    r = 0
    # iterate until openings vanish
    while cur.any() and r < 512:
        # one erosion step: keep pixels that have all 8-neighbors =1
        p = np.pad(cur, 1, mode="constant", constant_values=0)
        neigh_min = np.minimum.reduce([
            p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:],
            p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]
        ])
        cur = neigh_min.astype(np.uint8)
        r += 1
        dist[cur > 0] = r
    # local feature size proxy ~ 2*radius
    return 2.0 * dist * float(pixel_um)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
