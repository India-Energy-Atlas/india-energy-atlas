# Cookbook — IEX price duration curve

A price-duration curve plots prices sorted descending vs. the cumulative fraction of time. It's the standard "how often was the price above X?" view a trader or storage operator wants.

```python
from india_energy_atlas import AtlasClient
import matplotlib.pyplot as plt
import numpy as np

with AtlasClient() as client:
    df = client.get_iex_prices(
        market="dam",
        start="2024-01-01",
        end="2024-12-31",
    )

prices = df["mcp_inr_per_mwh"].dropna().sort_values(ascending=False).to_numpy()
duration = np.linspace(0, 1, len(prices))

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(duration * 100, prices)
ax.set_xlabel("% of hours price ≥ value")
ax.set_ylabel("Clearing price (INR / MWh)")
ax.set_title("IEX DAM 2024 — Price-duration curve")
ax.grid(True, alpha=0.3)
plt.tight_layout()

p90 = np.quantile(prices, 0.10)  # exceeded 90% of the time
print(f"Price exceeded 90% of the time: {p90:,.0f} INR/MWh")
```
