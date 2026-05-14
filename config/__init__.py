"""
Configuration management for the proxy application.

This module provides profile management and configuration persistence.
"""

from .profile import WireMockProfile
from .manager import ConfigManager
from .globals import (
    get_global_config,
    get_global_proxy,
    get_global_queue,
    get_global_traffic,
    set_global_traffic,
    get_global_traffic_version,
    increment_traffic_version,
)

__all__ = [
    'WireMockProfile',
    'ConfigManager',
    'get_global_config',
    'get_global_proxy',
    'get_global_queue',
    'get_global_traffic',
    'set_global_traffic',
    'get_global_traffic_version',
    'increment_traffic_version',
]
