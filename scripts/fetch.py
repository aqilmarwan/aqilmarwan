#!/usr/bin/env python3
"""GitHub GraphQL -> data/contributions.json (+ history, commit-density cache).

Standard library only. No third-party stat services - every number here comes
from GitHub's own API.

Design notes
------------
* Nothing under data/ is written until every request has succeeded, so a failed
  run leaves yesterday's good snapshot (and yesterday's SVGs) in place.
* Repository names are never persisted. The density cache is keyed by a salted
  hash of the repo's node id, so a public profile repo never leaks the name of
  a private repo.
* Output is written with sorted keys and rounded floats so that unchanged input
  produces a byte-identical file and the daily commit is a genuine no-op.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ_NAME = "Asia/Kuala_Lumpur"
API = "https://api.github.com/graphql"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MAX_HOUR_REPOS = 25          # rate-limit budget for commit-timestamp sampling
HISTORY_LOOKBACK_DAYS = 365
BATCH = 4                    # repos per batched history query
USER_AGENT = "gh-stats (github.com/aqilmarwan) contribution renderer"

# Bump when the cache layout changes; a mismatch rebuilds from scratch rather
# than silently mixing incompatible buckets.
CACHE_VERSION = 2


class FetchError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------

class Client:
    def __init__(self, token: str):
        self.token = token
        self.calls = 0
        self.rate = {}

    def query(self, query: str, variables: dict | None = None, tries: int = 5) -> dict:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        delay = 1.0
        last = None

        for attempt in range(1, tries + 1):
            req = urllib.request.Request(
                API,
                data=payload,
                headers={
                    "Authorization": f"bearer {self.token}",
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = json.loads(resp.read().decode())
                self.calls += 1
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:400]
                if exc.code == 401:
                    raise FetchError(
                        "GitHub rejected the token (401). GH_STATS_TOKEN is "
                        "missing, expired or revoked. See SETUP.md."
                    ) from exc
                if exc.code == 403 and "rate limit" in detail.lower():
                    last = f"secondary rate limit: {detail}"
                elif 500 <= exc.code < 600 or exc.code in (403, 429):
                    last = f"HTTP {exc.code}: {detail}"
                else:
                    raise FetchError(f"HTTP {exc.code} from GitHub: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if body.get("errors"):
                    msgs = "; ".join(e.get("message", "?") for e in body["errors"])
                    # a genuinely transient server-side blip is worth retrying
                    if any(w in msgs.lower() for w in ("timeout", "try again", "502")):
                        last = f"GraphQL error: {msgs}"
                    else:
                        raise FetchError(f"GraphQL error: {msgs}")
                else:
                    data = body.get("data") or {}
                    if isinstance(data.get("rateLimit"), dict):
                        self.rate = data["rateLimit"]
                    return data

            if attempt < tries:
                sleep = delay + random.uniform(0, 0.4)
                print(f"  retry {attempt}/{tries - 1} in {sleep:.1f}s - {last}",
                      file=sys.stderr)
                time.sleep(sleep)
                delay *= 2

        raise FetchError(f"gave up after {tries} attempts: {last}")


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

Q_PROFILE = """
query {
  viewer {
    id
    login
    name
    createdAt
    contributionsCollection { contributionYears }
  }
  rateLimit { limit cost remaining resetAt }
}
"""

Q_WINDOW = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository { id nameWithOwner isPrivate }
        contributions { totalCount }
      }
    }
  }
  rateLimit { limit cost remaining resetAt }
}
"""

Q_REPOS = """
query($cursor: String) {
  viewer {
    repositories(
      first: 50, after: $cursor, isFork: false,
      ownerAffiliations: [OWNER, COLLABORATOR],
      orderBy: { field: PUSHED_AT, direction: DESC }
    ) {
      pageInfo { hasNextPage endCursor }
      nodes { id nameWithOwner isPrivate isArchived pushedAt
              defaultBranchRef { name } }
    }
  }
  rateLimit { limit cost remaining resetAt }
}
"""


def _history_fragment(alias: str, idx: int) -> str:
    return f"""
  {alias}: repository(owner: $o{idx}, name: $n{idx}) {{
    defaultBranchRef {{
      target {{
        ... on Commit {{
          history(author: {{ id: $author }}, since: $s{idx}, first: 100, after: $c{idx}) {{
            pageInfo {{ hasNextPage endCursor }}
            nodes {{ committedDate }}
          }}
        }}
      }}
    }}
  }}"""


