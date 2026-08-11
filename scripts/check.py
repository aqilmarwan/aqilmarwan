#!/usr/bin/env python3
"""Assertions for the things that are easy to break silently.

Run with `make check`. Covers the acceptance criteria that can be tested
mechanically: determinism, size budget, accessibility attributes, coordinate
precision, the perceptual evenness of the ramp, and the empty states.
"""

from __future__ import annotations

import json
import re
import sys
import xml.dom.minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as R          # noqa: E402
import theme as T           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_KB = 250
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


# --------------------------------------------------------------------------
# colour maths (sRGB -> OKLab), so the ramp claims are verified not asserted
# --------------------------------------------------------------------------

M1 = [[0.4122214708, 0.5363325363, 0.0514459929],
      [0.2119034982, 0.6806995451, 0.1073969566],
      [0.0883024619, 0.2817188376, 0.6299787005]]
M2 = [[0.2104542553, 0.7936177850, -0.0040720468],
      [1.9779984951, -2.4285922050, 0.4505937099],
      [0.0259040371, 0.7827717662, -0.8086757660]]


def _lin(u: float) -> float:
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4


def _mul(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def oklab(hx: str) -> tuple[float, float, float]:
    hx = hx.lstrip("#")
    rgb = [_lin(int(hx[i:i + 2], 16) / 255) for i in (0, 2, 4)]
    lms = [(x ** (1 / 3)) if x >= 0 else -((-x) ** (1 / 3)) for x in _mul(M1, rgb)]
    L, a, b = _mul(M2, lms)
    return L, a, b


def oklab_L(hx: str) -> float:
    return oklab(hx)[0]


def contrast(a: str, b: str) -> float:
    def lum(hx):
        hx = hx.lstrip("#")
        c = [_lin(int(hx[i:i + 2], 16) / 255) for i in (0, 2, 4)]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    x, y = lum(a), lum(b)
    hi, lo = max(x, y), min(x, y)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------

def main() -> int:
    data_path = ROOT / "data" / "contributions.json"
    fixture_path = ROOT / "fixtures" / "sample.json"
    source = data_path if data_path.exists() else fixture_path
    if not source.exists():
        print("error: no data/contributions.json and no fixtures/sample.json",
              file=sys.stderr)
        return 1
    data = json.loads(source.read_text())

    print(f"\ntheme ({source.name})")
    for mode in ("light", "dark"):
        c = T.THEMES[mode]

        # The 5-step intensity scale. Kept as a loop so a second ramp can be
        # added back without restructuring the block.
        for name in ("ramp",):
            ramp = c[name]
            ls = [oklab_L(h) for h in ramp]
            deltas = [abs(ls[i + 1] - ls[i]) for i in range(len(ls) - 1)]
            faintest = min(ramp, key=lambda h: contrast(h, c["surface"]))

            check(f"{mode}/{name}: lightness monotone",
                  ls == sorted(ls) or ls == sorted(ls, reverse=True),
                  f"L {' '.join(f'{v:.3f}' for v in ls)}")
            check(f"{mode}/{name}: steps perceptually even",
                  max(deltas) - min(deltas) < 0.02,
                  f"dL spread {max(deltas) - min(deltas):.4f}")
            check(f"{mode}/{name}: every step >= 0.06 dL apart",
                  min(deltas) >= 0.06, f"min {min(deltas):.3f}")
            check(f"{mode}/{name}: faintest step separates from surface",
                  contrast(faintest, c["surface"]) >= 2.0,
                  f"{contrast(faintest, c['surface']):.2f}:1")

    print("\noutput")
    svgs = {mode: R.render(data, mode) for mode in ("light", "dark")}
    for mode, svg in svgs.items():
        kb = len(svg.encode()) / 1024
        check(f"{mode}: under {MAX_KB} KB", kb < MAX_KB, f"{kb:.1f} KB")
        try:
            xml.dom.minidom.parseString(svg)
            check(f"{mode}: well-formed XML", True)
        except Exception as exc:                      # noqa: BLE001
            check(f"{mode}: well-formed XML", False, str(exc))
        check(f"{mode}: has role/title/desc",
              'role="img"' in svg and "<title" in svg and "<desc" in svg)
        check(f"{mode}: no script or animation",
              "<script" not in svg and "<animate" not in svg)
        check(f"{mode}: coordinates rounded to 2dp",
              not re.search(r"-?\d+\.\d{3,}", svg))
        check(f"{mode}: deterministic", R.render(data, mode) == svg)

    print("\nempty states")
    blank = {
        "schema": 1, "generated": "2026-01-01", "timezone": "Asia/Kuala_Lumpur",
        "user": {"login": "newcomer", "name": None, "created": "2026-01-01"},
        "window": {"days": []},
        "metrics": {"total": 0, "days_tracked": 0, "active_days": 0,
                    "active_pct": 0.0, "current_streak": 0, "longest_streak": 0,
                    "longest_gap": 0, "busiest_day": {"date": None, "count": 0},
                    "median_active": 0.0, "mean_active": 0.0,
                    "weekday_totals": [0] * 7, "rolling7": []},
        "composition": {"commits": 0, "pull_requests": 0, "issues": 0,
                        "reviews": 0, "private": 0},
        "density": {"matrix": [[0] * 24 for _ in range(7)],
                    "histogram": [0] * 24, "weekday_totals": [0] * 7,
                    "total": 0, "peak_hour": None, "peak_weekday": None,
                    "peak_cell": None, "peak_block": None},
        "sampling": {"repos_sampled": 0, "repos_available": 0,
                     "commits_scanned": 0, "complete": True},
        "per_year": {}, "all_time": 0, "yoy_pct": None, "prior_365": 0,
    }
    try:
        for mode in ("light", "dark"):
            xml.dom.minidom.parseString(R.render(blank, mode))
        check("brand-new account with no history renders", True)
    except Exception as exc:                          # noqa: BLE001
        check("brand-new account with no history renders", False, str(exc))

    if fixture_path.exists():
        fx = json.loads(fixture_path.read_text())
        try:
            for mode in ("light", "dark"):
                xml.dom.minidom.parseString(R.render(fx, mode))
            check("messy fixture renders", True,
                  f"gap {fx['metrics']['longest_gap']}d, "
                  f"peak day {fx['metrics']['busiest_day']['count']}")
        except Exception as exc:                      # noqa: BLE001
            check("messy fixture renders", False, str(exc))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
