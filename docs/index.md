# india-energy-atlas

> Python client library for the [India Energy Atlas](https://energymap.in) data platform.
> Apache 2.0. Maintained by India Energy Atlas (energymap.in).

```bash
pip install india-energy-atlas
```

```python
from india_energy_atlas import AtlasClient

client = AtlasClient(api_key="iea_live_...")
df = client.get_state_demand(states=["delhi"], start="2025-01-01", end="2025-01-07")
print(df.head())
```

The Python counterpart to the auto-generated TypeScript SDK promised at [`/ies`](https://energymap.in/ies). Talks to `api.energymap.in` from a notebook, script, or downstream app.

---

## What you get

- **Typed methods** for the high-traffic Atlas datasets (`get_state_demand`, `get_fuel_mix`, `get_iex_prices`, `get_carbon_intensity`, `get_discom_metrics`, `get_frequency`).
- **Generic escape hatch** `get_dataset(...)` reaches every documented endpoint.
- **Regulatory corpus**: `search_orders` and `get_order` over CERC + 5 SERCs.
- **Async sibling** `AsyncAtlasClient` for parallel fan-out from notebooks.
- **CLI** (`iea fetch sldc_demand --out demand.csv`) for ops users and journalists who don't write Python.
- Returns **tz-aware pandas DataFrames** defaulting to `Asia/Kolkata`, with a `provenance` column matching the [`ies-ingest`](https://github.com/India-Energy-Atlas/ies-ingest) source-kind vocabulary.
- Strict typed errors: `AtlasAuthError`, `AtlasRateLimitError`, `AtlasNotFoundError`, `AtlasServerError`, `AtlasValidationError`.

---

## Sister repositories

| Repo | What it is |
|---|---|
| [`india-energy-atlas`](https://github.com/India-Energy-Atlas/india-energy-atlas) (this) | Consumer Python SDK. Talks to `api.energymap.in` from a notebook or downstream app. |
| [`ies-ingest`](https://github.com/India-Energy-Atlas/ies-ingest) | Orchestration + contract layer that pilots run *inside* their stack. |

---

## Status & roadmap

Current version: see the [CHANGELOG](https://github.com/India-Energy-Atlas/india-energy-atlas/blob/main/CHANGELOG.md). Every method ships as a small PR off the [IEA-311](https://linear.app/sayon/issue/IEA-311) parent issue.

Carbon intensity is marked **Preview** until the DUM 2026 launch (October 2026); it emits a `PreviewWarning` on first use.
