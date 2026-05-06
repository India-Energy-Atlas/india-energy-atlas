"""Canonical state slugs.

Mirrors the spirit of `ies-ingest`'s canonical_states.py — every Atlas
caller speaks one consistent set of slugs, and we reject anything else
at parameter-validation time before making an HTTP call.

This list intentionally lives in the SDK so that an offline tool (CLI,
tests) can validate input without round-tripping through the API.
"""

from __future__ import annotations

CANONICAL_STATES: frozenset[str] = frozenset(
    {
        "andhra-pradesh",
        "arunachal-pradesh",
        "assam",
        "bihar",
        "chhattisgarh",
        "delhi",
        "goa",
        "gujarat",
        "haryana",
        "himachal-pradesh",
        "jammu-kashmir",
        "jharkhand",
        "karnataka",
        "kerala",
        "madhya-pradesh",
        "maharashtra",
        "manipur",
        "meghalaya",
        "mizoram",
        "nagaland",
        "odisha",
        "punjab",
        "rajasthan",
        "sikkim",
        "tamil-nadu",
        "telangana",
        "tripura",
        "uttar-pradesh",
        "uttarakhand",
        "west-bengal",
        # union territories with hourly SLDC publication
        "chandigarh",
        "puducherry",
    }
)


def validate_state(slug: str) -> str:
    """Return the slug if canonical; raise ValueError otherwise.

    Validation lives in the SDK rather than only at the API so that
    typos surface before the first network round-trip.
    """
    if slug not in CANONICAL_STATES:
        raise ValueError(
            f"Unknown state slug {slug!r}. Expected one of "
            f"{sorted(CANONICAL_STATES)[:5]}... ({len(CANONICAL_STATES)} total)."
        )
    return slug
