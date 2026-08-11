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


def nice_unit(peak: int, rows: int) -> int:
    """Smallest 'nice' cell value keeping the tallest column within `rows`."""
    for unit in T.NICE_UNITS:
        if peak <= unit * rows:
            return unit
    return max(1, math.ceil(peak / rows))


def thresholds(counts: list[int]) -> list[int]:
    """Quantile cut points over ACTIVE days, so the ramp spends its steps where
    the data actually is. A fixed linear scale would put ~95% of this account's
    days in step 1 and waste four colours on the tail."""
    active = sorted(c for c in counts if c > 0)
    if not active:
        return [1, 2, 3, 4]
    cuts = []
    for i in range(1, T.LEGEND_STEPS):
        idx = min(len(active) - 1, int(len(active) * i / T.LEGEND_STEPS))
        cuts.append(active[idx])
    # keep strictly increasing so every step stays reachable
    for i in range(1, len(cuts)):
        cuts[i] = max(cuts[i], cuts[i - 1] + 1)
    return cuts


def level(count: int, cuts: list[int]) -> int:
    if count <= 0:
        return 0
    for i, cut in enumerate(cuts):
        if count < cut:
            return i
    return len(cuts)


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def build_header(d, c) -> str:
    user = d["user"]
    handle = user.get("login", "")
    sub = (f"contribution distribution · trailing 365 days · "
           f"{d['timezone'].replace('_', ' ')}")
    return group([
        text(T.MARGIN, T.BANDS["header"]["y"] + 4, handle, "h1"),
        text(T.MARGIN, T.BANDS["header"]["y"] + 22, sub, "l"),
    ])


