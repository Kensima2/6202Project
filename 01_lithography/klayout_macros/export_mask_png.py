# KLayout Python macro (pya) - Export current view to PNG
# Save as: export_mask_png.py in KLayout macros folder, then run from KLayout (Macros -> Run)
#
# This macro exports the current view as a PNG. Recommended:
# - Zoom to your mask cell
# - Set background white, shapes black (or vice versa)
# - Disable anti-aliasing if available
#
# You can also export image manually via File -> Export -> Image...
#
# Note: KLayout GUI API differences exist across versions; this macro is a best-effort template.

import pya

mw = pya.Application.instance().main_window()
view = mw.current_view()
if view is None:
    raise RuntimeError("No active view. Open a layout first.")

# Adjust these:
out_path = "mask_export.png"
w = 1024
h = 1024

# Export screenshot of current viewport
view.save_image(out_path, w, h)
print("Exported:", out_path)
