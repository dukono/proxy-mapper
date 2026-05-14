"""Base strategy for loading and validating mappings."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rules import Rule


class MappingStrategy(ABC):
    """Base strategy for loading and validating mappings."""

    def __init__(self, ui_instance: Any):
        self.ui = ui_instance

    @abstractmethod
    def load_mapping(self, mapping: dict) -> "Rule":
        """Load a mapping and convert to Rule - to be implemented by subclasses."""
        raise NotImplementedError

    @abstractmethod
    def validate_mapping(self, mapping: dict) -> tuple[bool, list]:
        """Validate mapping structure - to be implemented by subclasses."""
        raise NotImplementedError
