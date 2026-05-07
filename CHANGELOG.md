# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-07

### Changed — pivot to live API surface ([IEA-321](https://linear.app/sayon/issue/IEA-321))

**What works now (5 live endpoints):**

- `health()` — GET `/api/health` → `{status, database, workspace}` dict.
- `list_states()` — GET `/api/states` → DataFrame of all states with `state_slug`, `state_name`, `iso_code`, `release_tier`, `build_status`, `completion_class`.
- `get_state(slug)` — GET `/api/states/{slug}` → per-state detail dict with counts, geometry, downloads.
- `get_iex_prices(market, start=, end=)` — GET `/api/intelligence/iex-market-data?market_type={DAM|RTM|GDAM|HP-DAM|SCM}`. Returns DataFrame with `mcp_inr_per_mwh` (renamed from `mcp_rs_mwh`), all MW/price columns numeric-coerced from strings. Date filtering is client-side.
- `get_carbon_intensity(state=, start=, end=)` — GET `/api/intelligence/carbon-intensity?state=`. Returns DataFrame with `gco2_per_kwh` (renamed from `carbon_intensity_gco2_kwh`). Emits `PreviewWarning`. DISCOM addressing raises `NotImplementedError` (IEA-327).

**What is deferred (raises `NotImplementedError` with tracking issue):**

| Method | Lands in |
|---|---|
| `get_state_demand` | [IEA-323](https://linear.app/sayon/issue/IEA-323) |
| `get_fuel_mix` | [IEA-324](https://linear.app/sayon/issue/IEA-324) |
| `list_datasets`, `get_dataset_metadata`, `get_dataset` | [IEA-325](https://linear.app/sayon/issue/IEA-325) |
| `get_frequency` | [IEA-326](https://linear.app/sayon/issue/IEA-326) |
| `get_discom_metrics` | [IEA-327](https://linear.app/sayon/issue/IEA-327) |
| `search_orders`, `get_order` | [IEA-328](https://linear.app/sayon/issue/IEA-328) |

**Transport / breaking changes:**

- `DEFAULT_BASE_URL` changed from `https://api.energymap.in/v1` to `https://api.energymap.in` (the `/v1` namespace does not exist on the live server).
- Pagination envelope changed from `{data, next_cursor}` (cursor-based) to `{items, count}` (single-page). The iterator interface is preserved — calling code shape is unchanged.
- `IexMarket` literals changed to uppercase: `DAM`, `RTM`, `GDAM`, `HP-DAM`, `SCM` (matching the live `market_type` query param).
- CLI: `iea datasets` now exits non-zero with a message pointing at IEA-325. `iea states` added. `iea health` added. `iea fetch carbon-intensity --state <slug> --out <file>` works.

**Previously in `[Unreleased]`** (all changes from v0.0.1 through this release):

- Docs site (IEA-319), CLI (IEA-318), AsyncAtlasClient (IEA-317), regulatory corpus (IEA-316), typed secondary methods (IEA-315), typed core methods (IEA-314), discovery methods (IEA-313), transport layer (IEA-312).

### Added

- **Docs site** ([IEA-319](https://linear.app/sayon/issue/IEA-319)): MkDocs Material site at `https://india-energy-atlas.github.io/india-energy-atlas/`. `docs/` content: hero index, quickstart, datasets table, three cookbook recipes (carbon intensity / IEX duration curve / renewable contribution), positioning page, and API reference auto-generated from docstrings via `mkdocstrings`. `.github/workflows/docs.yml` builds with `--strict` and deploys via `mkdocs gh-deploy` on every push to `main`. `mkdocs build --strict` clean locally.
- **CLI** ([IEA-318](https://linear.app/sayon/issue/IEA-318)): new `iea` console script (Typer + Rich) — `iea --help`, `iea version`, `iea datasets` (pretty Rich table), `iea metadata <dataset>` (JSON), `iea fetch <dataset> --out <path>` writes CSV / Parquet / JSONL based on suffix. Honours `--api-key` / `IEA_API_KEY` and `--base-url` / `IEA_BASE_URL`. Supports the same filter args as `get_dataset`. 8 tests via `typer.testing.CliRunner`; total 87/87 green.
- `rich>=13.7` added to runtime deps for table rendering.
- **Async sibling** ([IEA-317](https://linear.app/sayon/issue/IEA-317)): `AsyncAtlasClient` mirrors every public method on `AtlasClient` as `async`, backed by a new `_AsyncHttpxTransport` that shares retry policy / status-code mapping / telemetry helpers with the sync transport (no duplicate request logic). Async context manager (`async with AsyncAtlasClient() as c: ...`). 16 pytest-asyncio tests, including the headline `asyncio.gather(*[...])` parallel fan-out from the AC. Total 79/79 tests green.
- **Regulatory corpus** ([IEA-316](https://linear.app/sayon/issue/IEA-316)): `search_orders(body=, query=, issued_after=, issued_before=, limit=)` over CERC + 5 SERC structured orders, auto-pagination, returns DataFrame indexed by `issued_at`. `get_order(order_id)` returns the full structured payload (parties, prayer, ratio, directions). Raises `AtlasNotFoundError` for unknown ids. 7 new tests; 62/62 total green.
- **Typed methods (secondary)** ([IEA-315](https://linear.app/sayon/issue/IEA-315)): `get_carbon_intensity` (DISCOM- or state-addressable, marked Preview), `get_discom_metrics` (70+ daily metrics, optional subset filter), `get_frequency` (1sec/1min, optional region filter NR/WR/SR/ER/NER). New `PreviewWarning` exception class — emitted once per session on first use of a Preview API. 11 new tests; 56/56 total green.
- **Typed core methods** ([IEA-314](https://linear.app/sayon/issue/IEA-314)): `get_state_demand`, `get_fuel_mix`, `get_iex_prices`. All return tz-aware DataFrames defaulting to `Asia/Kolkata` with a `provenance` column matching the `ies-ingest` source-kind vocabulary. Parameter validation raises `AtlasValidationError` before the network call for: bad granularity, unknown state slug (against the canonical 32-state list), unknown IEX market, end < start. 12 new respx tests; total 46/46 green.
- Internal helpers: `_states.CANONICAL_STATES` (offline state-slug allowlist), `_validators.ensure_one_of` / `ensure_window` (shared parameter validation).
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

[Unreleased]: https://github.com/India-Energy-Atlas/india-energy-atlas/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/India-Energy-Atlas/india-energy-atlas/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/India-Energy-Atlas/india-energy-atlas/releases/tag/v0.0.1
