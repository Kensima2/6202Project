# Report Template (Max 6 pages)

## 1. Objective and Spec
- Target pattern (line/space or contact), pitch, target CD and tolerance
- Tools used (baseline + your extensions)

## 2. Baseline Reproduction
Include the three baseline plots:
1) Mask / Aerial image / Developed resist (one representative case)
2) Dose–Defocus process window pass/fail map
3) CD vs Dose (defocus≈0) and CD vs Defocus (dose≈center)

## 3. Imaging / RET Extension (Required)
Describe your implementation and show at least one comparison plot:
- baseline vs your illumination/PSM/RET

## 4. Resist / Process Extension (Required)
Describe your resist/process model extension and show its effect on:
- CD sensitivity and/or process window

## 5. Manufacturability Metric (Required)
Choose at least one metric and report it:
- Window area
- NILS
- CD uniformity / sensitivity

## 6. Engineering Trade-offs
Explain the trade-off(s) you found:
- resolution vs DOF
- window size vs minimum CD
- robustness vs aggressiveness

## 7. Conclusion
- your recommended “center recipe” (dose, defocus, PEB, illumination, etc.)
- what you would do next if you had more time

## 2D Contact (optional but recommended for strong teams)
If you run 2D contact mode, include:
- `demo_2d_resist_circlefit.png` and briefly explain CD_fit and center offset
- Report EPE mean/std/max|epe| (nm), CDU std (nm), and NILS(2D) proxy (1/nm)

## Spin coating (added)
Include at least one of:
- `spin_thickness_vs_rpm.png` + explanation of why thickness changes with rpm
- `spin_thickness_radial_profile.png` + discussion of non-uniformity and edge bead
And briefly state how thickness affected your litho window (through PEB/threshold or your improved model).
