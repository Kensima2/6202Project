"""
Photolithography Baseline Simulator (Open-source, teaching-focused)
===============================================================

Goal:
- Provide a baseline, modifiable simulator for a course project on photolithography.
- Students can explore how wavelength/NA/partial coherence/defocus/dose/resist/PEB
  affect aerial image, developed resist profile, CD, and process window.

This is a *teaching* model (scalar imaging + simplified resist). It is NOT a replacement
for commercial lithography simulators.

Dependencies:
    pip install numpy matplotlib

Run:
    python photolithography_baseline.py

What you will get (figures):
1) Mask + aerial image + developed resist demo
2) Dose–Defocus process window (pass/fail for CD target)
3) CD vs Dose slice, CD vs Defocus slice

How to extend (student tasks):
- Implement different illumination (annular, dipole), different patterns (contacts),
  add resist contrast curve, add LER noise, optimize for max process window, etc.

License: MIT (for course use; edit freely)
"""

from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt

# Local project modules (optional)
try:
    import psm
    import opc
except Exception:
    psm = None
    opc = None



# =========================
# 0) Student-editable knobs
# =========================

# --- Target / spec ---
TARGET_CD_NM = 180.0
CD_TOL_NM = 10.0

# --- Imaging knobs ---
WAVELENGTH_NM = 193.0          # 365 / 248 / 193, etc.
NA = 0.93                      # e.g., 0.4~1.35 (immersion)
SIGMA_IN = 0.0                 # partial coherence annulus inner sigma
SIGMA_OUT = 0.7                # outer sigma (0~1)
N_SOURCE_SAMPLES = 12          # more = slower but smoother

# Defocus sweep (nm)
DEFOCUS_LIST_NM = np.linspace(-200, 200, 161)

# --- Mask / pattern ---
PATTERN = "line_space_1d"      # "line_space_1d" or "contact_2d"
PITCH_NM = 400.0
DUTY_CYCLE = 0.5               # line width / pitch (or contact CD / pitch)
MASK_TONE = "bright"           # "bright" (features transmit) or "dark" (features block)

# --- RET options (teaching) ---
PSM_ENABLED = False            # phase shift mask (complex transmission)
PSM_PHASE_RAD = np.pi          # default pi shift
PSM_REGION = "spaces"          # "spaces" or "lines" for 1D, "background"/"features" for 2D
OPC_MASK_BIAS_NM = 0.0         # simple mask bias (nm). positive widens features
CUSTOM_MASK_PATH = None        # optional: path to .npy mask array for advanced teams
CUSTOM_MASK_SCALE = 1.0        # optional scaling on custom mask (for exploration)

# --- Resist / process knobs ---
RESIST_TYPE = "positive"       # "positive" or "negative"
DOSE_LIST = np.linspace(0.7, 1.3, 121)   # relative dose sweep
DOSE0 = 1.0
DEVELOP_THRESHOLD = 0.5        # threshold after normalization (0~1)
PEB_BLUR_NM = 18.0             # diffusion-length proxy (larger => more blur)
POST_DEV_BIAS_NM = 0.0         # optional simple bias

# --- Numerical grid ---
DX_NM = 2.0                    # pixel size
SIM_PITCHES = 3                # simulate multiple pitches
PAD_FACTOR = 2                 # FFT padding factor


# =========================
# 1) Utilities
# =========================

def _fft2(a: np.ndarray) -> np.ndarray:
    return np.fft.fft2(a)

def _ifft2(a: np.ndarray) -> np.ndarray:
    return np.fft.ifft2(a)

def gaussian_blur_fft(img: np.ndarray, sigma_nm: float, dx_nm: float) -> np.ndarray:
    """Gaussian blur via FFT (no SciPy). sigma in nm."""
    if sigma_nm <= 0:
        return img.copy()
    ny, nx = img.shape
    fy = np.fft.fftfreq(ny, d=dx_nm)  # cycles per nm
    fx = np.fft.fftfreq(nx, d=dx_nm)
    FX, FY = np.meshgrid(fx, fy)
    H = np.exp(-2.0 * (np.pi**2) * (sigma_nm**2) * (FX**2 + FY**2))
    out = _ifft2(_fft2(img) * H).real
    return out

