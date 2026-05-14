"""
Mapping Strategy Classes for different validation types.

This module provides strategies for loading and validating WireMock mappings
depending on the profile type (Wire or default).
"""

from .base import MappingStrategy
from .wire_strategy import WireStrategy
from .default_strategy import DefaultStrategy
from .factory import MappingStrategyFactory

__all__ = [
    'MappingStrategy',
    'WireStrategy',
    'DefaultStrategy',
    'MappingStrategyFactory',
]
