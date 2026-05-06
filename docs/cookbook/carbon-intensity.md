# Cookbook — Carbon intensity over time

Plot one DISCOM's hourly carbon intensity for a month.

```python
from india_energy_atlas import AtlasClient
import matplotlib.pyplot as plt

with AtlasClient() as client:
    df = client.get_carbon_intensity(
        discom="bses-rajdhani",
        start="2025-06-01",
        end="2025-07-01",
    )

fig, ax = plt.subplots(figsize=(12, 4))
df["gco2_per_kwh"].plot(ax=ax, alpha=0.7)
df["gco2_per_kwh"].rolling("24h").mean().plot(ax=ax, linewidth=2, label="24h rolling")
ax.set_ylabel("gCO₂ / kWh")
ax.set_title("BSES Rajdhani — June 2025")
ax.legend()
plt.tight_layout()
```

`get_carbon_intensity` is marked Preview until the DUM 2026 launch (October 2026). It emits a `PreviewWarning` on first use; the column shape is stable but the method signature may evolve.
