
# illumination_models.py
import numpy as np

def sample_disk(n, sigma, rng):
    r = sigma * np.sqrt(rng.random(n))
    th = 2*np.pi*rng.random(n)
    return np.stack([r*np.cos(th), r*np.sin(th)], axis=1)

def sample_annular(n, sigma_in, sigma_out, rng):
    r2 = (sigma_out**2 - sigma_in**2)*rng.random(n) + sigma_in**2
    r = np.sqrt(r2)
    th = 2*np.pi*rng.random(n)
    return np.stack([r*np.cos(th), r*np.sin(th)], axis=1)

def sample_dipole(n, center, width, angle, rng):
    n1 = n//2
    n2 = n-n1
    ux, uy = np.cos(angle), np.sin(angle)
    c = np.array([center*ux, center*uy])
    pts1 = c + width*rng.standard_normal((n1,2))
    pts2 = -c + width*rng.standard_normal((n2,2))
    return np.vstack([pts1, pts2])

def sample_quadrupole(n, center, width, angle, rng):
    angles = [angle, angle+np.pi/2, angle+np.pi, angle+3*np.pi/2]
    pts = []
    for a in angles:
        ux, uy = np.cos(a), np.sin(a)
        c = np.array([center*ux, center*uy])
        pts.append(c + width*rng.standard_normal((n//4,2)))
    return np.vstack(pts)
