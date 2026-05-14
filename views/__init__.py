"""
View components for the proxy application.

This module provides modular views for:
- Monitor: Traffic list and request details
- Mappings: Rule management
"""

from .monitor import MonitorView
from .mappings import MappingsView

__all__ = ['MonitorView', 'MappingsView']
