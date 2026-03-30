
# stage3_thermal_implant.py
"""Compatibility wrapper (kept for earlier handouts).

The Virtual Mini-Foundry flow evolved to:
  Stage 3: CVD / dielectric
  Stage 4: Ion Implant + Thermal anneal/diffusion

This file forwards to stage4_thermal_implant.py so older scripts still work.

If you are using the newer pipeline, call stage3_cvd.py and stage4_thermal_implant.py directly.
"""

from stage4_thermal_implant import main

if __name__ == "__main__":
    main()
