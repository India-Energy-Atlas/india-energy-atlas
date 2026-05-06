# Quickstart

## Install

```bash
pip install india-energy-atlas
```

Python 3.10+ required.

## Authenticate

The SDK resolves the API key in this order:

1. Explicit `AtlasClient(api_key="...")`
2. `$IEA_API_KEY` environment variable
3. `~/.config/india-energy-atlas/credentials` (TOML)
4. Unauthenticated (public datasets only)

Pro tier (`.gov.in`, `.ac.in`, partner-utility domains) is auto-promoted on signup; same key, no rate limits.

## First call

```python
from india_energy_atlas import AtlasClient

with AtlasClient() as client:
    df = client.get_state_demand(
        states=["delhi", "maharashtra", "tamil-nadu"],
        start="2025-01-01",
        end="2025-12-31",
        granularity="hourly",
    )

print(df.head())
print(df.dtypes)
```

The DataFrame has a tz-aware DatetimeIndex (default `Asia/Kolkata`) and a `provenance` column (`observed | modeled | synthesized | derived | missing`).

## Common patterns

### Filter on a column

```python
df = client.get_dataset(
    "sldc_demand",
    start="2025-01-01",
    end="2025-01-31",
    filter_column="state",
    filter_operator="in",
    filter_value=["delhi", "punjab"],
)
```

### Cap rows

```python
df = client.get_dataset("sldc_demand", limit=10_000)
```

### Switch timezone

```python
df = client.get_state_demand(states=["delhi"], start=..., end=..., tz="UTC")
```

### Errors

```python
from india_energy_atlas import AtlasError, AtlasRateLimitError, AtlasAuthError

try:
    df = client.get_state_demand(states=["delhi"], start="2025-01-01", end="2025-12-31")
except AtlasAuthError:
    print("Bad or missing API key")
except AtlasRateLimitError as e:
    print(f"Slow down: {e}")
except AtlasError as e:
    print(f"Other Atlas failure: {e}")
```

### Async fan-out

```python
import asyncio
from india_energy_atlas import AsyncAtlasClient

STATES = ["delhi", "maharashtra", "tamil-nadu", "punjab", "karnataka"]

async def main():
    async with AsyncAtlasClient() as client:
        dfs = await asyncio.gather(*(
            client.get_state_demand([s], start="2025-01-01", end="2025-01-07")
            for s in STATES
        ))
    return dfs

dfs = asyncio.run(main())
```

### CLI

```bash
iea datasets
iea metadata sldc_demand
iea fetch sldc_demand --start 2025-01-01 --end 2025-01-07 --out delhi.csv \
    --filter-column state --filter-operator = --filter-value delhi
```
