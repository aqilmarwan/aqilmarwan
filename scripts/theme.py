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
    "empty":       "#edecf0",   # a zero-contribution day
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

CANVAS = {"w": 900, "h": 560}
MARGIN = 32
CONTENT_W = CANVAS["w"] - 2 * MARGIN          # 836

CELL = 12          # the atom - calendar day, hour-field unit, legend swatch
GUTTER = 3
PITCH = CELL + GUTTER                          # 15
RADIUS = 2

WEEKS = 53
CAL_W = WEEKS * PITCH - GUTTER                 # 792
DAY_LABEL_W = 26                               # gutter for Mon/Wed/Fri

# The hour field is the signature view: 24 columns built from the *same* cell
# and pitch as the calendar, so it reads as the same material. That is what
# fixes the middle panel at 24 * PITCH - GUTTER = 357, and the other two
# panels are sized around it.
HOUR_W = HOUR_BUCKETS_W = 24 * PITCH - GUTTER  # 357

PANEL_GAP = 28
PANEL_W = [220, 360, 200]                      # 780 + 2*28 = 836 = CONTENT_W

BANDS = {
    "header":   {"y": 26},
    "stats":    {"y": 84},
    "months":   {"y": 156},                    # month-label baseline
    "grid":     {"y": 162},                    # heatmap top edge (7*15-3=102)
    "legend":   {"y": 280},
    "momentum": {"y": 292, "h": 40},
    "panels":   {"y": 340, "h": 176},
    "footer":   {"y": 538},
}

STROKE_HAIRLINE = 1
STROKE_LINE = 2                                # momentum line

# The hour field quantises into cells. Pick the smallest "nice" unit that keeps
# the tallest column within HOUR_FIELD_ROWS, so the caption reads sensibly
# ("1 square = 10 commits") instead of "1 square = 11 commits".
HOUR_FIELD_ROWS = 10
HOUR_BUCKETS = 24
NICE_UNITS = [1, 2, 5, 10, 15, 20, 25, 50, 100, 200, 500]

STAT_VALUE_SIZE = 30
LEGEND_STEPS = 5
LEGEND_LABEL_W = 30    # reserved width for the "Less"/"More" end labels
LEGEND_LABEL_GAP = 8
SEG_GAP = 2            # surface gap between stacked composition segments
SEG_MIN = 1.5          # a nonzero category never disappears entirely
