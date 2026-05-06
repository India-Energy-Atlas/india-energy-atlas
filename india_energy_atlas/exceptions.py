"""Error taxonomy for india-energy-atlas.

All exceptions raised by the SDK subclass `AtlasError`. Catch the base
to handle anything; catch a specific subclass to react to specific
failure modes.
"""


class AtlasError(Exception):
    """Base class for all errors raised by the india-energy-atlas SDK."""


class AtlasAuthError(AtlasError):
    """API key missing, invalid, or revoked. HTTP 401."""


class AtlasRateLimitError(AtlasError):
    """Rate limit exceeded. HTTP 429. Honour `Retry-After` header where present."""


class AtlasNotFoundError(AtlasError):
    """Resource (dataset, order, etc.) not found. HTTP 404."""


class AtlasServerError(AtlasError):
    """Server-side failure. HTTP 5xx."""


class AtlasValidationError(AtlasError):
    """Request parameters failed validation. HTTP 400 / 422."""
