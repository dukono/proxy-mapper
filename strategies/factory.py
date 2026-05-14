"""Factory to get the appropriate strategy for a profile type."""

from typing import Any

from .base import MappingStrategy
from .wire_strategy import WireStrategy
from .default_strategy import DefaultStrategy


class MappingStrategyFactory:
    """Factory to get the appropriate strategy for a profile type."""

    STRATEGIES = {
        'wire': WireStrategy,
        'default': DefaultStrategy,
    }

    @classmethod
    def get_strategy(cls, mapping_type: str, ui_instance: Any) -> MappingStrategy:
        """Get strategy instance for the given mapping type (case-insensitive)."""
        key = (mapping_type or 'default').lower()
        strategy_class = cls.STRATEGIES.get(key, DefaultStrategy)
        return strategy_class(ui_instance)