def build_history_query(n: int) -> str:
    """Each repo carries its OWN `since`. Sharing one cutoff across the batch
    would re-deliver commits an up-to-date repo had already contributed, and
    they would be counted into the hour buckets a second time."""
    params = ["$author: ID!"]
    for i in range(n):
        params += [f"$o{i}: String!", f"$n{i}: String!",
                   f"$s{i}: GitTimestamp!", f"$c{i}: String"]
    body = "".join(_history_fragment(f"r{i}", i) for i in range(n))
    return (f"query({', '.join(params)}) {{{body}\n"
            "  rateLimit { limit cost remaining resetAt }\n}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def repo_key(node_id: str) -> str:
    """Stable, non-reversible key so private repo names never reach data/."""
    return hashlib.sha256(f"gh-stats/{node_id}".encode()).hexdigest()[:16]


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# derived metrics
# ---------------------------------------------------------------------------

def derive(days: list[dict]) -> dict:
    """days: [{date, count, weekday}] ordered oldest -> newest."""
    counts = [d["count"] for d in days]
    active = [c for c in counts if c > 0]

    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)

    # Current streak counts back from the most recent day. Today is excluded
    # when it is still empty - a day in progress must not break a live streak.
    current = 0
    for i in range(len(counts) - 1, -1, -1):
        if counts[i] > 0:
            current += 1
        elif i == len(counts) - 1:
            continue
        else:
            break

    longest_gap = gap = 0
    for c in counts:
        gap = gap + 1 if c == 0 else 0
        longest_gap = max(longest_gap, gap)

    busiest = max(days, key=lambda d: d["count"]) if days else {"date": None, "count": 0}

    weekday = [0] * 7
    for d in days:
        weekday[d["weekday"]] += d["count"]

    rolling, window = [], []
    for c in counts:
        window.append(c)
        if len(window) > 7:
            window.pop(0)
        rolling.append(round(sum(window) / len(window), 2))

    return {
        "total": sum(counts),
        "days_tracked": len(days),
        "active_days": len(active),
        "active_pct": round(100 * len(active) / len(days), 1) if days else 0.0,
        "current_streak": current,
        "longest_streak": longest,
        "longest_gap": longest_gap,
        "busiest_day": {"date": busiest["date"], "count": busiest["count"]},
        "median_active": round(statistics.median(active), 1) if active else 0.0,
        "mean_active": round(statistics.fmean(active), 2) if active else 0.0,
        "weekday_totals": weekday,
        "rolling7": rolling,
    }


def density_stats(matrix: list[list[int]]) -> dict:
    """matrix[weekday][hour], weekday 0 = Sunday to match the GitHub calendar."""
    hours = [sum(matrix[wd][h] for wd in range(7)) for h in range(24)]
    weekdays = [sum(row) for row in matrix]
    total = sum(hours)

    peak_hour = max(range(24), key=lambda h: hours[h]) if total else None
    peak_weekday = max(range(7), key=lambda wd: weekdays[wd]) if total else None

    # the single busiest weekday/hour intersection - the thing a joint
    # distribution can show that two separate marginals cannot
    peak_cell = None
    if total:
        wd, h = max(((w, x) for w in range(7) for x in range(24)),
                    key=lambda c: matrix[c[0]][c[1]])
        peak_cell = {"weekday": wd, "hour": h, "count": matrix[wd][h]}

    block = None
    if total:
        best = max(range(24), key=lambda s: sum(hours[(s + k) % 24] for k in range(4)))
        block = {"start": best, "end": (best + 4) % 24,
                 "count": sum(hours[(best + k) % 24] for k in range(4))}

    return {
        "matrix": matrix,
        "histogram": hours,
        "weekday_totals": weekdays,
        "total": total,
        "peak_hour": peak_hour,
        "peak_weekday": peak_weekday,
        "peak_cell": peak_cell,
        "peak_block": block,
    }


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------

