# Setup

A self-contained pipeline that turns GitHub's own API into a contribution
graphic and commits it back daily. Python 3.11, standard library only - there
is nothing to `pip install`.

```
.github/workflows/update-stats.yml   daily cron + manual dispatch
scripts/theme.py                     every design token, in one place
scripts/fetch.py                     GitHub GraphQL -> data/*.json
scripts/render.py                    data/*.json -> assets/*.svg
scripts/make_fixture.py              regenerates the offline test fixture
scripts/check.py                     determinism / a11y / palette assertions
data/contributions.json              latest normalized snapshot (committed)
data/history.json                    append-only daily rollups (committed)
data/hour-cache.json                 incremental commit-hour cache (committed)
fixtures/sample.json                 deliberately messy sample data
assets/contributions-{light,dark}.svg
```

---

## 1. Create the token

The `GITHUB_TOKEN` that Actions provides automatically authenticates as the
Actions bot, so `viewer { contributionsCollection }` would return the *bot's*
contributions - an empty graph. You need a Personal Access Token that
authenticates as you.

1. Go to **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. **Generate new token (classic)**, name it something like `gh-stats`
3. Select scopes:

   | Scope | Needed for |
   |---|---|
   | `read:user` | contribution calendar, totals, per-year history - **always required** |
   | `repo` | private-repository contributions and commit timestamps from private repos |

   This repository is configured to include private contributions, so **both
   scopes are required**. If you switch to public-only, drop `repo` and reduce
   `MAX_HOUR_REPOS` coverage accordingly.

4. Set an expiry you will actually remember. When it lapses the workflow fails
   loudly rather than publishing zeros - but it does stop updating.
5. Copy the token.

### Add it as a repository secret

**Settings → Secrets and variables → Actions → New repository secret**

- Name: `GH_STATS_TOKEN`
- Value: the token you just copied

The name matters - both the workflow and `fetch.py` look for exactly this.

---

## 2. Show your private contributions

If you have activity in private repositories, GitHub returns it as an opaque
`restrictedContributionsCount` unless you opt in. Until you do, the composition
panel shows that block in neutral grey and labels it `private`, because it is a
hole in the data rather than a category of work.

**Settings → Public profile → tick "Include private contributions on my profile"**

Turning this on makes the type breakdown (commits / PRs / issues / reviews)
reflect your real totals. Note that it also surfaces that activity on your
public profile page - that is the trade.

Hour-of-day data does **not** depend on this setting. Those timestamps come from
enumerating repositories directly with the `repo` scope, so the hour field is
accurate either way.

---

## 3. Run it locally

```bash
echo 'GH_STATS_TOKEN=ghp_your_token_here' > .env   # .env is gitignored
make dev                                            # fetch + render
```

Other targets:

```bash
make preview    # render from fixtures/sample.json - no API calls at all
make fixture    # regenerate the fixture, then preview it
make render     # re-render from data already on disk
make check      # determinism, size, accessibility and palette assertions
```

`make preview` is the one to use while iterating on design. The fixture contains
a 75-day gap, a 40-contribution outlier day, a near-dead Saturday, two empty
hour buckets and a zero-value composition category - the cases that break
layouts.

---

## 4. How the data is collected

**Trailing year, totals, per-year history** come from
`viewer.contributionsCollection` - one query for the 365-day window, one per
contribution year, and one for the preceding 365 days (year-over-year compares
trailing-365 against the prior 365; comparing calendar years would pit a
part-finished year against a whole one).

**Hour-of-day is the hard part.** The contribution calendar carries no
timestamps, so commit hours come from
`repository.defaultBranchRef.target.history(author: …)`, reading `committedDate`
off each commit and converting to `Asia/Kuala_Lumpur`.

That is rate-limit sensitive, so:

- repositories are capped at `MAX_HOUR_REPOS` (25), ranked by commits in the
  window then by most recent push
- queries are batched four repositories per request, each with its **own**
  `since` cutoff
- results are cached in `data/hour-cache.json` as per-repo, per-month
  24-bucket histograms, so each run only asks for commits newer than the last
  one it banked - a warm run scans zero commits
- the remaining rate limit is logged every run
- when coverage is partial the SVG footer says so explicitly
  ("hours sampled from the 25 most active of 49 repositories")

Repository **names are never written to `data/`**. The cache is keyed by a
salted SHA-256 of the repository node id, so a public profile repo cannot leak
the name of a private one.

### Rate limit

A cold run costs about 20 GraphQL calls out of 5,000/hour. Warm runs cost
slightly fewer. You are nowhere near the ceiling.

---

## 5. How the graphic is built

