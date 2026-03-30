
# plasma_basics_utils.py
"""Plasma / dry-process helper functions (teaching proxies).

These functions connect a few 'knobs' mentioned in the Plasma Basics + Etch lectures
to simple quantitative proxies:

- Mean free path (MFP) vs pressure
- A toy relationship between RF power / bias and ion energy
- A toy relationship between magnetic field and plasma density (ion flux)

NOTE: These are not calibrated to a particular tool.
They are intentionally simple so students can modify and reason about them.
"""

from __future__ import annotations
import numpy as np

kB = 1.380649e-23  # J/K

def mean_free_path(T_K: float, pressure_mTorr: float, collision_diameter_nm: float = 0.37) -> float:
    """Return mean free path (meters) using a hard-sphere model.

    λ = kT / (sqrt(2) * π * d^2 * p)

    Typical effective collision diameters in plasmas are O(0.3–0.5 nm).
    This is a teaching approximation; real MFP depends on species & energy.

    Args:
        T_K: gas temperature in Kelvin
        pressure_mTorr: chamber pressure in mTorr
        collision_diameter_nm: effective diameter in nm

    Returns:
        mean free path in meters
    """
    p_Pa = pressure_mTorr * 1e-3 * 133.322  # mTorr -> Torr -> Pa
    d_m = collision_diameter_nm * 1e-9
    return (kB * T_K) / (np.sqrt(2) * np.pi * (d_m**2) * max(p_Pa, 1e-9))

def ion_energy_eV(rf_power_W: float, pressure_mTorr: float, electrode_area_ratio: float = 10.0) -> float:
    """Toy ion energy model (eV).

    Qualitative trends covered in the lecture:
    - Higher RF power -> higher ion bombardment energy/flux
    - Higher pressure -> more collisions -> lower ion energy

    We model a 'self-bias' proxy that increases with power and decreases with pressure.
    The area ratio term loosely reflects asymmetric electrodes.

    Returns:
        ion energy in eV (order-of-magnitude proxy)
    """
    # keep it bounded and smooth
    power_term = np.sqrt(max(rf_power_W, 0.0))
    pressure_term = 1.0 / (1.0 + (pressure_mTorr / 30.0))
    area_term = (electrode_area_ratio ** 0.25)  # from V1/V2 ~ (A2/A1)^4 in idealized case
    return float(20.0 * power_term * pressure_term / max(area_term, 1e-6))

def ion_flux_rel(magnetic_field_mT: float, rf_power_W: float) -> float:
    """Relative ion flux (dimensionless).

    Lecture trend:
    - Increasing magnetic field can increase plasma density (more electrons confined),
      increasing ion flux, but can also change bias/energy.
    - Higher RF power generally increases flux.

    Returns:
        relative flux (1.0 ~ baseline)
    """
    B = max(magnetic_field_mT, 0.0)
    p = max(rf_power_W, 0.0)
    return float(1.0 + 0.015 * np.log1p(B) + 0.01 * np.log1p(p))
