
# stage4_thermal_implant.py
"""Stage 4 — Ion Implantation + Thermal Anneal/Diffusion (Teaching Proxy)

Lecture-aligned knobs:
  - Dose (cm^-2) controls concentration scale
  - Energy (keV) controls projected range Rp and straggle ΔRp
  - Channeling tail (single-crystal) and mitigation:
      * wafer tilt (~7°)
      * screen oxide
      * pre-amorphous implant (PAI)
  - Anneal: furnace vs RTA; activation + diffusion happen simultaneously
    (minimizing diffusion is critical for small feature sizes)

Simplifying assumptions:
  - 1D depth profile only (no lateral diffusion).
  - Rp and ΔRp are modeled with a toy scaling vs energy and ion mass.
  - Diffusion modeled as convolution with a Gaussian kernel (equivalent to
    constant diffusivity during anneal).

Outputs:
  - depth_um.npy
  - dopant_profile_cm3.npy (as-implanted)
  - dopant_profile_annealed_cm3.npy
  - metrics.json (junction depth, sheet resistance proxy, peak conc, etc.)

Students can extend:
  - add 2D diffusion + mask edge effects
  - implement temperature-dependent diffusivity more carefully
  - link anneal choices to device Vt/leakage in Stage 6
"""

from __future__ import annotations
import argparse, os, json
import numpy as np
import matplotlib.pyplot as plt
from common_utils import save_json

ION_MASS = {"B": 11.0, "P": 31.0, "As": 75.0}

def rp_um(energy_keV: float, ion: str) -> float:
    """Toy projected range Rp in um."""
    m = ION_MASS.get(ion, 31.0)
    # lighter ions go deeper
    return 0.01 * (energy_keV ** 1.2) * (31.0 / m) ** 0.35

def straggle_um(energy_keV: float, ion: str) -> float:
    """Toy straggle (1-sigma) in um."""
    return 0.35 * rp_um(energy_keV, ion)

def gaussian_profile(depth_um: np.ndarray, dose_cm2: float, Rp_um: float, dRp_um: float) -> np.ndarray:
    """Gaussian implant profile with area = dose."""
    z_cm = depth_um * 1e-4  # um -> cm
    Rp_cm = Rp_um * 1e-4
    dRp_cm = max(dRp_um * 1e-4, 1e-9)
    # concentration (cm^-3) such that integral C dz = dose (cm^-2)
    C = (dose_cm2 / (np.sqrt(2*np.pi) * dRp_cm)) * np.exp(-0.5 * ((z_cm - Rp_cm)/dRp_cm)**2)
    return C

def add_channeling_tail(C: np.ndarray, depth_um: np.ndarray, tail_strength: float = 0.15, tail_scale_um: float = 3.0) -> np.ndarray:
    """Add an exponential channeling tail (toy)."""
    tail = tail_strength * np.max(C) * np.exp(-depth_um / max(tail_scale_um, 1e-6))
    return C + tail

def diffusion_gaussian(C: np.ndarray, depth_um: np.ndarray, sigma_um: float) -> np.ndarray:
    """Diffuse by convolving with a Gaussian kernel of width sigma_um."""
    dz = float(np.mean(np.diff(depth_um)))
    sigma_px = max(1e-6, sigma_um / max(dz, 1e-9))
    # build kernel
    half = int(np.ceil(4*sigma_px))
    x = np.arange(-half, half+1)
    k = np.exp(-0.5 * (x/sigma_px)**2)
    k /= k.sum()
    Cpad = np.pad(C, (half, half), mode="edge")
    out = np.convolve(Cpad, k, mode="valid")
    return out

def diffusivity_um2_per_s(T_C: float, dopant: str) -> float:
    """Toy diffusivity in um^2/s (not calibrated)."""
    # Arrhenius-like scaling: D = D0 exp(-Ea/kT)
    # We'll just provide relative scaling to let students see trends.
    T = T_C + 273.15
    if dopant == "B":
        D0, Ea = 5e3, 3.5  # proxy
    elif dopant == "P":
        D0, Ea = 2e3, 3.7
    else:
        D0, Ea = 1e3, 4.0
    k_eV = 8.617333262e-5
    return float(D0 * np.exp(-Ea/(k_eV*T)))

def anneal_sigma_um(T_C: float, time_s: float, dopant: str, method: str) -> float:
    """Return diffusion length sigma in um."""
    D = diffusivity_um2_per_s(T_C, dopant)
    # method factor: furnace longer, RTA shorter effective diffusion
    method_factor = 1.0 if method == "furnace" else 0.25
    sigma2 = 2.0 * D * time_s * method_factor
    return float(np.sqrt(max(sigma2, 0.0)))

def activation_fraction(T_C: float, time_s: float) -> float:
    """Toy dopant activation fraction (0..1)."""
    # faster at higher T; saturates
    x = (T_C - 700.0)/200.0 + np.log1p(time_s)/6.0
    return float(1.0/(1.0+np.exp(-x)))

def junction_depth_um(depth_um: np.ndarray, C: np.ndarray, background_cm3: float) -> float:
    """Depth where dopant equals background (simple)."""
    idx = np.where(C <= background_cm3)[0]
    if len(idx) == 0:
        return float(depth_um[-1])
    return float(depth_um[idx[0]])

