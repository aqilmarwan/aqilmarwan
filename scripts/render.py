#!/usr/bin/env python3
"""data/contributions.json -> assets/contributions-{light,dark}.svg

Static geometry only. GitHub serves README images through Camo as <img>, so no
script runs and no external resource loads - every colour, font stack and rule
is emitted inline at build time.

Determinism matters: identical input must produce byte-identical output so the
daily workflow commit is a genuine no-op. All coordinates go through f().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import theme as T

ROOT = Path(__file__).resolve().parent.parent
WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def f(value: float) -> str:
    """Round to 2dp and drop trailing zeros - keeps output small and stable."""
    return f"{round(value + 0.0, 2):.2f}".rstrip("0").rstrip(".") or "0"


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def rect(x, y, w, h, fill, r=None, cls=None, extra="") -> str:
    r = T.RADIUS if r is None else r
    out = f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"'
    if r:
        out += f' rx="{f(r)}"'
    if cls:
        out += f' class="{cls}"'
    if fill:
        out += f' fill="{fill}"'
    return out + extra + "/>"


def text(x, y, body, cls="b", anchor=None, extra="") -> str:
    a = f' text-anchor="{anchor}"' if anchor else ""
    return (f'<text x="{f(x)}" y="{f(y)}" class="{cls}"{a}{extra}>'
            f"{esc(body)}</text>")


def group(body: list[str], transform: str = "") -> str:
    t = f' transform="{transform}"' if transform else ""
    return f"<g{t}>" + "".join(body) + "</g>"


# ---------------------------------------------------------------------------
# curve helpers
# ---------------------------------------------------------------------------

def smooth(values: list[float], kernel: list[int]) -> list[float]:
    """Circular weighted smoothing - a day wraps, so 23:00 neighbours 00:00.

    Deliberately gentle. A wide kernel would flatten the late-night spike that
    is the most distinctive feature of the distribution.
    """
    n = len(values)
    half = len(kernel) // 2
    total = sum(kernel)
    return [
        sum(values[(i + k - half) % n] * w for k, w in enumerate(kernel)) / total
        for i in range(n)
    ]


def spline(points: list[tuple[float, float]]) -> str:
    """Catmull-Rom through the points, emitted as cubic beziers."""
    if len(points) < 2:
        return ""
    out = [f"M{f(points[0][0])},{f(points[0][1])}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i else points[0]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} "
                   f"{f(p2[0])},{f(p2[1])}")
    return " ".join(out)


def hour_x(hour: float) -> float:
    """Hour -> x, sampled at bin centres across the plot width."""
    return T.RIDGE_X + (hour + 0.5) * T.RIDGE_W / T.HOURS


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def build_header(d, c) -> str:
    handle = d["user"].get("login", "")
    sub = (f"commit density by weekday and hour · trailing 365 days · "
           f"{d['timezone'].replace('_', ' ')}")
    return group([
        text(T.MARGIN, T.BANDS["header"]["y"] + 4, handle, "h1"),
        text(T.MARGIN, T.BANDS["header"]["y"] + 22, sub, "l"),
    ])


def build_stats(d, c) -> str:
    m = d["metrics"]
    dn = d["density"]
    yoy = d.get("yoy_pct")
    yoy_txt = "-" if yoy is None else f"{'+' if yoy >= 0 else ''}{round(yoy):g}%"

    peak = dn.get("peak_cell")
    peak_txt = "-"
    if peak:
        peak_txt = f"{WEEKDAY_NAMES[peak['weekday']]} {peak['hour']:02d}"

    tiles = [
        (f"{m['total']:,}", "contributions"),
        (str(m["current_streak"]), "current streak"),
        (str(m["longest_streak"]), "longest streak"),
        (str(m["busiest_day"]["count"]), "busiest day"),
        (peak_txt, "densest hour"),
        (yoy_txt, "vs prior year"),
    ]

    y = T.BANDS["stats"]["y"]
    step = T.CONTENT_W / len(tiles)
    out = []
    for i, (value, label) in enumerate(tiles):
        x = T.MARGIN + i * step
        if i:
            out.append(f'<line x1="{f(x - 14)}" y1="{f(y - 4)}" '
                       f'x2="{f(x - 14)}" y2="{f(y + 40)}" class="rule"/>')
        out.append(text(x, y + 26, value, "v"))
        out.append(text(x, y + 42, label, "l"))
    return group(out)


def build_ridgeline(d, c) -> str:
    """Seven weekday density curves over the 24-hour day.

    One shared y scale across all rows, so row heights are directly comparable -
    per-row normalisation would make Saturday look as busy as Monday.
    """
    dn = d["density"]
    matrix = dn.get("matrix") or [[0] * T.HOURS for _ in range(T.DAYS)]
    order = [1, 2, 3, 4, 5, 6, 0]          # Monday first; GitHub indexes Sun=0
    peak_cell = dn.get("peak_cell")

    curves = [smooth([float(v) for v in matrix[wd]], T.RIDGE_SMOOTH)
              for wd in order]
    ceiling = max((max(c_) for c_ in curves), default=0.0) or 1.0

    last_base = T.RIDGE_TOP + T.RIDGE_HEIGHT + (T.DAYS - 1) * T.RIDGE_PITCH
    out = []

    # structure first, behind the ridges
    for h in T.GRID_HOURS:
        out.append(f'<line x1="{f(hour_x(h))}" y1="{f(T.RIDGE_TOP - 6)}" '
                   f'x2="{f(hour_x(h))}" y2="{f(last_base)}" class="rule"/>')
    out.append(f'<line x1="{f(T.RIDGE_X)}" y1="{f(last_base)}" '
               f'x2="{f(T.RIDGE_X + T.RIDGE_W)}" y2="{f(last_base)}" '
               f'class="rule"/>')

    # Back to front: each ridge carries a surface-coloured halo, so the row
    # behind stays readable where they overlap.
    for row, wd in enumerate(order):
        base = T.RIDGE_TOP + T.RIDGE_HEIGHT + row * T.RIDGE_PITCH
        values = curves[row]
        edge = (values[0] + values[-1]) / 2      # the day wraps at midnight

        def y_of(v):
            return base - (v / ceiling) * T.RIDGE_HEIGHT

        pts = [(T.RIDGE_X, y_of(edge))]
        pts += [(hour_x(h), y_of(v)) for h, v in enumerate(values)]
        pts.append((T.RIDGE_X + T.RIDGE_W, y_of(edge)))

        curve = spline(pts)
        area = (f"{curve} L{f(T.RIDGE_X + T.RIDGE_W)},{f(base)} "
                f"L{f(T.RIDGE_X)},{f(base)} Z")

        out.append(f'<path d="{area}" fill="{c["ridge"][row]}" '
                   f'stroke="{c["surface"]}" stroke-width="{T.RIDGE_HALO}" '
                   f'stroke-linejoin="round"/>')
        # Top line in the ridge's own colour: it vanishes into the fill where
        # the curve is tall, and gives a quiet weekday like Saturday a visible
        # trace where the fill would otherwise be a sliver. A neutral grey line
        # here reads louder than the data it outlines.
        out.append(f'<path d="{curve}" fill="none" stroke="{c["ridge"][row]}" '
                   f'stroke-width="{T.RIDGE_TOPLINE}" stroke-linecap="round"/>')

        out.append(text(T.MARGIN, base - 3, WEEKDAY_NAMES[wd], "l"))
        out.append(text(T.MARGIN + T.CONTENT_W, base - 3,
                        f"{dn['weekday_totals'][wd]:,}", "n", anchor="end"))

        if peak_cell and peak_cell["weekday"] == wd and peak_cell["count"]:
            px = hour_x(peak_cell["hour"])
            py = y_of(values[peak_cell["hour"]])
            out.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="3.4" '
                       f'fill="{c["accent"]}" stroke="{c["surface"]}" '
                       f'stroke-width="1.6"/>')

    # Ticks only. A trailing "hour of day" caption sat on top of the 23 tick,
    # and the subtitle already names the axis.
    for h in T.HOUR_TICKS:
        out.append(text(hour_x(h), T.BANDS["hour_axis"]["y"], f"{h:02d}", "n",
                        anchor="middle"))

    if peak_cell and peak_cell["count"]:
        label = (f"densest: {WEEKDAY_NAMES[peak_cell['weekday']]} "
                 f"{peak_cell['hour']:02d}:00 · {peak_cell['count']} commits")
        out.append(text(T.MARGIN + T.CONTENT_W, T.RIDGE_TOP - 12, label,
                        "cap-accent", anchor="end"))
    out.append(text(T.MARGIN, T.RIDGE_TOP - 12, "COMMIT DENSITY", "cap"))
    return group(out)


def build_momentum(d, c) -> str:
    days = d["window"]["days"]
    roll = d["metrics"]["rolling7"]
    band = T.BANDS["foot"]
    x0, width = T.MARGIN, T.FOOT_W[0]
    top = band["y"] + 20
    base = band["y"] + band["h"] - 26
    if not days or not roll:
        return ""

    peak = max(roll) or 1
    height = base - top
    step = width / max(len(roll), 1)
    pts = [(x0 + (i + 0.5) * step, base - (v / peak) * height)
           for i, v in enumerate(roll)]

    line = "M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts)
    area = (f"M{f(pts[0][0])},{f(base)} L"
            + " L".join(f"{f(x)},{f(y)}" for x, y in pts)
            + f" L{f(pts[-1][0])},{f(base)} Z")

    return group([
        text(x0, band["y"] + 8, "MOMENTUM", "cap"),
        text(x0 + width, band["y"] + 8,
             f"7-day rolling average · peak {round(peak, 1):g}/day", "l",
             anchor="end"),
        f'<line x1="{f(x0)}" y1="{f(base)}" x2="{f(x0 + width)}" '
        f'y2="{f(base)}" class="rule"/>',
        f'<path d="{area}" fill="{c["ramp"][0]}" fill-opacity="0.30"/>',
        f'<path d="{line}" fill="none" stroke="{c["ramp"][3]}" '
        f'stroke-width="{T.STROKE_LINE}" stroke-linejoin="round" '
        f'stroke-linecap="round"/>',
        text(x0, base + 14, days[0]["date"][:7], "n"),
        text(x0 + width, base + 14, days[-1]["date"][:7], "n", anchor="end"),
    ])


def build_composition(d, c) -> str:
    comp = d["composition"]
    band = T.BANDS["foot"]
    x0 = T.MARGIN + T.FOOT_W[0] + T.FOOT_GAP
    width = T.FOOT_W[1]

    # Private activity is not a *kind* of work - it is a hole in the data, so
    # it wears the neutral empty token rather than a ramp step. When the
    # profile setting is enabled it disappears and the real types fill in.
    rows = [
        ("commits", comp.get("commits", 0), c["ramp"][4]),
        ("pull requests", comp.get("pull_requests", 0), c["ramp"][3]),
        ("issues", comp.get("issues", 0), c["ramp"][2]),
        ("reviews", comp.get("reviews", 0), c["ramp"][1]),
        ("other", comp.get("other", 0), c["ramp"][0]),
        ("private", comp.get("private", 0), c["empty"]),
    ]
    rows = [r for r in rows if r[1] > 0] or [("no activity", 0, c["empty"])]
    total = sum(r[1] for r in rows) or 1

    out = [text(x0, band["y"] + 8, "COMPOSITION", "cap")]

    bar_y = band["y"] + 20
    x = x0
    for i, (_, value, fill) in enumerate(rows):
        w = (value / total) * width
        if i == len(rows) - 1:
            w = max(0.0, x0 + width - x)          # absorb rounding drift
        out.append(rect(x, bar_y, max(w - T.SEG_GAP, T.SEG_MIN), 12, fill))
        x += w

    # two columns, so five or six categories fit the band height
    col_w = width / T.LEGEND_COLS
    for i, (label, value, fill) in enumerate(rows):
        col, row = divmod(i, (len(rows) + T.LEGEND_COLS - 1) // T.LEGEND_COLS)
        cx = x0 + col * col_w
        cy = bar_y + 28 + row * T.LEGEND_ROW_H
        out.append(rect(cx, cy - 7, 8, 8, fill, r=1.5))
        out.append(text(cx + 13, cy, label, "l"))
        out.append(text(cx + col_w - 12, cy, f"{value:,}", "n", anchor="end"))
    return group(out)


def build_footer(d, c) -> str:
    s = d.get("sampling", {})
    n = d.get("density", {}).get("total", 0)
    bits = [f"Updated {d['generated']}",
            "generated from the GitHub GraphQL API"]
    if not s.get("complete", True):
        bits.append(f"density from {n:,} commit timestamps across the "
                    f"{s.get('repos_sampled', 0)} most active of "
                    f"{s.get('repos_available', 0)} repositories")
    else:
        bits.append(f"density from {n:,} commit timestamps across all "
                    f"{s.get('repos_sampled', 0)} repositories")
    return text(T.MARGIN, T.BANDS["footer"]["y"], " · ".join(bits), "l")


# ---------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------

def stylesheet(c) -> str:
    ty = T.TYPE
    return (
        f"text{{font-family:{T.SANS};fill:{c['ink']}}}"
        f".h1{{font-size:{ty['title']['size']}px;font-weight:{ty['title']['weight']};"
        f"letter-spacing:{ty['title']['tracking']}px}}"
        f".v{{font-size:{T.STAT_VALUE_SIZE}px;font-weight:{ty['hero']['weight']};"
        f"letter-spacing:{ty['hero']['tracking']}px}}"
        f".b{{font-size:{ty['body']['size']}px}}"
        f".l{{font-size:{ty['label']['size']}px;font-weight:{ty['label']['weight']};"
        f"letter-spacing:{ty['label']['tracking']}px;fill:{c['ink_muted']}}}"
        f".n{{font-family:{T.MONO};font-size:{ty['label']['size']}px;"
        f"font-variant-numeric:tabular-nums;fill:{c['ink_soft']}}}"
        f".cap{{font-size:{ty['micro']['size']}px;font-weight:600;"
        f"letter-spacing:0.8px;fill:{c['ink_muted']}}}"
        f".cap-accent{{font-size:{ty['micro']['size']}px;font-weight:600;"
        f"letter-spacing:0.8px;fill:{c['accent']}}}"
        f".rule{{stroke:{c['hairline']};stroke-width:{T.STROKE_HAIRLINE}}}"
    )


def describe(d) -> str:
    m = d["metrics"]
    dn = d["density"]
    bits = [
        f"Commit density by weekday and hour of day, {d['timezone']} time, "
        f"over the trailing 365 days.",
        f"{m['total']:,} contributions, active on {m['active_days']} days "
        f"({m['active_pct']:g}% of the year).",
        f"Current streak {m['current_streak']} days, longest "
        f"{m['longest_streak']}.",
    ]
    cell = dn.get("peak_cell")
    if cell and cell["count"]:
        bits.append(
            f"The densest hour is {WEEKDAY_NAMES[cell['weekday']]} at "
            f"{cell['hour']:02d}:00 with {cell['count']} commits."
        )
    if dn.get("peak_weekday") is not None:
        totals = dn["weekday_totals"]
        wd = dn["peak_weekday"]
        quietest = min(range(7), key=lambda i: totals[i])
        bits.append(
            f"{WEEKDAY_NAMES[wd]} is the busiest weekday with {totals[wd]} "
            f"commits; {WEEKDAY_NAMES[quietest]} the quietest with "
            f"{totals[quietest]}."
        )
    if dn.get("peak_block"):
        b = dn["peak_block"]
        bits.append(f"The busiest four-hour block is {b['start']:02d}:00 to "
                    f"{b['end']:02d}:00.")
    return " ".join(bits)


def render(d: dict, mode: str) -> str:
    c = T.THEMES[mode]
    title = f"{d['user'].get('login', 'user')}'s commit density distribution"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {T.CANVAS["w"]} {T.CANVAS["h"]}" '
        f'width="{T.CANVAS["w"]}" height="{T.CANVAS["h"]}" role="img" '
        f'aria-labelledby="ttl dsc">',
        f'<title id="ttl">{esc(title)}</title>',
        f'<desc id="dsc">{esc(describe(d))}</desc>',
        f"<style>{stylesheet(c)}</style>",
        rect(0, 0, T.CANVAS["w"], T.CANVAS["h"], c["surface"], r=0),
        build_header(d, c),
        build_stats(d, c),
        build_ridgeline(d, c),
        build_momentum(d, c),
        build_composition(d, c),
        build_footer(d, c),
        "</svg>",
    ]
    return "\n".join(p for p in parts if p) + "\n"


def stamp_readme(assets_dir: Path) -> bool:
    """Rewrite the ?v= query string on the README's embed URLs.

    Camo caches aggressively, so an updated SVG at an unchanged URL can stay
    stale on the rendered profile for hours. The tag is a hash of the SVG bytes,
    which means it only changes when the image actually changes - the daily
    no-op commit stays a no-op.
    """
    readme = ROOT / "README.md"
    if not readme.exists():
        return False

    digest = hashlib.sha256()
    for mode in ("light", "dark"):
        digest.update((assets_dir / f"contributions-{mode}.svg").read_bytes())
    tag = digest.hexdigest()[:12]

    body = readme.read_text()
    updated = re.sub(
        r"(\./assets/contributions-(?:light|dark)\.svg)(?:\?v=[0-9a-f]+)?",
        rf"\1?v={tag}",
        body,
    )
    if updated == body:
        return False
    readme.write_text(updated)
    print(f"stamped README.md embeds with ?v={tag}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true",
                    help="render from fixtures/sample.json instead of live data")
    ap.add_argument("--out", default=str(ROOT / "assets"))
    ap.add_argument("--no-stamp", action="store_true",
                    help="skip rewriting the README cache-busting query string")
    args = ap.parse_args()

    src = (ROOT / "fixtures" / "sample.json") if args.fixture \
        else (ROOT / "data" / "contributions.json")
    if not src.exists():
        print(f"error: {src} not found - run scripts/fetch.py first "
              "(or pass --fixture)", file=sys.stderr)
        return 1

    d = json.loads(src.read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for mode in ("light", "dark"):
        svg = render(d, mode)
        path = out_dir / f"contributions-{mode}.svg"
        path.write_text(svg)
        try:
            shown = path.relative_to(ROOT)
        except ValueError:          # --out may point outside the repo
            shown = path
        print(f"wrote {shown}  {len(svg.encode()) / 1024:.1f} KB")

    if not args.no_stamp and out_dir.resolve() == (ROOT / "assets").resolve():
        stamp_readme(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
