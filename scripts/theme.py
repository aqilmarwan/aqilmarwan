"""Design tokens. Every colour, size and spacing value in the renderer comes from
here - render.py must not contain a literal hex code or a bare pixel number.

The ramp uses GitHub's contribution-green tone (OKLCH hue ~148) but re-spaced:
GitHub's own steps jump unevenly in lightness (dL 0.14 / 0.10 / 0.15), this one
is exactly even. Verified with the dataviz validator in both modes:

  ramp (--ordinal)   monotone L, adjacent dL >= 0.06, light end >= 2:1 vs surface

Even dL is what makes the ramp survive deuteranopia: the steps stay ordered by
lightness alone, so hue is never load-bearing.
"""

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------

LIGHT = {
    "surface":     "#fbfaf8",
    "empty":       "#edecf0",   # an empty bucket
    "hairline":    "#dfdde3",
    "ink":         "#211f27",
    "ink_soft":    "#6a676f",
    "ink_muted":   "#8d8b91",
    "ramp": ["#46ca5b", "#18b044", "#00943a", "#007935", "#005f2d"],
}

DARK = {
    "surface":     "#0d0d11",
    "empty":       "#1a191d",
    "hairline":    "#27252b",
    "ink":         "#f7f6f9",
    "ink_soft":    "#b8b6bd",
    "ink_muted":   "#87858c",
    "ramp": ["#005215", "#007327", "#00963b", "#00ba56", "#26df77"],
}

THEMES = {"light": LIGHT, "dark": DARK}

# OKLCH lightness of each ramp step, kept for documentation and for the
# self-check in tests. Even spacing is the accessibility mechanism.
RAMP_L = {
    "light": [0.742, 0.662, 0.583, 0.503, 0.424],
    "dark":  [0.380, 0.483, 0.587, 0.690, 0.794],
}

# --------------------------------------------------------------------------
# typography
# --------------------------------------------------------------------------

SANS = ('-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, '
        "Arial, sans-serif")
MONO = ('ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
        '"Liberation Mono", monospace')

TYPE = {
    "hero":    {"size": 34, "weight": 600, "tracking": -0.8},
    "title":   {"size": 17, "weight": 600, "tracking": -0.2},
    "body":    {"size": 12, "weight": 400, "tracking": 0},
    "label":   {"size": 10, "weight": 500, "tracking": 0.3},
    "micro":   {"size": 9,  "weight": 500, "tracking": 0.4},
}

# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

CANVAS = {"w": 900, "h": 322}
MARGIN = 32
CONTENT_W = CANVAS["w"] - 2 * MARGIN          # 836

RADIUS = 2

# --- the density time series (the whole graphic) --------------------------
# Every one of the trailing 365 days gets its own bar, so the plot carries the
# raw distribution rather than a summary of it. A 7-day envelope sits behind
# the bars to give the trend a readable shape.
DENSITY_Y = 36
DENSITY_H = 150
DENSITY_X = MARGIN
DENSITY_W = CONTENT_W
BAR_GAP = 0.9                                  # keeps daily bars distinct
BAR_MIN = 1.0
ENVELOPE_SMOOTH = [1, 2, 3, 2, 1]              # gentle shape under the bars
MONTH_AXIS_Y = 204

# --- composition, the second line -----------------------------------------
COMP_Y = 232
COMP_H = 12
COMP_LABEL_Y = 262
SEG_GAP = 2            # surface gap between stacked composition segments
SEG_MIN = 1.5          # a nonzero category never disappears entirely
SWATCH = 8
LEGEND_GAP = 20        # between one legend entry and the next

# rough advance widths, used only to pack the inline legend deterministically
CHAR_W_SANS = 0.54
CHAR_W_MONO = 0.60

BANDS = {
    "density": {"y": DENSITY_Y, "h": DENSITY_H},
    "footer":  {"y": 290},
}

STROKE_HAIRLINE = 1
STROKE_LINE = 2
