"""
illumination.py
Deterministic source sampling for illumination shapes (annular/dipole).
Students can extend this to quadrupole, custom pupil filters, etc.
"""

from __future__ import annotations
import numpy as np

def annular_source_points(sigma_in: float, sigma_out: float, n_r: int = 4, n_theta: int = 12) -> np.ndarray:
    """
    Deterministic annular sampling in normalized pupil coordinates.
    Returns (N,2) points (sx, sy) with sx^2+sy^2 in [sigma_in^2, sigma_out^2].
    """
    rs = np.linspace(max(1e-6, sigma_in), max(sigma_in + 1e-6, sigma_out), n_r)
    thetas = np.linspace(0, 2*np.pi, n_theta, endpoint=False)
    pts = []
    for r in rs:
        for th in thetas:
            pts.append([r*np.cos(th), r*np.sin(th)])
    return np.array(pts, dtype=float)

def dipole_source_points(sigma: float, delta_theta_deg: float = 20.0, n_theta: int = 9) -> np.ndarray:
    """
    Two lobes centered at 0 and pi (along x-axis) with small angular spread.
    """
    dth = np.deg2rad(delta_theta_deg)
    thetas1 = np.linspace(-dth, dth, n_theta)
    thetas2 = np.pi + thetas1
    pts = []
    for th in np.concatenate([thetas1, thetas2]):
        pts.append([sigma*np.cos(th), sigma*np.sin(th)])
    return np.array(pts, dtype=float)
