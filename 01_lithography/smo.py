"""
smo.py
Source-Mask Optimization (SMO) helpers (teaching-focused).

We provide a simple grid-search SMO:
- Variables: illumination sigma_out (and optionally sigma_in), and 1D mask bias (OPC-like)
- Objective: maximize process window area under CD tolerance.

Students can extend:
- Add dipole/annular choice, dipole angle, quadrupole
- Joint optimize PEB/threshold
- Use Bayesian optimization or evolutionary search
"""

from __future__ import annotations
import numpy as np

def grid_search_smo(eval_window_area_fn,
                    sigma_out_list: np.ndarray,
                    bias_nm_list: np.ndarray,
                    sigma_in: float = 0.0) -> dict:
    """
    eval_window_area_fn(sigma_in, sigma_out, bias_nm)->window_area

    Returns dict with best params and full score grid.
    """
    sigma_out_list = np.asarray(sigma_out_list, dtype=float)
    bias_nm_list = np.asarray(bias_nm_list, dtype=float)
    scores = np.zeros((len(sigma_out_list), len(bias_nm_list)), dtype=float)

    best = (-np.inf, None, None)
    for i, so in enumerate(sigma_out_list):
        for j, b in enumerate(bias_nm_list):
            w = float(eval_window_area_fn(float(sigma_in), float(so), float(b)))
            scores[i, j] = w
            if w > best[0]:
                best = (w, float(so), float(b))
    return {"best_window_area": best[0], "best_sigma_out": best[1], "best_bias_nm": best[2],
            "sigma_out_list": sigma_out_list, "bias_nm_list": bias_nm_list, "scores": scores}
