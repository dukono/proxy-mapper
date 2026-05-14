"""Profile dataclass for WireMock configuration."""

from dataclasses import dataclass


@dataclass
class WireMockProfile:
    """Configuration dataclass for WireMock profiles.

    Attributes:
        name: Profile name
        root_path: Root directory containing mappings/ and __files/
        description: Optional description
        mapping_type: "Wire" (redirect to external service) or "default" (local validation)
        service_url: For Wire type: URL of external WireMock service
    """
    name: str
    root_path: str
    description: str = ""
    mapping_type: str = "Wire"
    service_url: str = ""
    mappings_path: str = ""  # custom path to mappings dir; if empty, uses root_path/mappings
