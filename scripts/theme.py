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
    # Weekday is an ORDERED category (Mon -> Sun), so it takes an ordinal
    # ramp rather than categorical hues. Index 0 = Monday.
    "ridge": ["#6a0082", "#79239e", "#863db9", "#9455d3",
              "#a16cee", "#ae86ff", "#baa5ff"],
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
    "ridge": ["#ecb1ff", "#d992ff", "#be79f5", "#a266e2",
              "#8752cf", "#6f3eba", "#5729a5"],
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

CANVAS = {"w": 900, "h": 620}
MARGIN = 32
CONTENT_W = CANVAS["w"] - 2 * MARGIN          # 836

RADIUS = 2
HOURS = 24
DAYS = 7

# --- ridgeline (the hero) -------------------------------------------------
# Seven density curves, one per weekday, sharing one y scale so the rows are
# comparable. Curves are taller than the row pitch, so they overlap - that is
# the joy-plot read, and each ridge carries a surface-coloured halo stroke so
# the one behind stays legible.
RIDGE_LABEL_W = 40                             # Mon/Tue/... gutter
RIDGE_VALUE_W = 56                             # per-row totals, right aligned
RIDGE_PITCH = 32                               # baseline-to-baseline
RIDGE_HEIGHT = 52                              # curve height at the shared max
RIDGE_TOP = 158                                # topmost possible curve apex
RIDGE_X = MARGIN + RIDGE_LABEL_W
RIDGE_W = CONTENT_W - RIDGE_LABEL_W - RIDGE_VALUE_W
RIDGE_HALO = 3                                 # surface-coloured separation
RIDGE_TOPLINE = 2
RIDGE_SMOOTH = [1, 2, 1]                       # gentle, wraps around midnight
HOUR_TICKS = (0, 6, 12, 18, 23)
GRID_HOURS = (6, 12, 18)                       # hairlines behind the ridges

# --- bottom band: momentum (left) + composition (right) -------------------
FOOT_GAP = 36
FOOT_W = [548, 252]                            # 800 + 36 = 836
LEGEND_COLS = 2
LEGEND_ROW_H = 18

BANDS = {
    "header":    {"y": 26},
    "stats":     {"y": 84},
    "ridge":     {"y": RIDGE_TOP},
    "hour_axis": {"y": 424},
    "foot":      {"y": 456, "h": 104},
    "footer":    {"y": 590},
}

STROKE_HAIRLINE = 1
STROKE_LINE = 2                                # momentum line

STAT_VALUE_SIZE = 30
SEG_GAP = 2            # surface gap between stacked composition segments
SEG_MIN = 1.5          # a nonzero category never disappears entirely
