#!/usr/bin/env python
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np

def rasterize(polys, bbox, N):
    from PIL import Image, ImageDraw
    xmin, ymin, xmax, ymax = bbox
    img = Image.new("L", (N, N), 0)
    draw = ImageDraw.Draw(img)

    def to_px(x, y):
        px = int((x - xmin) / (xmax - xmin + 1e-30) * (N - 1))
        py = int((y - ymin) / (ymax - ymin + 1e-30) * (N - 1))
        return (px, (N - 1) - py)

    for p in polys:
        if len(p) < 3:
            continue
        pts = [to_px(float(x), float(y)) for x, y in p]
        draw.polygon(pts, outline=1, fill=1)

    return (np.array(img) > 0).astype(np.uint8)

def main():
    ap = argparse.ArgumentParser(description="Convert multi-layer GDS to per-layer raster masks (NPY + PNG).")
    ap.add_argument("--gds", required=True)
    ap.add_argument("--layer_map", required=True)
    ap.add_argument("--outdir", default="masks")
    ap.add_argument("--N", type=int, default=1024)
    ap.add_argument("--top_cell", default="")
    args = ap.parse_args()

    import gdstk
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    lm = json.load(open(args.layer_map, "r", encoding="utf-8"))
    lib = gdstk.read_gds(args.gds)
    tops = lib.top_level()
    if not tops:
        raise RuntimeError("No top-level cells found in GDS.")
    if args.top_cell:
        top = next((c for c in tops if c.name == args.top_cell), None)
        if top is None:
            raise ValueError(f"top_cell '{args.top_cell}' not found. Available: {[c.name for c in tops]}")
    else:
        top = tops[0]

    # by_spec = top.get_polygons(by_spec=True)
    polys = top.get_polygons()
    by_spec = {}
    for p in polys:
        key = (p.layer, p.datatype)
        by_spec.setdefault(key, []).append(p.points)

        
    all_polys = []
    for _, (ly, dt) in lm.items():
        all_polys.extend(by_spec.get((ly, dt), []))
    if not all_polys:
        raise RuntimeError("No polygons found for the provided layer map. Check layer/datatype values.")

    xmin = min(p[:,0].min() for p in all_polys)
    ymin = min(p[:,1].min() for p in all_polys)
    xmax = max(p[:,0].max() for p in all_polys)
    ymax = max(p[:,1].max() for p in all_polys)
    bbox = (float(xmin), float(ymin), float(xmax), float(ymax))

    meta = {"gds": args.gds, "top_cell": top.name, "bbox": bbox, "N": args.N, "layers": lm}
    json.dump(meta, open(outdir/"grid_meta.json", "w", encoding="utf-8"), indent=2)

    from PIL import Image
    for name, (ly, dt) in lm.items():
        polys = by_spec.get((ly, dt), [])
        mask = rasterize(polys, bbox=bbox, N=args.N)
        np.save(outdir/f"{name}.npy", mask)
        Image.fromarray((mask*255).astype(np.uint8)).save(outdir/f"{name}.png")
        print("Wrote", name, "polygons:", len(polys))

if __name__ == "__main__":
    main()
