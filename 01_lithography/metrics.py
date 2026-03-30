"""
metrics.py
Metrics for manufacturability: window area, NILS (1D), sensitivity.
"""

from __future__ import annotations
import numpy as np

def window_area(pass_map: np.ndarray, dose_list: np.ndarray, defocus_list_nm: np.ndarray) -> float:
    """
    Approximate process window area in (dose, defocus) space.
    Units: (relative-dose * nm)
    """
    if pass_map.size == 0:
        return 0.0
    dd = float(dose_list[1] - dose_list[0]) if len(dose_list) > 1 else 1.0
    df = float(defocus_list_nm[1] - defocus_list_nm[0]) if len(defocus_list_nm) > 1 else 1.0
    return float(pass_map.sum()) * dd * df

def nils_1d(intensity_row: np.ndarray, x_nm: np.ndarray, edge_x_nm: float, eps: float = 1e-9) -> float:
    """
    Normalized Image Log Slope (NILS) at a chosen edge location in 1D:
        NILS = | d ln I / d x | * CD
    Here we output |d ln I/dx| at edge_x_nm (1/nm).
    Students can define CD scaling or compute at the threshold crossing.
    """
    I = np.clip(intensity_row, eps, None)
    # derivative
    dI = np.gradient(I, x_nm)
    dlnI = dI / I
    # interpolate at edge_x_nm
    return float(np.interp(edge_x_nm, x_nm, np.abs(dlnI)))

def cd_sensitivity(values: np.ndarray, axis: np.ndarray) -> float:
    """
    Simple sensitivity metric: slope magnitude of CD vs axis around the center.
    """
    if len(axis) < 3:
        return 0.0
    mid = len(axis)//2
    # local linear fit using 5 points if available
    lo = max(0, mid-2); hi = min(len(axis), mid+3)
    x = axis[lo:hi]; y = values[lo:hi]
    A = np.vstack([x, np.ones_like(x)]).T
    m, _ = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(abs(m))


def epe_summary(epe_mean_nm: float | None, epe_std_nm: float | None, epe_maxabs_nm: float | None) -> str:
    if epe_mean_nm is None:
        return "EPE: N/A"
    return f"EPE mean={epe_mean_nm:.2f} nm, std={epe_std_nm:.2f} nm, max|epe|={epe_maxabs_nm:.2f} nm"

def cdu_summary(cd_mean_nm: float | None, cd_std_nm: float | None) -> str:
    if cd_mean_nm is None:
        return "CDU: N/A"
    return f"CDU (CD_fit): mean={cd_mean_nm:.2f} nm, std={cd_std_nm:.2f} nm"