`theme.py` holds every colour, size and spacing value; `render.py` contains no
literal hex codes or bare pixel numbers.

The five-step intensity ramp is generated in **OKLCH with exactly even lightness
steps** (ΔL ≈ 0.078 light, ≈ 0.105 dark) and converted to sRGB. Even lightness
spacing is what makes it survive deuteranopia - the steps stay ordered by
lightness alone, so hue never carries the meaning. `make check` re-verifies this
from the hex values rather than taking it on trust.

The amber accent appears in exactly one place: the peak hour column. It sits
≥ 8 OKLab ΔE from every ramp step (measured at 28+), so it can never be
mistaken for an intensity level.

### SVG constraints this respects

GitHub proxies README images through Camo and renders them as `<img>`:

- **no JavaScript executes** - everything is static geometry emitted at build time
- **two files, not one media query** - `<picture>` with two `<source>` elements
  is far more reliable on GitHub than `prefers-color-scheme` inside one SVG
- CSS lives in an inline `<style>` block; no external stylesheets or font files
- `role="img"` with `<title>` and `<desc>` carrying the key numbers
- all coordinates rounded to 2dp and output kept deterministic, so unchanged
  data produces a byte-identical file and the daily commit is a genuine no-op
- ~46 KB per file, no raster images, no animation

---

## 6. The workflow

Runs at `20 16 * * *` UTC, which is **00:20 Asia/Kuala_Lumpur** - just after
local midnight, with the previous day complete. Cron in GitHub Actions is always
UTC; adjust that expression if you change timezone.

- `permissions: contents: write`, nothing more
- a concurrency group so overlapping runs cannot race the same commit
- `fetch.py` retries 5xx and secondary rate limits with exponential backoff and
  jitter, and writes `data/` only after **every** request has succeeded - a
  failed run exits non-zero leaving yesterday's good data and SVGs untouched
- the commit step is a no-op unless `data/`, `assets/` or `README.md` changed
- commits are authored as
  `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>`
  with `[skip ci]`

### Keeping the schedule alive

GitHub disables scheduled workflows after **60 days of repository inactivity**,
and commits pushed with the default `GITHUB_TOKEN` do **not** reset that timer.

This workflow avoids the problem by checking out with `GH_STATS_TOKEN`, so the
daily push is attributed to your account and counts as activity:

```yaml
- uses: actions/checkout@v4
  with:
    token: ${{ secrets.GH_STATS_TOKEN }}
```

That is why the token needs write access to this repository. If you would rather
not grant that, drop back to the default token and either run
**Actions → update contribution graph → Run workflow** manually every couple of
months, or add a separate keepalive workflow that touches a file with a PAT.

### Camo caching

Camo caches aggressively, so a fresh SVG at an unchanged URL can stay stale on
your rendered profile. `render.py` rewrites the embed URLs in `README.md` with
`?v=<hash>`, where the hash is derived from the SVG bytes. It changes only when
the image actually changes, so no-op days stay no-ops.

If the profile still looks stale, hard-refresh, or purge Camo:

```bash
curl -X PURGE "$(  # the camo.githubusercontent.com URL from the rendered page
  echo 'https://camo.githubusercontent.com/...'
)"
```

---

## 7. Troubleshooting

**`error: GH_STATS_TOKEN is not set`**
The secret is missing or misnamed. Locally, check `.env` exists and contains
`GH_STATS_TOKEN=`. The script refuses to render a graph of zeros.

**`GitHub rejected the token (401)`**
Expired or revoked. Generate a new one and update the secret.

**Numbers are lower than my profile page shows**
Almost always the private-contributions setting - see step 2. Compare
`composition.private` in `data/contributions.json` against the gap.

**Composition is mostly grey**
Same cause. That block is `restrictedContributionsCount`.

**Hour-of-day looks thin**
Check `sampling` in `data/contributions.json`. If `complete` is `false`, raise
`MAX_HOUR_REPOS` in `fetch.py` - the cache means the extra cost is paid once.

**Workflow stopped running**
The 60-day inactivity cutoff. Re-enable it under the Actions tab and see
"Keeping the schedule alive" above.

**The daily commit changes files even when nothing happened**
Run `make check` - the determinism assertion should catch it. The usual cause is
a value that varies per run (a timestamp finer than a date) leaking into the
snapshot.

---

## 8. Moving this into your profile repository

The graphic renders on your profile when it lives in the special repository
named after your account (`aqilmarwan/aqilmarwan`) with the `<picture>` block in
its `README.md`. Copy the whole tree in, add the `GH_STATS_TOKEN` secret, and
run the workflow once manually to confirm it goes green.
