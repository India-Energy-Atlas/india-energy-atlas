# Datasets

The Atlas API exposes the datasets below. Each has a typed method on `AtlasClient` (and its async sibling `AsyncAtlasClient`); for anything else, use the generic `get_dataset(...)` escape hatch.

| Dataset id | Granularity | Coverage | Method |
|---|---|---|---|
| `sldc_demand` | hourly + 15-min | 2022→ for mature states; 2024-01→ 4-min national | `get_state_demand` |
| `sldc_fuel_mix` | hourly | 2022→ | `get_fuel_mix` |
| `discom_metrics` | daily (70+ metrics) | rolling | `get_discom_metrics` |
| `carbon_intensity_hourly` | hourly per DISCOM | 2024→ (Preview) | `get_carbon_intensity` |
| `iex_clearing_prices` | 15-min block | 2022→ | `get_iex_prices` |
| `frequency_observations` | 1-sec / 1-min | rolling 1 yr | `get_frequency` |
| `regulatory_orders` | event | CERC + 5 SERCs, structured | `search_orders` / `get_order` |

For the live, machine-readable list:

```python
client.list_datasets()                       # DataFrame
client.get_dataset_metadata("sldc_demand")   # dict — schema, units, source, provenance, refresh cadence
```

## Provenance

Every demand- or fuel-mix DataFrame includes a `provenance` column whose values match the [`ies-ingest`](https://github.com/India-Energy-Atlas/ies-ingest) `source_kind` vocabulary:

- `observed` — first-party SLDC publication
- `modeled` — fill-in via the LightGBM tier-2 model
- `synthesized` — composite estimate (e.g. national from SLDC sum)
- `derived` — calculated from other observed values (e.g. carbon intensity)
- `missing` — known gap; row will not be served as `null observed`

Filter accordingly when computing aggregates that should only count observed truth.
