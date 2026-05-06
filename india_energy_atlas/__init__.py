"""India Energy Atlas Python SDK.

Consumer client for the Atlas data platform at api.energymap.in.
See https://github.com/India-Energy-Atlas/india-energy-atlas for status and roadmap.
"""

from india_energy_atlas._version import __version__
from india_energy_atlas.client import AtlasClient
from india_energy_atlas.exceptions import (
    AtlasAuthError,
    AtlasError,
    AtlasNotFoundError,
    AtlasRateLimitError,
    AtlasServerError,
    AtlasValidationError,
    PreviewWarning,
)

__all__ = [
    "AtlasAuthError",
    "AtlasClient",
    "AtlasError",
    "AtlasNotFoundError",
    "AtlasRateLimitError",
    "AtlasServerError",
    "AtlasValidationError",
    "PreviewWarning",
    "__version__",
]