def sheet_resistance_ohm_per_sq(depth_um: np.ndarray, C_active: np.ndarray, mobility_cm2Vs: float = 200.0) -> float:
    """Very rough sheet resistance proxy: Rs ~ 1 / (q * mu * integral C dz)."""
    q = 1.602e-19
    dz_cm = np.mean(np.diff(depth_um)) * 1e-4
    sheet_charge = float(np.sum(C_active) * dz_cm)  # cm^-2
    cond = q * mobility_cm2Vs * sheet_charge
    return float(1.0 / max(cond, 1e-30))

def run(dopant: str,
        dose_cm2: float,
        energy_keV: float,
        depth_max_um: float,
        npts: int,
        channeling: bool,
        tilt_deg: float,
        screen_oxide_nm: float,
        pre_amorphous: bool,
        anneal_method: str,
        anneal_T_C: float,
        anneal_time_s: float,
        background_cm3: float) -> dict:

    depth_um = np.linspace(0, depth_max_um, npts)

    Rp = rp_um(energy_keV, dopant)
    dRp = straggle_um(energy_keV, dopant)

    C = gaussian_profile(depth_um, dose_cm2, Rp, dRp)

    # Channeling tail and mitigation
    if channeling and (not pre_amorphous):
        tail_strength = 0.18
        # tilt, screen oxide reduce tail
        tail_strength *= 1.0 / (1.0 + tilt_deg/7.0)
        tail_strength *= 1.0 / (1.0 + screen_oxide_nm/20.0)
        C = add_channeling_tail(C, depth_um, tail_strength=tail_strength, tail_scale_um=3.0*Rp)

    # Anneal: diffusion + activation
    sigma = anneal_sigma_um(anneal_T_C, anneal_time_s, dopant, anneal_method)
    C_anneal = diffusion_gaussian(C, depth_um, sigma_um=sigma)

    act = activation_fraction(anneal_T_C, anneal_time_s)
    C_active = act * C_anneal

    xj = junction_depth_um(depth_um, C_active, background_cm3)
    Rs = sheet_resistance_ohm_per_sq(depth_um, C_active)

    metrics = dict(
        dopant=dopant,
        dose_cm2=dose_cm2,
        energy_keV=energy_keV,
        Rp_um=Rp,
        dRp_um=dRp,
        channeling=channeling,
        tilt_deg=tilt_deg,
        screen_oxide_nm=screen_oxide_nm,
        pre_amorphous=pre_amorphous,
        anneal_method=anneal_method,
        anneal_T_C=anneal_T_C,
        anneal_time_s=anneal_time_s,
        diffusion_sigma_um=sigma,
        activation_fraction=act,
        background_cm3=background_cm3,
        peak_cm3=float(C_active.max()),
        junction_depth_um=xj,
        sheet_resistance_ohm_per_sq=Rs,
    )

    return dict(depth_um=depth_um, C_implant=C, C_anneal=C_anneal, C_active=C_active, metrics=metrics)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="out_stage4_implant_thermal")
    ap.add_argument("--dopant", choices=["B","P","As"], default="B")
    ap.add_argument("--dose_cm2", type=float, default=1e15)
    ap.add_argument("--energy_keV", type=float, default=20.0)
    ap.add_argument("--depth_max_um", type=float, default=1.0)
    ap.add_argument("--npts", type=int, default=2001)

    ap.add_argument("--channeling", action="store_true")
    ap.add_argument("--tilt_deg", type=float, default=7.0)
    ap.add_argument("--screen_oxide_nm", type=float, default=10.0)
    ap.add_argument("--pre_amorphous", action="store_true")

    ap.add_argument("--anneal_method", choices=["furnace","rta"], default="rta")
    ap.add_argument("--anneal_T_C", type=float, default=1050.0)
    ap.add_argument("--anneal_time_s", type=float, default=10.0)

    ap.add_argument("--background_cm3", type=float, default=1e15)

    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    out = run(args.dopant, args.dose_cm2, args.energy_keV, args.depth_max_um, args.npts,
              channeling=args.channeling, tilt_deg=args.tilt_deg, screen_oxide_nm=args.screen_oxide_nm,
              pre_amorphous=args.pre_amorphous,
              anneal_method=args.anneal_method, anneal_T_C=args.anneal_T_C, anneal_time_s=args.anneal_time_s,
              background_cm3=args.background_cm3)

    np.save(os.path.join(args.outdir, "depth_um.npy"), out["depth_um"])
    np.save(os.path.join(args.outdir, "dopant_profile_cm3.npy"), out["C_implant"])
    np.save(os.path.join(args.outdir, "dopant_profile_annealed_cm3.npy"), out["C_anneal"])
    np.save(os.path.join(args.outdir, "dopant_profile_active_cm3.npy"), out["C_active"])
    save_json(os.path.join(args.outdir, "metrics.json"), out["metrics"])

    # plot
    plt.figure(figsize=(6,4))
    plt.semilogy(out["depth_um"], out["C_implant"]+1, label="as-implanted")
    plt.semilogy(out["depth_um"], out["C_active"]+1, label="after anneal (active)")
    plt.axhline(args.background_cm3, linestyle="--", label="background")
    plt.xlabel("Depth (um)")
    plt.ylabel("Concentration (cm^-3)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(args.outdir, "dopant_profiles.png"), dpi=220)
    plt.close()

    print("Stage 4 finished. Outputs:", args.outdir)
    print("Junction depth (um):", out["metrics"]["junction_depth_um"], "Rs (ohm/sq):", out["metrics"]["sheet_resistance_ohm_per_sq"])

if __name__ == "__main__":
    main()
