"""Canonical DISCOM allowlist for the India Energy Atlas SDK."""

from __future__ import annotations

# Mirrors src/transmission_map/canonical_discoms.yaml in the backend.
# Maps discom_slug → state_slug.
CANONICAL_DISCOMS: dict[str, str] = {
    # Delhi
    "bses-rajdhani": "delhi",
    "bses-yamuna": "delhi",
    "tpddl": "delhi",
    # Maharashtra
    "msedcl": "maharashtra",
    "best-mumbai": "maharashtra",
    "adani-electricity-mumbai": "maharashtra",
    # Gujarat
    "dgvcl": "gujarat",
    "mgvcl": "gujarat",
    "pgvcl": "gujarat",
    "ugvcl": "gujarat",
    # Karnataka
    "bescom": "karnataka",
    "cesc-karnataka": "karnataka",
    "gescom": "karnataka",
    "hescom": "karnataka",
    "mescom": "karnataka",
    # Tamil Nadu
    "tangedco": "tamil-nadu",
    # Uttar Pradesh
    "dvvnl": "uttar-pradesh",
    "pvvnl": "uttar-pradesh",
    "mvvnl": "uttar-pradesh",
    "puvvnl": "uttar-pradesh",
    # Rajasthan
    "jvvnl": "rajasthan",
    "avvnl": "rajasthan",
    "jdvvnl": "rajasthan",
    # Madhya Pradesh
    "mpcz": "madhya-pradesh",
    "mpmkvvcl": "madhya-pradesh",
    "mpwz": "madhya-pradesh",
    # West Bengal
    "wbsedcl": "west-bengal",
    "cesc-kolkata": "west-bengal",
    # Andhra Pradesh
    "apspdcl": "andhra-pradesh",
    "apepdcl": "andhra-pradesh",
    # Telangana
    "tsspdcl": "telangana",
    "tsnpdcl": "telangana",
    # Haryana
    "dhbvn": "haryana",
    "uhbvn": "haryana",
}


def validate_discom(slug: str) -> None:
    """Raise ValueError if *slug* is not in the canonical DISCOM allowlist."""
    if slug not in CANONICAL_DISCOMS:
        valid = sorted(CANONICAL_DISCOMS.keys())
        raise ValueError(f"Unknown DISCOM slug {slug!r}. Valid slugs: {valid}")