def collect_commit_density(client: Client, viewer_id: str, repos: list[dict],
                           cache: dict, tz: ZoneInfo,
                           now: datetime) -> tuple[list[list[int]], dict]:
    """Incrementally pull commit timestamps into a weekday x hour density.

    The cache stores per-repo {watermark, months:{'YYYY-MM': {'wd,h': n}}} so
    each run only asks for commits newer than the last one it banked. The
    month buckets are sparse dicts because most of the 168 cells are empty,
    and they keep the trailing-year window computable without storing raw
    commits.
    """
    floor = iso_z(now - timedelta(days=HISTORY_LOOKBACK_DAYS + 35))
    pending = []
    for r in repos:
        key = repo_key(r["id"])
        entry = cache.setdefault(key, {"watermark": floor, "months": {}})
        owner, _, name = r["nameWithOwner"].partition("/")
        # `since` is inclusive, so step one second past the last commit we
        # already banked - otherwise it comes back and is counted twice.
        resume = (datetime.strptime(entry["watermark"], "%Y-%m-%dT%H:%M:%SZ")
                  .replace(tzinfo=timezone.utc) + timedelta(seconds=1))
        pending.append({"key": key, "owner": owner, "name": name,
                        "since": iso_z(resume), "cursor": None})

    newest = {p["key"]: cache[p["key"]]["watermark"] for p in pending}
    scanned = 0

    while pending:
        batch, pending = pending[:BATCH], pending[BATCH:]
        variables = {"author": viewer_id}
        for i, p in enumerate(batch):
            variables[f"o{i}"] = p["owner"]
            variables[f"n{i}"] = p["name"]
            variables[f"s{i}"] = p["since"]
            variables[f"c{i}"] = p["cursor"]

        data = client.query(build_history_query(len(batch)), variables)

        for i, p in enumerate(batch):
            repo = (data.get(f"r{i}") or {})
            ref = repo.get("defaultBranchRef") or {}
            target = ref.get("target") or {}
            hist = target.get("history")
            if not hist:
                continue

            months = cache[p["key"]]["months"]
            for node in hist.get("nodes") or []:
                stamp = node["committedDate"]
                local = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ") \
                    .replace(tzinfo=timezone.utc).astimezone(tz)
                bucket = months.setdefault(local.strftime("%Y-%m"), {})
                # isoweekday(): Mon=1..Sun=7 -> GitHub's Sun=0..Sat=6
                wd = local.isoweekday() % 7
                cell = f"{wd},{local.hour}"
                bucket[cell] = bucket.get(cell, 0) + 1
                scanned += 1
                if stamp > newest[p["key"]]:
                    newest[p["key"]] = stamp

            info = hist.get("pageInfo") or {}
            if info.get("hasNextPage"):
                pending.append({**p, "cursor": info.get("endCursor")})

    for key, water in newest.items():
        cache[key]["watermark"] = water

    # window the cached months down to the trailing year
    cutoff = (now.astimezone(tz) - timedelta(days=HISTORY_LOOKBACK_DAYS)).strftime("%Y-%m")
    matrix = [[0] * 24 for _ in range(7)]
    for entry in cache.values():
        for month, cells in entry["months"].items():
            if month < cutoff:
                continue
            for cell, count in cells.items():
                wd, hour = cell.split(",")
                matrix[int(wd)][int(hour)] += count

    return matrix, {"repos_sampled": len(repos), "commits_scanned": scanned}


