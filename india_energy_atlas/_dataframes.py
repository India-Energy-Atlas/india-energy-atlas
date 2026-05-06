"""DataFrame helpers.

Centralises the JSON-rows -> pandas.DataFrame conversion so every
typed method gets the same tz-aware index handling.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

DEFAULT_TZ = "Asia/Kolkata"
TIMESTAMP_COLUMNS = ("timestamp", "interval_start", "issued_at")


def rows_to_frame(
    rows: Iterable[dict[str, Any]],
    *,
    tz: str = DEFAULT_TZ,
    timestamp_column: str | None = None,
) -> pd.DataFrame:
    """Build a DataFrame from an iterable of row dicts.

    If a timestamp-like column is present (or one is named explicitly),
    parse it to a tz-aware DatetimeIndex localised to ``tz``.
    """
    df = pd.DataFrame(list(rows))
    if df.empty:
        return df

    ts_col = timestamp_column
    if ts_col is None:
        for candidate in TIMESTAMP_COLUMNS:
            if candidate in df.columns:
                ts_col = candidate
                break

    if ts_col is not None and ts_col in df.columns:
        ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
        df.index = ts.dt.tz_convert(tz)
        df.index.name = ts_col
    return df
