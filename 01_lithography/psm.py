"""
psm.py
Phase Shift Mask helpers (teaching-focused).

Idea:
- Represent mask transmission as a COMPLEX field: T = A * exp(j*phi)
- Binary PSM example: regions have phase 0 or pi.
- Works with our baseline imaging since FFT accepts complex arrays.

Students can extend:
- attenuated PSM (6% transmission), alternating PSM, rim-PSM for contacts, etc.
"""

from __future__ import annotations
import numpy as np

def apply_binary_psm_1d(mask_amp: np.ndarray, pitch_nm: float, x_nm: np.ndarray,
                        phase_shift_rad: float = np.pi,
                        region: str = "spaces") -> np.ndarray:
    """
    Apply phase shift to either 'spaces' or 'lines' region for 1D periodic line/space mask.

    mask_amp: (1,N) amplitude transmission (0/1 or gray)
    Returns complex transmission (1,N).
    """
    amp = mask_amp.astype(float)
    xm = np.mod(x_nm, pitch_nm)
    # Determine line region from amplitude if binary: line=1 (bright tone). For robustness, use amp>0.5.
    is_line = amp[0] > 0.5
    if region == "spaces":
        phase = np.where(is_line, 0.0, phase_shift_rad)
    elif region == "lines":
        phase = np.where(is_line, phase_shift_rad, 0.0)
    else:
        raise ValueError("region must be 'spaces' or 'lines'")
    return amp * np.exp(1j * phase)[None, :]

def apply_binary_psm_2d(mask_amp: np.ndarray, phase_shift_rad: float = np.pi,
                        where: str = "background") -> np.ndarray:
    """
    Simple 2D binary PSM:
    - where='background': background gets pi, features 0 (or vice versa)
    This is a teaching proxy; real PSM for contacts is more nuanced.

    mask_amp: (Ny,Nx) amplitude mask (0/1)
    Returns complex transmission.
    """
    amp = mask_amp.astype(float)
    is_feat = amp > 0.5
    if where == "background":
        phase = np.where(is_feat, 0.0, phase_shift_rad)
    elif where == "features":
        phase = np.where(is_feat, phase_shift_rad, 0.0)
    else:
        raise ValueError("where must be 'background' or 'features'")
    return amp * np.exp(1j * phase)
