# Contributing to india-energy-atlas

Thank you for considering a contribution. This is a small, focused codebase — short PRs that do one thing well are welcome.

## Setup

```bash
git clone https://github.com/India-Energy-Atlas/india-energy-atlas
cd india-energy-atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make verify
```

Python 3.10+ required.

## Workflow

1. Open an issue first for non-trivial changes — keeps everyone aligned on scope.
2. Branch from `main`. Use a descriptive branch name (`add-tariff-method`, `fix-pagination-edge`).
3. One logical change per PR. Conventional Commits in messages (`fix(transport): respect Retry-After header on 429`).
4. Tests required for new behaviour. Bug fixes that *don't* add a regression test will be asked to.
5. `make verify` must pass locally before push. CI will run the same checks plus a 4×4 (py3.10/3.11/3.12/3.13 × ubuntu/macOS) matrix.
6. PR description names *what* changed and *why*. The "why" matters more.

## What we accept

- New typed methods that wrap a documented Atlas API endpoint, with one VCR-recorded test and one integration test (skipped without `IEA_API_KEY`).
- Bug fixes with a test that fails on `main` and passes on the PR.
- Performance improvements with a before/after benchmark in the description.
- Better error messages, especially for 4xx responses where the API returns structured detail.
- Documentation improvements — typos, clearer examples, MkDocs additions.

## What we are cautious about

- New runtime dependencies. Each one is a maintenance tax forever; argue the case in the issue. The current cap is `httpx`, `pandas`, `pyarrow`, `pydantic>=2`, `typer`, `python-dateutil`.
- Dropping `pandas`-returning methods in favour of dicts. The DataFrame-first contract is load-bearing for the notebook audience.
- Anything that claims IES certification. We never make that claim — see the README's "Positioning" section.

## Reporting security issues

Please do **not** open public issues for security vulnerabilities. Email `security@energymap.in` instead. We aim to acknowledge within 48 hours.

## Code of conduct

By participating, you agree to abide by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
