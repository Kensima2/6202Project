"""
mask_import.py
Utilities to import a 2D mask exported from KLayout (PNG) into the simulator.

Recommended workflow:
1) Students draw a mask in KLayout (GDS) on a chosen layer.
2) Export the layout (or cell) as a monochrome PNG (KLayout: File -> Export -> Image...)
   - Use a square canvas (e.g., 1024x1024) and disable anti-alias if possible.
3) Run:
      python tools/klayout_png_to_npy.py --png path/to/mask.png --out masks/custom_mask.npy
4) Set CUSTOM_MASK_PATH (or config->klayout_mask->out_npy) to use it for 2D simulations.

Notes:
- This importer intentionally stays simple (education). It assumes a single layer exported as black/white.
- If the exported PNG is anti-aliased, we apply a threshold to binarize.
"""

from __future__ import annotations
import numpy as np

def binarize_image(img: np.ndarray, threshold: float = 0.5, invert: bool = False) -> np.ndarray:
    """
    img: float array in [0,1] or uint8 [0,255]. Supports RGB or grayscale.
    Returns binary float mask in {0,1}.
    """
    arr = img.astype(float)
    if arr.max() > 1.5:
        arr = arr / 255.0
    if arr.ndim == 3:
        # luminance
        arr = 0.2126*arr[...,0] + 0.7152*arr[...,1] + 0.0722*arr[...,2]
    bw = (arr >= float(threshold)).astype(np.float32)
    if invert:
        bw = 1.0 - bw
    return bw

def center_crop_to_square(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    s = min(h, w)
    y0 = (h - s)//2
    x0 = (w - s)//2
    return img[y0:y0+s, x0:x0+s]

def resize_nearest(img: np.ndarray, out_n: int) -> np.ndarray:
    """
    Nearest-neighbor resize (no SciPy).
    img: 2D
    """
    in_ny, in_nx = img.shape
    out_n = int(out_n)
    ys = (np.linspace(0, in_ny-1, out_n)).astype(int)
    xs = (np.linspace(0, in_nx-1, out_n)).astype(int)
    return img[np.ix_(ys, xs)]

def png_to_mask_npy(img: np.ndarray, out_n: int = 512, threshold: float = 0.5, invert: bool = False) -> np.ndarray:
    """
    Convert raw PNG array to a simulator-ready mask bitmap (Ny,Nx) float in {0,1}.
    - center-crop to square
    - binarize
    - resize to out_n x out_n
    """
    img = center_crop_to_square(img)
    bw = binarize_image(img, threshold=threshold, invert=invert)
    bw = resize_nearest(bw, out_n=out_n)
    return bw.astype(np.float32)
