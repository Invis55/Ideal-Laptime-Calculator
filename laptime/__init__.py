"""Ideal lap time calculator: real circuit geometry, optimal racing line, point-mass lap solver."""
from .api import simulate, LapComparison  # noqa: F401
from .geometry import available_tracks  # noqa: F401

__version__ = "1.0.0"
