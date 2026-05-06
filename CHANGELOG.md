# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repo scaffold: `pyproject.toml` (hatchling), Apache 2.0 LICENSE, NOTICE, CONTRIBUTING, CODE_OF_CONDUCT.
- CI matrix (ubuntu + macOS × py3.10/3.11/3.12/3.13) with `ruff`, `mypy --strict`, and `pytest`.
- `Makefile` with `install`, `verify`, `test`, `lint`, `typecheck`, `clean` targets — same surface as `ies-ingest`.
- Pre-commit hooks: `ruff check`, `ruff format`, `mypy --strict`.
- Release workflow skeleton (PyPI Trusted Publishing — wired but not yet active).
- Placeholder `AtlasClient` class. Methods raise `NotImplementedError` until step 2+ of the IEA-311 plan lands.
- Error taxonomy: `AtlasError` (base) with `AtlasAuthError`, `AtlasRateLimitError`, `AtlasNotFoundError`, `AtlasServerError`, `AtlasValidationError`.
- Type marker `py.typed` for downstream type-checkers.
- Smoke test that proves `pip install -e .` produces an importable package with a working version string.

## [0.0.1] - 2026-05-07

Initial scaffold. Tracking issue: [IEA-311](https://linear.app/sayon/issue/IEA-311).

[Unreleased]: https://github.com/India-Energy-Atlas/india-energy-atlas/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/India-Energy-Atlas/india-energy-atlas/releases/tag/v0.0.1
