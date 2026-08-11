#!/usr/bin/env python3
"""Generate fixtures/sample.json - deterministic, deliberately awkward data.

The fixture exists so the renderer can be iterated without spending API quota,
and so the layout is exercised against the cases that actually break it:

  * a 74-day gap with no contributions at all
  * a single 40-contribution day far above the rest of the distribution
  * a weekday (Saturday) with almost nothing on it
  * two completely empty hour buckets
  * a zero-value composition category

Seeded, so the fixture is stable across regenerations.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import derive, hour_stats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
END = date(2026, 8, 11)
DAYS = 366


def build():
    rng = random.Random(20260811)
    start = END - timedelta(days=DAYS - 1)
    days = []

    for i in range(DAYS):
        day = start + timedelta(days=i)
        wd = (day.weekday() + 1) % 7          # GitHub: 0 = Sunday

        if 40 <= i < 114:                     # the long silent stretch
            count = 0
        elif wd == 6:                         # Saturday, near-dead
            count = rng.choice([0, 0, 0, 0, 1])
        elif wd == 0:                         # Sunday, quiet
            count = rng.choice([0, 0, 0, 1, 2])
        else:
            count = rng.choice([0, 0, 1, 2, 2, 3, 4, 5, 7, 9, 12])

        days.append({"date": day.isoformat(), "count": count, "weekday": wd})

    days[300]["count"] = 40                   # the outlier day

    metrics = derive(days)

    hours = [0] * 24
    shape = [3, 1, 0, 0, 0, 0, 1, 2, 5, 9, 14, 18,
             22, 26, 24, 21, 19, 16, 12, 9, 11, 17, 28, 34]
    scale = max(1, metrics["total"] // max(1, sum(shape)))
    for h, weight in enumerate(shape):
        hours[h] = weight * scale
    hours[4] = hours[5] = 0                   # explicitly empty buckets

    total = metrics["total"]
    commits = int(total * 0.62)
    private = total - commits - 9 - 3 - 0
    composition = {"commits": commits, "pull_requests": 9, "issues": 3,
                   "reviews": 0, "private": max(private, 0)}

    return {
        "schema": 1,
        "generated": END.isoformat(),
        "timezone": "Asia/Kuala_Lumpur",
        "user": {"login": "octofixture", "name": "Fixture Account",
                 "created": "2020-04-23"},
        "window": {"days": days},
        "metrics": metrics,
        "composition": composition,
        "hours": hour_stats(hours),
        "sampling": {"repos_sampled": 25, "repos_available": 49,
                     "commits_scanned": sum(hours), "complete": False},
        "per_year": {},
        "all_time": total + 1200,
        "yoy_pct": -12.4,
        "prior_365": int(total / 0.876),
    }


if __name__ == "__main__":
    out = ROOT / "fixtures" / "sample.json"
    out.parent.mkdir(exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    m = data["metrics"]
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"  {m['total']} contributions, {m['active_days']} active days, "
          f"longest gap {m['longest_gap']}, busiest {m['busiest_day']['count']}")
