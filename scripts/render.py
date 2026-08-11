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
from datetime import date
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
# helpers
# ---------------------------------------------------------------------------

def smooth(values, kernel):
    """Circular weighted smoothing - the series is a year, so the ends are not
    joined; edges clamp to the nearest real value instead of wrapping."""
    n = len(values)
    if not n:
        return []
    half = len(kernel) // 2
    total = sum(kernel)
    out = []
    for i in range(n):
        acc = 0.0
        for k, w in enumerate(kernel):
            j = min(max(i + k - half, 0), n - 1)
            acc += values[j] * w
        out.append(acc / total)
    return out


def text_w(body, size, mono=False):
    """Approximate advance width - only used to pack the inline legend, and
    deterministic, which is what matters here."""
    per = T.CHAR_W_MONO if mono else T.CHAR_W_SANS
    return len(str(body)) * size * per


def relative_day(generated: str) -> str:
    """'last updated: today' / 'yesterday' / 'N days ago'.

    Deliberately day-granular. An SVG served through Camo is static, so an
    hour-granular string would freeze at build time and be wrong for the rest
    of the day; a day-granular one stays true for as long as the file is
    current.
    """
    try:
        gen = date.fromisoformat(generated)
    except (TypeError, ValueError):
        return f"last updated: {generated}"
    delta = (date.today() - gen).days
    if delta <= 0:
        return "last updated: today"
    if delta == 1:
        return "last updated: yesterday"
    return f"last updated: {delta} days ago"


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def build_density(d, c) -> str:
    """The whole graphic: one bar per day across the trailing year, with a
    smoothed envelope behind it carrying the trend."""
    days = d["window"]["days"]
    if not days:
        return ""

    counts = [day["count"] for day in days]
    base = T.DENSITY_Y + T.DENSITY_H
    peak = max(counts) or 1
    step = T.DENSITY_W / len(days)
    out = []

    def y_of(v):
        return base - (v / peak) * T.DENSITY_H

    # envelope first, behind the bars
    env = smooth([float(v) for v in counts], T.ENVELOPE_SMOOTH)
    pts = [(T.DENSITY_X + (i + 0.5) * step, y_of(v)) for i, v in enumerate(env)]
    area = (f"M{f(pts[0][0])},{f(base)} L"
            + " L".join(f"{f(x)},{f(y)}" for x, y in pts)
            + f" L{f(pts[-1][0])},{f(base)} Z")
    out.append(f'<path d="{area}" fill="{c["ramp"][0]}" fill-opacity="0.55"/>')

    # one bar per day - the raw distribution, not a summary of it
    peak_i = max(range(len(counts)), key=lambda i: counts[i])
    for i, count in enumerate(counts):
        if not count:
            continue
        h = max(base - y_of(count), T.BAR_MIN)
        out.append(rect(T.DENSITY_X + i * step, base - h,
                        max(step - T.BAR_GAP, T.BAR_MIN), h,
                        c["ramp"][4], r=0.6))

    out.append(f'<line x1="{f(T.DENSITY_X)}" y1="{f(base)}" '
               f'x2="{f(T.DENSITY_X + T.DENSITY_W)}" y2="{f(base)}" '
               f'class="rule"/>')

    # the single busiest day, in the accent that appears nowhere else
    if counts[peak_i]:
        px = T.DENSITY_X + peak_i * step + max(step - T.BAR_GAP, T.BAR_MIN) / 2
        py = y_of(counts[peak_i])
        out.append(f'<circle cx="{f(px)}" cy="{f(py - 8)}" '
                   f'r="{T.PEAK_DOT_R}" fill="{c["accent"]}"/>')
        anchor = "end" if peak_i > len(counts) * 0.85 else "middle"
        out.append(text(px, py - 16, f"{counts[peak_i]}", "cap-accent",
                        anchor=anchor))

    # month ticks, one per calendar month start
    for i, day in enumerate(days):
        _, mth, dom = day["date"].split("-")
        if dom != "01":
            continue
        x = T.DENSITY_X + i * step
        out.append(text(x, T.MONTH_AXIS_Y, MONTH_NAMES[int(mth) - 1], "l",
                        anchor="middle"))
    return group(out)


