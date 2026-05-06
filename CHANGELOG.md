# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Discovery methods** ([IEA-313](https://linear.app/sayon/issue/IEA-313)): `list_datasets()` returns the catalogue as a pandas DataFrame; `get_dataset_metadata(id)` returns schema/units/source/provenance/refresh cadence as a dict; generic `get_dataset(id, start=, end=, columns=, filter_column=, filter_operator=, filter_value=, limit=, tz=)` reaches every documented endpoint with auto-pagination, server-side filtering, and a tz-aware DatetimeIndex defaulting to `Asia/Kolkata`. 8 unit tests via respx; 33/33 total green.
- **Transport layer** ([IEA-312](https://linear.app/sayon/issue/IEA-312)): internal `_HttpxTransport` wrapping `httpx.Client`. Bearer auth from `api_key`, retry-on-5xx with exponential backoff, `Retry-After` honoured on 429, telemetry User-Agent header (off-switch via `send_telemetry=False` or `IEA_TELEMETRY=0`), cursor-pagination iterator, full status-code → exception mapping. 16 transport unit tests via `respx`.
- `AtlasClient` is now an HTTP-aware context manager (`with AtlasClient() as c:`). Methods still raise `NotImplementedError` until IEA-313 lands.
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
