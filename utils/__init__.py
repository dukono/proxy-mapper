"""
Utility functions for the proxy application.
"""

from .formatters import format_size, format_duration
from .colors import get_status_color, get_method_color
from .logger import get_logger

__all__ = [
    'format_size',
    'format_duration',
    'get_status_color',
    'get_method_color',
    'get_logger',
]
