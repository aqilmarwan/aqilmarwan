<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/contributions-dark.svg?v=b3586436eda8">
  <source media="(prefers-color-scheme: light)" srcset="./assets/contributions-light.svg?v=b3586436eda8">
  <img alt="aqilmarwan's contribution distribution" src="./assets/contributions-light.svg?v=b3586436eda8">
</picture>

---

### Hi, I'm Aqil

The graphic above is regenerated every day from the GitHub GraphQL API - the
pipeline lives in this repository, not on a third-party service.

- **Commit density** - seven weekday distributions across the 24-hour day, on
  one shared scale, so the rows are directly comparable. Built from real commit
  timestamps converted to local time, not from the contribution calendar.
- **Momentum** - 7-day rolling average across the trailing year
- **Composition** - commits, pull requests, issues, reviews

Deliberately not a calendar heatmap: a joint weekday-by-hour distribution shows
*when* the work happens, which a day-grid cannot.

Built with Python 3.11, no dependencies. See [SETUP.md](./SETUP.md) for how it
works and how to run it yourself.
