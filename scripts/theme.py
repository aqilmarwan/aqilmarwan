"""Design tokens. Every colour, size and spacing value in the renderer comes from
here - render.py must not contain a literal hex code or a bare pixel number.

The intensity ramps were generated in OKLCH with exactly-even lightness steps and
verified with the dataviz validator in both modes:

  ramps  (--ordinal)   monotone L, adjacent dL >= 0.06, light end >= 2:1 vs surface
  accent (--pairs all) CVD dE 28.5 protan / 28.1 deutan against the ramp mid

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
    "accent":      "#cc7200",   # amber - peak markers ONLY, nowhere else
    "ramp": ["#bda3ff", "#b47afd", "#a55edb", "#9541b9", "#842298"],
}

DARK = {
    "surface":     "#0d0d11",
    "empty":       "#1a191d",
    "hairline":    "#27252b",
    "ink":         "#f7f6f9",
    "ink_soft":    "#b8b6bd",
    "ink_muted":   "#87858c",
    "accent":      "#d47a00",
    "ramp": ["#5926a2", "#7e44bf", "#a762dc", "#d17ff7", "#f3a8ff"],
}

THEMES = {"light": LIGHT, "dark": DARK}

# OKLCH lightness of each ramp step, kept for documentation and for the
# self-check in tests. Even spacing is the accessibility mechanism.
RAMP_L = {
    "light": [0.772, 0.694, 0.616, 0.538, 0.461],
    "dark":  [0.416, 0.520, 0.625, 0.729, 0.834],
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

CANVAS = {"w": 900, "h": 330}
MARGIN = 32
CONTENT_W = CANVAS["w"] - 2 * MARGIN          # 836

RADIUS = 2

# --- the density time series (the whole graphic) --------------------------
# Every one of the trailing 365 days gets its own bar, so the plot carries the
# raw distribution rather than a summary of it. A 7-day envelope sits behind
# the bars to give the trend a readable shape.
DENSITY_Y = 44          # headroom for the peak annotation
DENSITY_H = 150
DENSITY_X = MARGIN
DENSITY_W = CONTENT_W
BAR_GAP = 0.5                                  # keeps daily bars distinct
BAR_MIN = 1.0
ENVELOPE_SMOOTH = [1, 2, 3, 2, 1]              # gentle shape under the bars
MONTH_AXIS_Y = 212
PEAK_DOT_R = 3.2

# --- composition, the second line -----------------------------------------
COMP_Y = 240
COMP_H = 12
COMP_LABEL_Y = 270
SEG_GAP = 2            # surface gap between stacked composition segments
SEG_MIN = 1.5          # a nonzero category never disappears entirely
SWATCH = 8
LEGEND_GAP = 20        # between one legend entry and the next

# rough advance widths, used only to pack the inline legend deterministically
CHAR_W_SANS = 0.54
CHAR_W_MONO = 0.60

BANDS = {
    "density": {"y": DENSITY_Y, "h": DENSITY_H},
    "footer":  {"y": 298},
}

STROKE_HAIRLINE = 1
STROKE_LINE = 2