def build_composition(d, c) -> str:
    comp = d["composition"]
    x0, width = T.MARGIN, T.CONTENT_W

    # Private activity is not a *kind* of work - it is a hole in the data, so
    # it wears the neutral empty token rather than a ramp step.
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

    out = []
    x = x0
    for i, (_, value, fill) in enumerate(rows):
        w = (value / total) * width
        if i == len(rows) - 1:
            w = max(0.0, x0 + width - x)          # absorb rounding drift
        out.append(rect(x, T.COMP_Y, max(w - T.SEG_GAP, T.SEG_MIN), T.COMP_H,
                        fill))
        x += w

    # inline legend on one line, packed left to right
    size = T.TYPE["label"]["size"]
    cursor = x0
    for label, value, fill in rows:
        value_txt = f"{value:,}"
        out.append(rect(cursor, T.COMP_LABEL_Y - T.SWATCH, T.SWATCH, T.SWATCH,
                        fill, r=1.5))
        cursor += T.SWATCH + 6
        out.append(text(cursor, T.COMP_LABEL_Y, label, "l"))
        cursor += text_w(label, size) + 6
        out.append(text(cursor, T.COMP_LABEL_Y, value_txt, "n"))
        cursor += text_w(value_txt, size, mono=True) + T.LEGEND_GAP
    return group(out)


def build_footer(d, c) -> str:
    return text(T.MARGIN, T.BANDS["footer"]["y"],
                relative_day(d.get("generated", "")), "l")


# ---------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------

def stylesheet(c) -> str:
    """Only the classes the graphic still uses - the header and stats strip
    are gone, and so are their rules."""
    ty = T.TYPE
    return (
        f"text{{font-family:{T.SANS};fill:{c['ink']}}}"
        f".b{{font-size:{ty['body']['size']}px}}"
        f".l{{font-size:{ty['label']['size']}px;font-weight:{ty['label']['weight']};"
        f"letter-spacing:{ty['label']['tracking']}px;fill:{c['ink_muted']}}}"
        f".n{{font-family:{T.MONO};font-size:{ty['label']['size']}px;"
        f"font-variant-numeric:tabular-nums;fill:{c['ink_soft']}}}"
        f".cap-accent{{font-family:{T.MONO};font-size:{ty['label']['size']}px;"
        f"font-weight:600;font-variant-numeric:tabular-nums;fill:{c['accent']}}}"
        f".rule{{stroke:{c['hairline']};stroke-width:{T.STROKE_HAIRLINE}}}"
    )


def describe(d) -> str:
    """What a screen reader gets. Describes what is drawn, nothing more."""
    m = d["metrics"]
    days = d["window"]["days"]
    comp = d["composition"]

    bits = [
        f"Daily contribution distribution over the trailing 365 days, "
        f"{d['timezone'].replace('_', ' ')} time.",
        f"{m['total']:,} contributions in total, active on "
        f"{m['active_days']} of {m['days_tracked']} days "
        f"({m['active_pct']:g}%).",
    ]
    busiest = m.get("busiest_day") or {}
    if busiest.get("count"):
        bits.append(f"The busiest single day was {busiest['count']} "
                    f"contributions on {busiest['date']}.")
    if m.get("median_active"):
        bits.append(f"Median {m['median_active']:g} contributions per "
                    f"active day, longest quiet stretch "
                    f"{m.get('longest_gap', 0)} days.")

    parts = [f"{v:,} {k.replace('_', ' ')}" for k, v in (
        ("commits", comp.get("commits", 0)),
        ("pull requests", comp.get("pull_requests", 0)),
        ("issues", comp.get("issues", 0)),
        ("reviews", comp.get("reviews", 0)),
        ("private", comp.get("private", 0)),
    ) if v]
    if parts:
        bits.append("Composition: " + ", ".join(parts) + ".")
    return " ".join(bits)


def render(d: dict, mode: str) -> str:
    c = T.THEMES[mode]
    # No handle: the graphic itself carries no name, and <title> is the
    # accessible name for the same image.
    title = "Contribution distribution, trailing 365 days"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {T.CANVAS["w"]} {T.CANVAS["h"]}" '
        f'width="{T.CANVAS["w"]}" height="{T.CANVAS["h"]}" role="img" '
        f'aria-labelledby="ttl dsc">',
        f'<title id="ttl">{esc(title)}</title>',
        f'<desc id="dsc">{esc(describe(d))}</desc>',
        f"<style>{stylesheet(c)}</style>",
        rect(0, 0, T.CANVAS["w"], T.CANVAS["h"], c["surface"], r=0),
        build_density(d, c),
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