def normalize01(a: np.ndarray) -> np.ndarray:
    a = a - a.min()
    mx = a.max()
    if mx > 0:
        a = a / mx
    return a


# =========================
# 2) Mask builders
# =========================

def build_mask_1d_line_space(x_nm: np.ndarray, pitch_nm: float, duty: float, tone: str) -> np.ndarray:
    """1D periodic binary mask along x (returned as 2D array with 1 row for reuse)."""
    line_w = pitch_nm * duty
    xm = np.mod(x_nm, pitch_nm)
    is_line = xm < line_w
    if tone == "bright":
        m = is_line.astype(float)
    elif tone == "dark":
        m = (~is_line).astype(float)
    else:
        raise ValueError("tone must be 'bright' or 'dark'")
    return m[None, :]  # shape (1, Nx)

def build_mask_2d_contact(x_nm: np.ndarray, y_nm: np.ndarray, pitch_nm: float, cd_nm: float, tone: str) -> np.ndarray:
    """2D periodic contact pattern (simple square)."""
    X, Y = np.meshgrid(x_nm, y_nm)
    xm = np.mod(X, pitch_nm)
    ym = np.mod(Y, pitch_nm)
    half = cd_nm / 2.0
    cx = pitch_nm / 2.0
    cy = pitch_nm / 2.0
    is_contact = (np.abs(xm - cx) <= half) & (np.abs(ym - cy) <= half)
    if tone == "bright":
        m = is_contact.astype(float)
    elif tone == "dark":
        m = (~is_contact).astype(float)
    else:
        raise ValueError("tone must be 'bright' or 'dark'")
    return m


# =========================
# 3) Scalar imaging (simplified partial coherence)
# =========================

def pupil_function(FX: np.ndarray, FY: np.ndarray, wavelength_nm: float, na: float, defocus_nm: float) -> np.ndarray:
    """
    Circular pupil with defocus phase.
    Cutoff: f_c = NA/lambda (cycles per nm). lambda in nm.
    Defocus phase here is a teaching approximation (captures trends).
    """
    fc = na / wavelength_nm
    R2 = FX**2 + FY**2
    inside = R2 <= fc**2
    rho2 = np.zeros_like(R2)
    rho2[inside] = R2[inside] / (fc**2)
    phase = np.exp(-1j * np.pi * (defocus_nm / max(1.0, wavelength_nm)) * rho2)
    return inside.astype(complex) * phase

