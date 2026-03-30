
# stage4_device.py
"""Compatibility wrapper (kept for earlier handouts).

The Virtual Mini-Foundry flow evolved to:
  Stage 6: device metrics (stage6_device.py)

This file forwards to stage6_device.py so older scripts still work.
"""

from stage6_device import main

if __name__ == "__main__":
    main()
