# india-energy-atlas

> Python client library for the [India Energy Atlas](https://energymap.in) data platform. Apache 2.0. Maintained by India Energy Atlas (energymap.in).

```bash
pip install india-energy-atlas
```

```python
from india_energy_atlas import AtlasClient

client = AtlasClient(api_key="iea_live_...")
df = client.get_state_demand(states=["delhi"], start="2025-01-01", end="2025-01-07")
print(df.head())
```

This is the **consumer SDK** for the Atlas API at `api.energymap.in`. It is the Python counterpart to the auto-generated TypeScript SDK promised at [`/ies`](https://energymap.in/ies).

> **Status: scaffold only (v0.0.1).** The package installs and imports. Most methods raise `NotImplementedError`. Real method implementations land in follow-on PRs tracked from [IEA-311](https://linear.app/sayon/issue/IEA-311). Watch the [CHANGELOG](CHANGELOG.md) for v0.1.0 — the first real release.

---

## Sister repositories

| Repo | What it is |
|---|---|
| [`india-energy-atlas`](https://github.com/India-Energy-Atlas/india-energy-atlas) (this) | Consumer Python SDK. Talks to `api.energymap.in` from a notebook or downstream app. |
| [`ies-ingest`](https://github.com/India-Energy-Atlas/ies-ingest) | Orchestration + contract layer that pilots run *inside* their stack. Different audience. |

---

## Quick start (local development)

```bash
git clone https://github.com/India-Energy-Atlas/india-energy-atlas
cd india-energy-atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make verify
```

Python 3.10+ required. `make verify` runs `ruff`, `mypy --strict`, and `pytest` — the same checks CI runs.

---

## Authentication model

Aligned with what the public [`/ies` page](https://energymap.in/ies) commits to:

- **Default tier**: API key required, free, generous community quota.
- **Pro tier**: auto-promoted for `.gov.in`, `.ac.in`, and partner-utility email domains at signup. Same key, no rate limits.
- **Public CSV downloads**: continue to need *no* key.

Key resolution order, highest precedence first:

1. Explicit `AtlasClient(api_key="...")`
2. `$IEA_API_KEY` environment variable
3. `~/.config/india-energy-atlas/credentials` (TOML)
4. Unauthenticated (public datasets only)

---

## Roadmap (one PR per row)

Tracked from [IEA-311](https://linear.app/sayon/issue/IEA-311):

1. [x] Repo scaffold + `pyproject.toml` + Apache 2.0 + CI skeleton.
2. [ ] Transport layer (`httpx`, auth, retry, error taxonomy) + VCR fixtures.
3. [ ] `list_datasets` / `get_dataset_metadata` / generic `get_dataset` (escape hatch).
4. [ ] Typed methods for `sldc_demand`, `sldc_fuel_mix`, `iex_clearing_prices`.
5. [ ] Carbon intensity + DISCOM metrics + frequency.
6. [ ] Regulatory orders (`search_orders`, `get_order`).
7. [ ] Async sibling (`AsyncAtlasClient`).
8. [ ] Typer CLI (`iea ...`).
9. [ ] Docs site at `https://india-energy-atlas.github.io/india-energy-atlas/`.
10. [ ] PyPI release (v0.1.0).

---

## Positioning — what this library is and is not

| | This package IS | This package is NOT |
|---|---|---|
| Identity | A consumer SDK published by India Energy Atlas (energymap.in) | The India Energy Stack (IES) — that is the Government of India programme led by REC Limited |
| Status | Apache 2.0, no certification | An IES-certified component |
| Authority | We publish a client; we do not speak for IES | The IES specification, signatory, or conformance authority |
| Use of the IES name | "Talks to an IES-shaped API" with v0.4 page references where relevant | "IES-compliant" or "IES-certified" |

**We never claim to be IES, speak for IES, or certify anything as IES-compliant.**

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: open an issue first for non-trivial changes, branch from `main`, one logical change per PR, `make verify` must pass.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Licence

- Code: **Apache License 2.0** — see [LICENSE](LICENSE).
- Documentation in this repo: **CC-BY 4.0**.
- Original copyright: India Energy Atlas (energymap.in), 2026.

See [NOTICE](NOTICE) for attribution.
