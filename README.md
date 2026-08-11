<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/contributions-dark.svg?v=ef58055ada75">
  <source media="(prefers-color-scheme: light)" srcset="./assets/contributions-light.svg?v=ef58055ada75">
  <img alt="Contribution distribution, trailing 365 days" src="./assets/contributions-light.svg?v=ef58055ada75">
</picture>

### Hi, I'm Aqil

The graphic above regenerates every day from the GitHub GraphQL API. The
pipeline lives in this repository - no third-party stat service, nothing to go
down but me.

- **Density** - one bar per day across the trailing 365 days, with a smoothed
  envelope behind it carrying the trend. The raw distribution, not a summary of
  it.
- **Composition** - commits, pull requests, issues, reviews.

Deliberately not a calendar heatmap: a time series shows the actual shape of a
year's work - the bursts, the gaps and the ramp - which a day grid flattens.

Python 3.11, standard library only. The five-step colour ramp is generated in
OKLCH with exactly even lightness steps, so it stays readable under
deuteranopia. [How it works →](./SETUP.md)
