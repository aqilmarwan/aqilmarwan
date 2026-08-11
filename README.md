<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/contributions-dark.svg?v=f01152f5f5b7">
  <source media="(prefers-color-scheme: light)" srcset="./assets/contributions-light.svg?v=f01152f5f5b7">
  <img alt="Contribution distribution, trailing 365 days" src="./assets/contributions-light.svg?v=f01152f5f5b7">
</picture>

---

### Hi, I'm Aqil

The graphic above is regenerated every day from the GitHub GraphQL API - the
pipeline lives in this repository, not on a third-party service.

- **Density** - one bar per day across the trailing 365 days, with a smoothed
  envelope behind it carrying the trend. The raw distribution, not a summary of
  it.
- **Composition** - commits, pull requests, issues, reviews

Deliberately not a calendar heatmap: a time series shows the actual shape of a
year's work - the bursts, the gaps and the ramp - which a day-grid flattens.

Built with Python 3.11, no dependencies. See [SETUP.md](./SETUP.md) for how it
works and how to run it yourself.