def build_stats(d, c) -> str:
    m = d["metrics"]
    yoy = d.get("yoy_pct")
    yoy_txt = "-" if yoy is None else f"{'+' if yoy >= 0 else ''}{round(yoy):g}%"

    tiles = [
        (f"{m['total']:,}", "contributions"),
        (str(m["current_streak"]), "current streak"),
        (str(m["longest_streak"]), "longest streak"),
        (str(m["busiest_day"]["count"]), "busiest day"),
        (f"{m['active_pct']:g}%", "of days active"),
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


def build_calendar(d, c, cuts) -> str:
    days = d["window"]["days"]
    if not days:
        return ""
    cal_x = T.MARGIN + T.DAY_LABEL_W
    grid_y = T.BANDS["grid"]["y"]
    offset = days[0]["weekday"]
    out = []

    # Month labels sit at the column holding that month's 1st. Keying off the
    # 1st (rather than the first day seen) means the partial month the window
    # opens in gets no label - otherwise the year reads as Aug ... Aug.
    for i, day in enumerate(days):
        _, mth, dom = day["date"].split("-")
        if dom != "01":
            continue
        col = (i + offset) // 7
        out.append(text(cal_x + col * T.PITCH,
                        T.BANDS["months"]["y"], MONTH_NAMES[int(mth) - 1], "l"))

    # weekday labels - Mon/Wed/Fri only, per the brief
    for row in (1, 3, 5):
        out.append(text(cal_x - 8, grid_y + row * T.PITCH + T.CELL - 2,
                        WEEKDAY_NAMES[row], "l", anchor="end"))

    for i, day in enumerate(days):
        slot = i + offset
        col, row = slot // 7, slot % 7
        lvl = level(day["count"], cuts)
        fill = c["empty"] if lvl == 0 else c["ramp"][lvl - 1]
        out.append(rect(cal_x + col * T.PITCH, grid_y + row * T.PITCH,
                        T.CELL, T.CELL, fill))

    # Legend, right-aligned so "More" ends exactly on the content edge - the
    # swatch run is inset by the reserved end-label widths rather than hung off
    # the grid's right edge, which used to push "More" past the margin.
    ly = T.BANDS["legend"]["y"]
    right = T.MARGIN + T.CONTENT_W
    swatches = T.LEGEND_STEPS + 1
    lw = swatches * T.PITCH - T.GUTTER
    sw_right = right - T.LEGEND_LABEL_W - T.LEGEND_LABEL_GAP
    sw_left = sw_right - lw
    baseline = ly + T.CELL - 2

    out.append(text(sw_left - T.LEGEND_LABEL_GAP, baseline, "Less", "l",
                    anchor="end"))
    for i in range(swatches):
        fill = c["empty"] if i == 0 else c["ramp"][i - 1]
        out.append(rect(sw_left + i * T.PITCH, ly, T.CELL, T.CELL, fill))
    out.append(text(sw_right + T.LEGEND_LABEL_GAP, baseline, "More", "l"))
    return group(out)


def build_momentum(d, c) -> str:
    days = d["window"]["days"]
    roll = d["metrics"]["rolling7"]
    if not days or not roll:
        return ""
    cal_x = T.MARGIN + T.DAY_LABEL_W
    offset = days[0]["weekday"]
    band = T.BANDS["momentum"]
    top, base = band["y"], band["y"] + band["h"]
    peak = max(roll) or 1

    def px(i):
        return cal_x + ((i + offset) / 7) * T.PITCH + T.CELL / 2

    def py(v):
        return base - (v / peak) * band["h"]

    pts = [(px(i), py(v)) for i, v in enumerate(roll)]
    line = "M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts)
    area = (f"M{f(pts[0][0])},{f(base)} L"
            + " L".join(f"{f(x)},{f(y)}" for x, y in pts)
            + f" L{f(pts[-1][0])},{f(base)} Z")

    out = [
        f'<line x1="{f(cal_x)}" y1="{f(base)}" x2="{f(cal_x + T.CAL_W)}" '
        f'y2="{f(base)}" class="rule"/>',
        f'<path d="{area}" fill="{c["ramp"][0]}" fill-opacity="0.30"/>',
        f'<path d="{line}" fill="none" stroke="{c["ramp"][3]}" '
        f'stroke-width="{T.STROKE_LINE}" stroke-linejoin="round" '
        f'stroke-linecap="round"/>',
        # One label, left-aligned. A second right-anchored label here collided
        # with the calendar legend, which shares this line.
        text(cal_x, top - 4,
             f"7-day rolling average · peak {round(peak, 1):g}/day", "l"),
    ]
    return group(out)


def build_weekday(d, c) -> str:
    totals = d["metrics"]["weekday_totals"]
    x0 = T.MARGIN
    band = T.BANDS["panels"]
    width = T.PANEL_W[0]
    label_w, value_w = 30, 34
    bar_max = width - label_w - value_w - 12
    peak = max(totals) or 1

    out = [text(x0, band["y"] + 8, "BY WEEKDAY", "cap")]
    # Monday-first reads better than GitHub's Sunday-first for a work pattern
    order = [1, 2, 3, 4, 5, 6, 0]
    for row, wd in enumerate(order):
        y = band["y"] + 22 + row * 20
        value = totals[wd]
        w = (value / peak) * bar_max
        out.append(text(x0, y + T.CELL - 2, WEEKDAY_NAMES[wd], "l"))
        out.append(rect(x0 + label_w, y, max(w, 1.5), T.CELL, c["ramp"][3]))
        out.append(text(x0 + width, y + T.CELL - 2, f"{value:,}", "n",
                        anchor="end"))
    return group(out)


def build_hours(d, c) -> str:
    """The signature view: 24 columns built from the same cell as the calendar."""
    hours = d["hours"]
    hist = hours["histogram"]
    x0 = T.MARGIN + T.PANEL_W[0] + T.PANEL_GAP
    band = T.BANDS["panels"]
    baseline = band["y"] + band["h"] - 24        # bottom edge of the cells
    peak_hour = hours.get("peak_hour")
    unit = nice_unit(max(hist) if hist else 0, T.HOUR_FIELD_ROWS)

    out = []
    for h in range(T.HOUR_BUCKETS):
        x = x0 + h * T.PITCH
        count = hist[h] if h < len(hist) else 0
        cells = math.ceil(count / unit) if count else 0
        if cells == 0:
            # empty bucket still gets a mark so the axis reads continuously
            out.append(rect(x, baseline - T.CELL, T.CELL, T.CELL, c["empty"]))
            continue
        fill = c["accent"] if h == peak_hour else c["ramp"][2]
        for row in range(cells):
            y = baseline - (row + 1) * T.CELL - row * T.GUTTER
            out.append(rect(x, y, T.CELL, T.CELL, fill))

    for h in (0, 6, 12, 18):
        out.append(text(x0 + h * T.PITCH + T.CELL / 2, baseline + 14,
                        f"{h:02d}", "n", anchor="middle"))
    out.append(text(x0 + 23 * T.PITCH + T.CELL / 2, baseline + 14, "23", "n",
                    anchor="middle"))

    # Title top-left, matching the other two panels. The peak annotation lives
    # at the bottom: the tallest column reaches the top of the band, so a
    # right-anchored label up there sits right on top of it.
    out.append(text(x0, band["y"] + 8, "BY HOUR OF DAY", "cap"))

    # The peak label is right-anchored so it lands directly under the accent
    # column it names; the unit caption takes the left.
    caption = f"1 square = {unit} commit" + ("s" if unit != 1 else "")
    out.append(text(x0, baseline + 26, caption, "l"))

    if peak_hour is not None:
        peak_txt = f"Peak {peak_hour:02d}:00-{(peak_hour + 1) % 24:02d}:00"
        out.append(text(x0 + T.HOUR_W, baseline + 26, peak_txt, "cap-accent",
                        anchor="end"))
    return group(out)


def build_composition(d, c) -> str:
    comp = d["composition"]
    x0 = T.MARGIN + T.PANEL_W[0] + T.PANEL_GAP + T.PANEL_W[1] + T.PANEL_GAP
    band = T.BANDS["panels"]
    width = T.PANEL_W[2]

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

    # one stacked bar, 2px surface gaps between segments
    bar_y = band["y"] + 20
    x = x0
    for i, (_, value, fill) in enumerate(rows):
        w = (value / total) * width
        if i == len(rows) - 1:
            w = max(0.0, x0 + width - x)          # absorb rounding drift
        # 2px surface gap between segments, but a category worth 0.3% must
        # still leave a visible mark rather than collapse to nothing.
        out.append(rect(x, bar_y, max(w - T.SEG_GAP, T.SEG_MIN), T.CELL, fill))
        x += w

    for i, (label, value, fill) in enumerate(rows):
        y = bar_y + 26 + i * 19
        out.append(rect(x0, y, 8, 8, fill, r=1.5))
        out.append(text(x0 + 14, y + 8, label, "l"))
        out.append(text(x0 + width, y + 8, f"{value:,}", "n", anchor="end"))
    return group(out)


def build_footer(d, c) -> str:
    s = d.get("sampling", {})
    bits = [f"Updated {d['generated']}",
            "generated from the GitHub GraphQL API"]
    if not s.get("complete", True):
        bits.append(f"hours sampled from the {s.get('repos_sampled', 0)} "
                    f"most active of {s.get('repos_available', 0)} repositories")
    else:
        bits.append(f"hours from all {s.get('repos_sampled', 0)} repositories")
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
    h = d["hours"]
    peak = h.get("peak_hour")
    peak_txt = (f"Commits peak between {peak:02d}:00 and {(peak + 1) % 24:02d}:00 "
                f"{d['timezone']} time. " if peak is not None else "")
    busiest_wd = WEEKDAY_NAMES[m["weekday_totals"].index(max(m["weekday_totals"]))]
    return (
        f"{m['total']:,} contributions over the trailing 365 days, active on "
        f"{m['active_days']} days ({m['active_pct']:g}% of the year). "
        f"Current streak {m['current_streak']} days, longest {m['longest_streak']}. "
        f"Busiest single day {m['busiest_day']['count']} contributions on "
        f"{m['busiest_day']['date']}. Busiest weekday {busiest_wd}. {peak_txt}"
        f"Median {m['median_active']:g} contributions per active day."
    )


def render(d: dict, mode: str) -> str:
    c = T.THEMES[mode]
    cuts = thresholds([day["count"] for day in d["window"]["days"]])
    title = f"{d['user'].get('login', 'user')}'s contribution distribution"

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
        build_calendar(d, c, cuts),
        build_momentum(d, c),
        build_weekday(d, c),
        build_hours(d, c),
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
