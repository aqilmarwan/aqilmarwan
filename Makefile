.PHONY: dev fetch render fixture preview check clean help
.DEFAULT_GOAL := help

PY := python3
LOAD_ENV := set -a; [ -f .env ] && . ./.env; set +a

help:
	@echo "make dev      fetch live data, then render both SVGs (needs .env)"
	@echo "make fetch    refresh data/ from the GitHub API only"
	@echo "make render   rebuild assets/ from the data already on disk"
	@echo "make fixture  regenerate fixtures/sample.json, then render from it"
	@echo "make preview  render from the fixture into .preview/ (no API calls)"
	@echo "make check    determinism, size and accessibility assertions"
	@echo "make clean    remove generated previews and caches"

dev: fetch render

fetch:
	@$(LOAD_ENV); $(PY) scripts/fetch.py

render:
	@$(PY) scripts/render.py

fixture:
	@$(PY) scripts/make_fixture.py
	@$(PY) scripts/render.py --fixture --out .preview --no-stamp

# Iterate on the design without spending API quota.
preview:
	@$(PY) scripts/render.py --fixture --out .preview --no-stamp
	@echo "open .preview/contributions-light.svg"

check:
	@$(PY) scripts/check.py

clean:
	@rm -rf .preview scripts/__pycache__
