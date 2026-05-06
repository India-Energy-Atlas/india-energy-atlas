# Cookbook — Demand vs renewable contribution

Stack solar + wind against total demand for one state, monthly:

```python
from india_energy_atlas import AtlasClient

with AtlasClient() as client:
    fuel = client.get_fuel_mix(
        state="gujarat",
        start="2025-01-01",
        end="2025-12-31",
    )

monthly = fuel.resample("MS").sum(numeric_only=True)
monthly["renewable_mw"] = monthly["solar_mw"] + monthly["wind_mw"]
monthly["total_mw"] = monthly[
    ["coal_mw", "gas_mw", "hydro_mw", "solar_mw", "wind_mw", "nuclear_mw", "other_mw"]
].sum(axis=1)
monthly["renewable_pct"] = 100 * monthly["renewable_mw"] / monthly["total_mw"]

print(monthly[["renewable_mw", "total_mw", "renewable_pct"]].round(1))
```

Switch states by changing `state="..."`. To see all states at once, fan out with `AsyncAtlasClient` (see [Quickstart → Async fan-out](../quickstart.md#async-fan-out)).
