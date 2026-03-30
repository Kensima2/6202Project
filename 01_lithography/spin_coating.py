"""
spin_coating.py
A teaching-focused (not high-fidelity) spin-coating simulator for photoresist.

What it models (qualitatively correct trends):
- Film thickness decreases with higher spin speed (omega) and longer spin time.
- Thickness increases with higher viscosity and higher solid content.
- Provides a simple radial non-uniformity + edge bead profile (for manufacturability discussion).

This module is designed for *education* and to connect "process knob -> resist thickness -> litho window".
"""

from __future__ import annotations
import numpy as np


def rpm_to_rad_s(rpm: float) -> float:
    return float(rpm) * 2.0 * np.pi / 60.0


def thickness_meyerhofer_nm(
    viscosity_pa_s: float,
    density_kg_m3: float,
    solids_fraction: float,
    rpm: float,
    spin_time_s: float,
    k: float = 1.0,
) -> float:
    """
    Meyerhofer-like scaling (teaching proxy):
        h ∝ (η * c / (ρ * ω^2 * t))^(1/3)

    Returns thickness in nm.

    Notes:
    - Real spin coating depends on solvent evaporation, shear thinning, temp, etc.
    - This captures major trends for a project course.
    """
    eta = max(1e-6, float(viscosity_pa_s))
    rho = max(1.0, float(density_kg_m3))
    c = np.clip(float(solids_fraction), 1e-4, 0.9)
    omega = max(1e-6, rpm_to_rad_s(float(rpm)))
    t = max(1e-3, float(spin_time_s))

    h_m = k * ((eta * c) / (rho * (omega**2) * t)) ** (1.0 / 3.0)
    return float(h_m * 1e9)  # m -> nm


def radial_thickness_profile_nm(
    h0_nm: float,
    r_mm: np.ndarray,
    wafer_radius_mm: float,
    nonuniformity_pct: float = 2.0,
    edge_bead_nm: float = 80.0,
    edge_bead_width_mm: float = 2.0,
) -> np.ndarray:
    """
    Simple radial profile:
    - mild bowl/tilt nonuniformity (parabolic)
    - edge bead as a Gaussian bump near edge

    nonuniformity_pct: peak-to-valley variation (percent of h0)
    """
    r = np.asarray(r_mm, dtype=float)
    R = max(1e-6, float(wafer_radius_mm))
    h0 = float(h0_nm)

    # Parabolic non-uniformity: center slightly thicker or thinner (choose thicker at center here)
    nu = (nonuniformity_pct / 100.0) * h0
    bowl = nu * (1.0 - (r / R) ** 2)  # max at center

    # Edge bead near r ~ R
    w = max(1e-3, float(edge_bead_width_mm))
    bead = float(edge_bead_nm) * np.exp(-0.5 * ((r - R) / w) ** 2)

    return np.clip(h0 + bowl + bead, 0.0, None)


def thickness_map_nm(
    h0_nm: float,
    wafer_radius_mm: float = 150.0,
    grid_n: int = 301,
    **profile_kwargs
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate a 2D thickness map for a circular wafer.
    Returns (X_mm, Y_mm, H_nm) with H_nm=0 outside wafer.
    """
    n = int(grid_n)
    R = float(wafer_radius_mm)
    xs = np.linspace(-R, R, n)
    ys = np.linspace(-R, R, n)
    X, Y = np.meshgrid(xs, ys)
    r = np.sqrt(X**2 + Y**2)
    H = radial_thickness_profile_nm(h0_nm, r_mm=r, wafer_radius_mm=R, **profile_kwargs)
    H[r > R] = 0.0
    return X, Y, H