def sample_source_points(sigma_in: float, sigma_out: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Sample points in a unit disk annulus [sigma_in, sigma_out]."""
    pts = []
    for _ in range(n):
        r = np.sqrt(rng.uniform(sigma_in**2, sigma_out**2))
        th = rng.uniform(0, 2*np.pi)
        pts.append([r*np.cos(th), r*np.sin(th)])
    return np.array(pts, dtype=float)

def aerial_image_scalar_partial(mask: np.ndarray, dx_nm: float,
                                wavelength_nm: float, na: float,
                                sigma_in: float, sigma_out: float,
                                n_source: int, defocus_nm: float,
                                seed: int = 0) -> np.ndarray:
    """
    Teaching partial-coherence model:
    - Average coherent images over multiple source points (oblique illumination).
    - Not full Hopkins/TCC, but captures key trends for education.
    """
    rng = np.random.default_rng(seed)
    ny, nx = mask.shape

    fy = np.fft.fftfreq(ny, d=dx_nm)
    fx = np.fft.fftfreq(nx, d=dx_nm)
    FX, FY = np.meshgrid(fx, fy)

    M = _fft2(mask)
    fc = na / wavelength_nm
    src = sample_source_points(sigma_in, sigma_out, n_source, rng)

    I_acc = np.zeros_like(mask, dtype=float)
    for sx, sy in src:
        H = pupil_function(FX - sx*fc, FY - sy*fc, wavelength_nm, na, defocus_nm)
        E = _ifft2(M * H)
        I_acc += (E.real**2 + E.imag**2)

    return normalize01(I_acc / max(1, len(src)))


# =========================
# 4) Resist (simplified)
# =========================

def develop(intensity01: np.ndarray, dose_rel: float, thr: float,
            resist_type: str, peb_blur_nm: float, dx_nm: float) -> np.ndarray:
    """
    Simplified resist:
    - dose scales intensity
    - PEB blur modeled as Gaussian blur on intensity
    - threshold -> binary resist remain
    """
    I = np.clip(intensity01 * dose_rel, 0.0, 1.0)
    I = gaussian_blur_fft(I, sigma_nm=peb_blur_nm, dx_nm=dx_nm)
    I = normalize01(I)

    if resist_type == "positive":
        return (I < thr).astype(int)
    if resist_type == "negative":
        return (I >= thr).astype(int)
    raise ValueError("resist_type must be 'positive' or 'negative'")


# =========================
# 5) CD extraction
# =========================

def extract_cd_line_1d(x_nm: np.ndarray, resist_row: np.ndarray, pitch_nm: float) -> float:
    """CD as the widest contiguous resist segment in the center pitch."""
    in_center = (x_nm >= -pitch_nm/2) & (x_nm < pitch_nm/2)
    ones = (resist_row[in_center] == 1).astype(int)
    xx = x_nm[in_center]
    if ones.sum() == 0:
        return 0.0
    edges = np.diff(np.concatenate(([0], ones, [0])))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    dx = xx[1] - xx[0]
    widths = (ends - starts) * dx
    return float(np.max(widths))


def _boundary_points(bin_img: np.ndarray) -> np.ndarray:
    """
    Return (N,2) integer pixel coordinates (y,x) of boundary pixels where bin_img==1 and at least one 4-neighbor is 0.
    """
    h, w = bin_img.shape
    pts = []
    for y in range(h):
        for x in range(w):
            if bin_img[y, x] != 1:
                continue
            # 4-neighbors
            if (y == 0 or bin_img[y-1, x] == 0 or
                y == h-1 or bin_img[y+1, x] == 0 or
                x == 0 or bin_img[y, x-1] == 0 or
                x == w-1 or bin_img[y, x+1] == 0):
                pts.append((y, x))
    return np.array(pts, dtype=int)


def fit_circle_kasa(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float] | None:
    """
    Algebraic circle fit (Kåsa): fit x^2 + y^2 + A x + B y + C = 0
    Returns (xc, yc, r) in same units as x,y. Returns None if insufficient points.
    """
    if len(x) < 6:
        return None
    A = np.vstack([x, y, np.ones_like(x)]).T
    b = -(x**2 + y**2)
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    a, b_, c = sol
    xc = -a / 2.0
    yc = -b_ / 2.0
    r2 = xc**2 + yc**2 - c
    if r2 <= 0:
        return None
    r = float(np.sqrt(r2))
    return float(xc), float(yc), r


def contact_metrics_from_cell(cell: np.ndarray,
                              x_nm: np.ndarray, y_nm: np.ndarray,
                              intensity_cell: np.ndarray | None = None,
                              target_cd_nm: float | None = None) -> dict:
    """
    Compute manufacturing-relevant metrics from ONE pitch cell:
    - Largest connected component area
    - Equivalent circle CD from area
    - Boundary extraction + circle fit (center & CD)
    - EPE stats vs target CD (if provided)
    - NILS(2D) proxy on boundary from intensity (if provided)

    Returns dict with keys:
      area_nm2, cd_area_circle_nm, cd_fit_nm, cx_nm, cy_nm,
      epe_mean_nm, epe_std_nm, epe_maxabs_nm, nils2d_median_1_per_nm
    """
    dx = float(x_nm[1] - x_nm[0])
    dy = float(y_nm[1] - y_nm[0])

    # Largest component area
    area_nm2 = _largest_component_area(cell.astype(np.uint8), dx_nm=dx, dy_nm=dy)
    cd_area = 0.0 if area_nm2 <= 0 else float(2.0 * np.sqrt(area_nm2 / np.pi))

    # Boundary points for circle fit
    pts = _boundary_points(cell.astype(np.uint8))
    if len(pts) < 6:
        return {
            "area_nm2": float(area_nm2),
            "cd_area_circle_nm": float(cd_area),
            "cd_fit_nm": float(cd_area),
            "cx_nm": 0.0, "cy_nm": 0.0,
            "epe_mean_nm": None, "epe_std_nm": None, "epe_maxabs_nm": None,
            "nils2d_median_1_per_nm": None
        }

    # Convert pixel coordinates to nm coordinates (centered at cell center)
    ys = pts[:, 0]
    xs = pts[:, 1]
    # Coordinates in nm (same grid as x_nm/y_nm slice)
    x_coords = x_nm[xs]
    y_coords = y_nm[ys]

    fit = fit_circle_kasa(x_coords, y_coords)
    if fit is None:
        cd_fit = cd_area
        cx = cy = 0.0
    else:
        cx, cy, r = fit
        cd_fit = float(2.0 * r)

    # EPE statistics (radial error) if target provided
    epe_mean = epe_std = epe_maxabs = None
    if target_cd_nm is not None and fit is not None:
        r_t = float(target_cd_nm) / 2.0
        rr = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)
        epe = rr - r_t
        epe_mean = float(np.mean(epe))
        epe_std = float(np.std(epe))
        epe_maxabs = float(np.max(np.abs(epe)))

    # NILS(2D) proxy on boundary if intensity provided
    nils_med = None
    if intensity_cell is not None:
        I = np.clip(intensity_cell, 1e-9, None)
        dIy, dIx = np.gradient(I, dy, dx)  # gradients in per-nm scaling
        # |grad ln I| = |grad I| / I
        gln = np.sqrt(dIx**2 + dIy**2) / I
        # sample at boundary points (clip indices)
        nils_vals = gln[ys, xs]
        if len(nils_vals) > 0:
            nils_med = float(np.median(nils_vals))

    return {
        "area_nm2": float(area_nm2),
        "cd_area_circle_nm": float(cd_area),
        "cd_fit_nm": float(cd_fit),
        "cx_nm": float(cx),
        "cy_nm": float(cy),
        "epe_mean_nm": epe_mean,
        "epe_std_nm": epe_std,
        "epe_maxabs_nm": epe_maxabs,
        "nils2d_median_1_per_nm": nils_med
    }


def extract_contact_cdu(resist: np.ndarray, intensity: np.ndarray,
                        x_nm: np.ndarray, y_nm: np.ndarray,
                        pitch_nm: float, target_cd_nm: float) -> dict:
    """
    Compute CDU-style statistics by evaluating multiple pitch cells in the simulated field.
    Assumes the simulation spans SIM_PITCHES pitches in x and y.
    Returns mean/std of CD_fit over cells and also returns center-cell metrics.
    """
    dx = float(x_nm[1] - x_nm[0])
    dy = float(y_nm[1] - y_nm[0])

    # Determine pitch in pixels
    pitch_px_x = int(round(pitch_nm / dx))
    pitch_px_y = int(round(pitch_nm / dy))
    if pitch_px_x <= 2 or pitch_px_y <= 2:
        return {"cd_mean_nm": None, "cd_std_nm": None, "center": None}

    # Find center indices
    ny, nx = resist.shape
    cx0 = nx // 2
    cy0 = ny // 2

    # Determine how many whole cells we can extract around the center
    # We'll try to extract SIM_PITCHES x SIM_PITCHES cells centered.
    n_cells = SIM_PITCHES
    half = n_cells // 2

    cds = []
    centers = None
    center_metrics = None

    for iy in range(-half, half + 1):
        for ix in range(-half, half + 1):
            x_start = cx0 + ix * pitch_px_x - pitch_px_x // 2
            x_end   = x_start + pitch_px_x
            y_start = cy0 + iy * pitch_px_y - pitch_px_y // 2
            y_end   = y_start + pitch_px_y
            if x_start < 0 or y_start < 0 or x_end > nx or y_end > ny:
                continue

            cell = resist[y_start:y_end, x_start:x_end].astype(np.uint8)
            Icell = intensity[y_start:y_end, x_start:x_end]
            # local x/y coordinates centered at cell center
            x_local = (np.arange(x_start, x_end) - (x_start + pitch_px_x/2.0)) * dx
            y_local = (np.arange(y_start, y_end) - (y_start + pitch_px_y/2.0)) * dy

            m = contact_metrics_from_cell(cell, x_local, y_local, intensity_cell=Icell, target_cd_nm=target_cd_nm)
            cds.append(m["cd_fit_nm"])

            if ix == 0 and iy == 0:
                center_metrics = m

    if len(cds) == 0:
        return {"cd_mean_nm": None, "cd_std_nm": None, "center": center_metrics}

    cd_mean = float(np.mean(cds))
    cd_std = float(np.std(cds))
    return {"cd_mean_nm": cd_mean, "cd_std_nm": cd_std, "center": center_metrics}

def _largest_component_area(bin_img: np.ndarray, dx_nm: float, dy_nm: float) -> float:
    """
    Compute area (nm^2) of the largest connected component (4-connectivity) in a binary image.
    Implemented without SciPy for portability.
    """
    h, w = bin_img.shape
    visited = np.zeros((h, w), dtype=np.uint8)
    best = 0

    # neighbor offsets (4-connected)
    nbrs = [(1,0), (-1,0), (0,1), (0,-1)]

    for y in range(h):
        for x in range(w):
            if bin_img[y, x] == 0 or visited[y, x]:
                continue
            # BFS
            qy = [y]
            qx = [x]
            visited[y, x] = 1
            cnt = 0
            while qy:
                cy = qy.pop()
                cx = qx.pop()
                cnt += 1
                for dy, dx in nbrs:
                    ny = cy + dy
                    nx = cx + dx
                    if 0 <= ny < h and 0 <= nx < w and (not visited[ny, nx]) and bin_img[ny, nx] == 1:
                        visited[ny, nx] = 1
                        qy.append(ny)
                        qx.append(nx)
            if cnt > best:
                best = cnt

    return float(best) * dx_nm * dy_nm


def _midline_cd_1d(bin_row: np.ndarray, coord_nm: np.ndarray) -> float:
    """
    Width (nm) of the largest contiguous '1' segment in a 1D binary row.
    """
    if bin_row.sum() == 0:
        return 0.0
    edges = np.diff(np.concatenate(([0], bin_row.astype(int), [0])))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    d = float(coord_nm[1] - coord_nm[0])
    widths = (ends - starts) * d
    return float(np.max(widths)) if len(widths) else 0.0


def extract_cd_contact_2d(x_nm: np.ndarray, y_nm: np.ndarray, resist_bin: np.ndarray, pitch_nm: float) -> float:
    """
    More 'industrial-like' CD proxy for 2D contact:
    1) Restrict to the center pitch cell
    2) Find the largest connected component (4-connectivity) in that cell
    3) Compute an **equivalent circular diameter** from its area:
            d_eq = 2 * sqrt(area / pi)

    Returns: d_eq (nm)
    Notes:
    - This avoids the overly optimistic 'area of all pixels' proxy when multiple islands exist.
    - Students can further extend to contour-fitting and critical edge placement metrics.
    """
    dx = float(x_nm[1] - x_nm[0])
    dy = float(y_nm[1] - y_nm[0])

    # Center cell mask
    X, Y = np.meshgrid(x_nm, y_nm)
    in_center = (X >= -pitch_nm/2) & (X < pitch_nm/2) & (Y >= -pitch_nm/2) & (Y < pitch_nm/2)

    # Extract center cell into a compact array
    # We crop bounding box of the center region for speed
    ys, xs = np.where(in_center)
    if len(xs) == 0:
        return 0.0
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    cell = resist_bin[y0:y1, x0:x1].astype(np.uint8)

    area_nm2 = _largest_component_area(cell, dx_nm=dx, dy_nm=dy)
    if area_nm2 <= 0:
        return 0.0

    d_eq = 2.0 * np.sqrt(area_nm2 / np.pi)

    # Optional: midline CDs (not returned, but handy for student extensions)
    # mid_y = cell.shape[0] // 2
    # mid_x = cell.shape[1] // 2
    # cd_x = _midline_cd_1d(cell[mid_y, :], x_nm[x0:x1])
    # cd_y = _midline_cd_1d(cell[:, mid_x], y_nm[y0:y1])

    return float(d_eq)


# =========================
# 6) Simulation
# =========================

def pad_to(a: np.ndarray, pad_factor: int) -> np.ndarray:
    ny, nx = a.shape
    py = (pad_factor - 1) * ny // 2
    px = (pad_factor - 1) * nx // 2
    return np.pad(a, ((py, py), (px, px)), mode="constant", constant_values=0.0)

def crop_center(a: np.ndarray, ny: int, nx: int) -> np.ndarray:
    cy, cx = a.shape[0]//2, a.shape[1]//2
    y0 = cy - ny//2
    x0 = cx - nx//2
    return a[y0:y0+ny, x0:x0+nx]

def simulate_one(dose_rel: float, defocus_nm: float, seed: int = 0) -> dict:
    total_len_nm = SIM_PITCHES * PITCH_NM

    if PATTERN == "line_space_1d":
        x_nm = np.arange(-total_len_nm/2, total_len_nm/2, DX_NM)
        mask = build_mask_1d_line_space(x_nm, PITCH_NM, DUTY_CYCLE, MASK_TONE)
        y_nm = np.array([0.0])
    elif PATTERN == "contact_2d":
        x_nm = np.arange(-total_len_nm/2, total_len_nm/2, DX_NM)
        y_nm = np.arange(-total_len_nm/2, total_len_nm/2, DX_NM)
        cd0 = DUTY_CYCLE * PITCH_NM
        mask = build_mask_2d_contact(x_nm, y_nm, PITCH_NM, cd0, MASK_TONE)
    else:
        raise ValueError("PATTERN must be 'line_space_1d' or 'contact_2d'")


    # --- Optional: custom mask injection (advanced teams) ---
    if CUSTOM_MASK_PATH is not None:
        try:
            cm = np.load(CUSTOM_MASK_PATH)
            if cm.ndim == 1:
                cm = cm[None, :]
            # Normalize to [0,1] amplitude and allow scaling
            cm = normalize01(cm.astype(float)) * float(CUSTOM_MASK_SCALE)
            mask = cm.astype(complex)  # can be complex later by PSM
        except Exception as e:
            raise RuntimeError(f"Failed to load CUSTOM_MASK_PATH={CUSTOM_MASK_PATH}: {e}")

    # --- Optional: OPC mask bias (simple) ---
    if OPC_MASK_BIAS_NM != 0.0 and opc is not None:
        if PATTERN == "line_space_1d":
            # Convert bias -> effective duty cycle and rebuild 1D mask
            duty_eff = opc.apply_mask_bias_1d(None, PITCH_NM, DUTY_CYCLE, float(OPC_MASK_BIAS_NM))
            mask = build_mask_1d_line_space(x_nm, PITCH_NM, duty_eff, MASK_TONE)
        elif PATTERN == "contact_2d":
            # Morphology-based bias: dilate/erode in pixel domain
            radius_px = int(round(abs(OPC_MASK_BIAS_NM) / max(1e-6, DX_NM)))
            if radius_px > 0:
                m_bin = (mask > 0.5).astype(np.uint8)
                mode = "dilate" if OPC_MASK_BIAS_NM > 0 else "erode"
                m_bin2 = opc.opc_morphology_2d(m_bin, steps=1, radius_px=radius_px, mode=mode)
                mask = m_bin2.astype(float)

    # --- Optional: Phase shift mask (PSM) ---
    if PSM_ENABLED and psm is not None:
        if PATTERN == "line_space_1d":
            mask = psm.apply_binary_psm_1d(mask.astype(float), pitch_nm=PITCH_NM, x_nm=x_nm,
                                           phase_shift_rad=float(PSM_PHASE_RAD), region=str(PSM_REGION))
        else:
            # 2D PSM teaching proxy
            mask = psm.apply_binary_psm_2d(mask.astype(float), phase_shift_rad=float(PSM_PHASE_RAD),
                                           where=str(PSM_REGION))

    mask_p = pad_to(mask, PAD_FACTOR)
    I_p = aerial_image_scalar_partial(
        mask_p, DX_NM, WAVELENGTH_NM, NA,
        SIGMA_IN, SIGMA_OUT, N_SOURCE_SAMPLES,
        defocus_nm=defocus_nm, seed=seed
    )
    I = crop_center(I_p, mask.shape[0], mask.shape[1])

    R = develop(I, dose_rel=dose_rel, thr=DEVELOP_THRESHOLD,
                resist_type=RESIST_TYPE, peb_blur_nm=PEB_BLUR_NM, dx_nm=DX_NM)

    extra = {}
    if PATTERN == "line_space_1d":
        cd = extract_cd_line_1d(x_nm, R[0, :], PITCH_NM)
    else:
        # 2D contact: compute more manufacturing-relevant metrics (circle fit, EPE, CDU, NILS2D)
        cdu = extract_contact_cdu(R, I, x_nm, y_nm, PITCH_NM, target_cd_nm=TARGET_CD_NM)
        center = cdu.get("center") or {}
        cd = float(center.get("cd_fit_nm", extract_cd_contact_2d(x_nm, y_nm, R, PITCH_NM)))
        extra = {
            "cd_fit_nm": center.get("cd_fit_nm"),
            "cd_area_circle_nm": center.get("cd_area_circle_nm"),
            "circle_center_nm": [center.get("cx_nm"), center.get("cy_nm")],
            "epe_mean_nm": center.get("epe_mean_nm"),
            "epe_std_nm": center.get("epe_std_nm"),
            "epe_maxabs_nm": center.get("epe_maxabs_nm"),
            "nils2d_median_1_per_nm": center.get("nils2d_median_1_per_nm"),
            "cdu_cd_mean_nm": cdu.get("cd_mean_nm"),
            "cdu_cd_std_nm": cdu.get("cd_std_nm")
        }

    cd = max(0.0, cd + POST_DEV_BIAS_NM)
    out = {"x_nm": x_nm, "y_nm": y_nm, "mask": mask, "I": I, "R": R, "cd_nm": cd}
    out.update(extra)
    return out


# =========================
# 7) Plots / outputs
# =========================

def plot_demo_case():
    r = simulate_one(dose_rel=DOSE0, defocus_nm=0.0, seed=1)

    if PATTERN == "line_space_1d":
        x = r["x_nm"]
        plt.figure()
        plt.plot(x, r["mask"][0], label="Mask (binary)")
        plt.plot(x, r["I"][0], label="Aerial image (norm)")
        plt.plot(x, r["R"][0], label="Resist remain (binary)")
        plt.ylim(-0.2, 1.2)
        plt.xlabel("x (nm)")
        plt.title(f"Demo | λ={WAVELENGTH_NM:.0f}nm, NA={NA:.2f}, σ=[{SIGMA_IN:.2f},{SIGMA_OUT:.2f}] "
                  f"| Dose={DOSE0:.2f}, Defocus=0 nm | CD≈{r['cd_nm']:.1f} nm")
        plt.legend()
        plt.grid(True, which="both")
        plt.show()
    else:
        plt.figure(); plt.imshow(r["mask"], origin="lower"); plt.title("Mask (2D)"); plt.colorbar(); plt.show()
        plt.figure(); plt.imshow(r["I"], origin="lower"); plt.title("Aerial image (2D, normalized)"); plt.colorbar(); plt.show()
        plt.figure(); plt.imshow(r["R"], origin="lower"); plt.title(f"Resist remain (2D, binary) | CD≈{r['cd_nm']:.1f} nm(eq)"); plt.colorbar(); plt.show()

def process_window():
    cds = np.zeros((len(DEFOCUS_LIST_NM), len(DOSE_LIST)), dtype=float)
    for i, f in enumerate(DEFOCUS_LIST_NM):
        for j, d in enumerate(DOSE_LIST):
            cds[i, j] = simulate_one(dose_rel=d, defocus_nm=f, seed=0)["cd_nm"]

    pass_map = np.abs(cds - TARGET_CD_NM) <= CD_TOL_NM

    D, F = np.meshgrid(DOSE_LIST, DEFOCUS_LIST_NM)
    plt.figure()
    plt.contourf(D, F, pass_map.astype(int), levels=[-0.5, 0.5, 1.5])
    plt.xlabel("Relative Dose")
    plt.ylabel("Defocus (nm)")
    plt.title(f"Process Window | Target CD={TARGET_CD_NM:.0f}±{CD_TOL_NM:.0f} nm | "
              f"λ={WAVELENGTH_NM:.0f}nm NA={NA:.2f} σ=[{SIGMA_IN:.2f},{SIGMA_OUT:.2f}] "
              f"PEB blur={PEB_BLUR_NM:.0f}nm")
    plt.colorbar(label="Pass(1)/Fail(0)")
    plt.show()

    # Slices
    f0 = int(np.argmin(np.abs(DEFOCUS_LIST_NM - 0.0)))
    d0 = int(np.argmin(np.abs(DOSE_LIST - DOSE0)))

    plt.figure()
    plt.plot(DOSE_LIST, cds[f0, :])
    plt.axhline(TARGET_CD_NM + CD_TOL_NM, linestyle="--")
    plt.axhline(TARGET_CD_NM - CD_TOL_NM, linestyle="--")
    plt.xlabel("Relative Dose")
    plt.ylabel("CD (nm)")
    plt.title("CD vs Dose @ Defocus≈0")
    plt.grid(True, which="both")
    plt.show()

    plt.figure()
    plt.plot(DEFOCUS_LIST_NM, cds[:, d0])
    plt.axhline(TARGET_CD_NM + CD_TOL_NM, linestyle="--")
    plt.axhline(TARGET_CD_NM - CD_TOL_NM, linestyle="--")
    plt.xlabel("Defocus (nm)")
    plt.ylabel("CD (nm)")
    plt.title(f"CD vs Defocus @ Dose≈{DOSE0:.2f}")
    plt.grid(True, which="both")
    plt.show()

    if np.any(pass_map):
        err = np.abs(cds - TARGET_CD_NM)
        err_masked = np.where(pass_map, err, np.inf)
        bi, bj = np.unravel_index(np.argmin(err_masked), err_masked.shape)
        print(f"[Suggested center point] Dose={DOSE_LIST[bj]:.3f}, Defocus={DEFOCUS_LIST_NM[bi]:.1f} nm "
              f"(CD≈{cds[bi,bj]:.2f} nm)")
    else:
        print("[No pass region] Try adjusting PEB_BLUR_NM, DEVELOP_THRESHOLD, NA, σ, or target/tolerance.")


if __name__ == "__main__":
    plot_demo_case()
    process_window()