def main() -> int:
    token = os.environ.get("GH_STATS_TOKEN", "").strip()
    if not token:
        print(
            "error: GH_STATS_TOKEN is not set.\n"
            "  In Actions: add it under Settings > Secrets and variables > Actions.\n"
            "  Locally:    put GH_STATS_TOKEN=ghp_... in .env (see SETUP.md).\n"
            "Refusing to render a graph of zeros.",
            file=sys.stderr,
        )
        return 2

    tz = ZoneInfo(TZ_NAME)
    client = Client(token)
    now = datetime.now(timezone.utc)

    print("-> profile")
    profile = client.query(Q_PROFILE)["viewer"]
    viewer_id, login = profile["id"], profile["login"]
    years = sorted(profile["contributionsCollection"]["contributionYears"])
    print(f"   {login} - contribution years {years[0]}..{years[-1]}")

    print("-> trailing 365 days")
    window = client.query(Q_WINDOW, {
        "from": iso_z(now - timedelta(days=HISTORY_LOOKBACK_DAYS)),
        "to": iso_z(now),
    })["viewer"]["contributionsCollection"]

    days = [
        {"date": d["date"], "count": d["contributionCount"], "weekday": d["weekday"]}
        for week in window["contributionCalendar"]["weeks"]
        for d in week["contributionDays"]
    ]
    metrics = derive(days)

    print("-> per-year totals")
    per_year = {}
    for year in years:
        y = client.query(Q_WINDOW, {
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        })["viewer"]["contributionsCollection"]
        per_year[str(year)] = {
            "total": y["contributionCalendar"]["totalContributions"],
            "commits": y["totalCommitContributions"],
            "restricted": y["restrictedContributionsCount"],
        }

    print("-> repositories for hour sampling")
    repos, cursor = [], None
    while True:
        page = client.query(Q_REPOS, {"cursor": cursor})["viewer"]["repositories"]
        repos.extend(n for n in page["nodes"] if n.get("defaultBranchRef"))
        if not page["pageInfo"]["hasNextPage"] or len(repos) >= 200:
            break
        cursor = page["pageInfo"]["endCursor"]

    # repos with commits in the window rank first, then most-recently-pushed
    committed = {
        r["repository"]["id"]: r["contributions"]["totalCount"]
        for r in window["commitContributionsByRepository"]
    }
    repos.sort(key=lambda r: (committed.get(r["id"], 0), r["pushedAt"] or ""),
               reverse=True)
    selected = repos[:MAX_HOUR_REPOS]
    print(f"   {len(repos)} candidates, sampling {len(selected)}")

    cache_path = DATA / "commit-density-cache.json"
    stored = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if stored.get("version") != CACHE_VERSION:
        if stored:
            print(f"   cache schema changed -> rebuilding from scratch")
        stored = {"version": CACHE_VERSION, "repos": {}}
    cache = stored["repos"]

    print("-> commit timestamps")
    matrix, sampling = collect_commit_density(client, viewer_id, selected,
                                              cache, tz, now)
    print(f"   {sampling['commits_scanned']} new commits across "
          f"{sampling['repos_sampled']} repos")

    typed = {
        "commits": window["totalCommitContributions"],
        "pull_requests": window["totalPullRequestContributions"],
        "issues": window["totalIssueContributions"],
        "reviews": window["totalPullRequestReviewContributions"],
        "private": window["restrictedContributionsCount"],
    }
    residual = metrics["total"] - sum(typed.values())
    if residual > 0:
        typed["other"] = residual

    today = now.astimezone(tz).date()

    # Year-over-year compares the trailing 365 days against the 365 before it.
    # Calendar-year totals would pit a part-finished year against a whole one
    # and flatter the number badly.
    print("-> prior 365 days (for year-over-year)")
    prior = client.query(Q_WINDOW, {
        "from": iso_z(now - timedelta(days=2 * HISTORY_LOOKBACK_DAYS)),
        "to": iso_z(now - timedelta(days=HISTORY_LOOKBACK_DAYS)),
    })["viewer"]["contributionsCollection"]
    prior_total = prior["contributionCalendar"]["totalContributions"]
    yoy = (round(100 * (metrics["total"] - prior_total) / prior_total, 1)
           if prior_total else None)

    snapshot = {
        "schema": 1,
        "generated": today.isoformat(),
        "timezone": TZ_NAME,
        "user": {"login": login, "name": profile.get("name"),
                 "created": profile["createdAt"][:10]},
        "window": {"days": days},
        "metrics": metrics,
        "composition": typed,
        "density": density_stats(matrix),
        "sampling": {**sampling, "repos_available": len(repos),
                     "complete": len(selected) >= len(repos)},
        "per_year": per_year,
        "all_time": sum(v["total"] for v in per_year.values()),
        "yoy_pct": yoy,
        "prior_365": prior_total,
    }

    # ---- everything succeeded; only now do we touch data/ -----------------
    DATA.mkdir(exist_ok=True)

    history_path = DATA / "history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    history = [h for h in history if h["date"] != snapshot["generated"]]
    history.append({
        "date": snapshot["generated"],
        "total_365": metrics["total"],
        "active_days": metrics["active_days"],
        "current_streak": metrics["current_streak"],
        "longest_streak": metrics["longest_streak"],
        "all_time": snapshot["all_time"],
    })
    history.sort(key=lambda h: h["date"])

    for path, obj in ((DATA / "contributions.json", snapshot),
                      (history_path, history),
                      (cache_path, stored)):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
        tmp.replace(path)

    rate = client.rate or {}
    print(f"\nok - {client.calls} API calls, rate limit "
          f"{rate.get('remaining', '?')}/{rate.get('limit', '?')} remaining "
          f"(resets {rate.get('resetAt', '?')})")
    print(f"   {metrics['total']} contributions, {metrics['active_days']} active days, "
          f"streak {metrics['current_streak']} (longest {metrics['longest_streak']})")
    if typed.get("private"):
        print(f"   note: {typed['private']} contributions are private/undisclosed - "
              "enable Settings > Public profile > 'Include private contributions' "
              "for a full breakdown")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("data/ and assets/ left untouched.", file=sys.stderr)
        sys.exit(1)
