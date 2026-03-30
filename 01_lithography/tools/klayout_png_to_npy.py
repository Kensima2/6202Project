#!/usr/bin/env python
"""
tools/klayout_png_to_npy.py
Convert a KLayout-exported PNG mask to a .npy mask for 2D simulation.

Usage:
  python tools/klayout_png_to_npy.py --png mymask.png --out masks/custom_mask.npy --size 512 --threshold 0.5 --invert

Notes:
- Requires pillow (PIL) for robust PNG reading.
"""
from __future__ import annotations
import argparse, os
import numpy as np
from PIL import Image
import mask_import

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", required=True, help="Input PNG exported by KLayout")
    ap.add_argument("--out", required=True, help="Output .npy path")
    ap.add_argument("--size", type=int, default=512, help="Output mask size (NxN)")
    ap.add_argument("--threshold", type=float, default=0.5, help="Binarization threshold in [0,1]")
    ap.add_argument("--invert", action="store_true", help="Invert black/white if needed")
    args = ap.parse_args()

    img = np.array(Image.open(args.png).convert("RGBA"))[:, :, :3]  # drop alpha
    m = mask_import.png_to_mask_npy(img, out_n=args.size, threshold=args.threshold, invert=args.invert)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    np.save(args.out, m)
    print(f"Saved mask: {args.out} shape={m.shape}")

if __name__ == "__main__":
    main()
