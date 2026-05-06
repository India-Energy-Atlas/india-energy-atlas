"""Lightweight parameter validation shared across typed methods.

Catches the obvious mistakes (bad granularity, end < start, unknown
enum value) before we make a network call. Raises
`AtlasValidationError` so callers can `except AtlasValidationError`
uniformly whether the validation happens client-side or server-side.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from india_energy_atlas.exceptions import AtlasValidationError


def ensure_one_of(name: str, value: str, choices: Iterable[str]) -> str:
    valid = list(choices)
    if value not in valid:
        raise AtlasValidationError(f"{name}={value!r} is not one of {valid}")
    return value


def ensure_window(start: object, end: object) -> None:
    """Reject windows where end is strictly before start.

    Both inputs may be `str` or `pd.Timestamp`. Anything else is
    coerced via `pd.to_datetime`.
    """
    if start is None or end is None:
        return
    s = pd.to_datetime(start, utc=True, errors="coerce")
    e = pd.to_datetime(end, utc=True, errors="coerce")
    if pd.isna(s) or pd.isna(e):
        return  # let the server reject malformed values with its own message
    if e < s:
        raise AtlasValidationError(f"end ({end!r}) must be >= start ({start!r})")
