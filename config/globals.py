"""Global singletons and configuration accessor functions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import ConfigManager
    from proxy_server import ProxyServer

# Global singletons (shared across page reloads)
_global_proxy = None
_global_queue = None
_global_traffic = []
_global_config = None
_global_traffic_version = 0   # incremented on every traffic update
_mappings_loaded = False       # guard: only auto-load once globally


def get_global_config() -> "ConfigManager":
    """Get or create the global ConfigManager instance."""
    global _global_config
    if _global_config is None:
        from .manager import ConfigManager
        _global_config = ConfigManager()
    return _global_config


def get_global_proxy():
    """Get or create the global ProxyServer instance."""
    global _global_proxy
    if _global_proxy is None:
        from proxy_server import ProxyServer
        _global_proxy = ProxyServer(port=8080)
    return _global_proxy


def get_global_queue():
    """Get or create the global update queue."""
    from queue import Queue
    global _global_queue
    if _global_queue is None:
        _global_queue = Queue()
    return _global_queue


def get_global_traffic():
    """Get the global traffic list."""
    global _global_traffic
    return _global_traffic


def set_global_traffic(traffic: list):
    """Set the global traffic list."""
    global _global_traffic
    _global_traffic = traffic


def get_global_traffic_version() -> int:
    """Get the current traffic version counter."""
    global _global_traffic_version
    return _global_traffic_version


def increment_traffic_version():
    """Increment the traffic version counter (call on every add/update)."""
    global _global_traffic_version
    _global_traffic_version += 1


def is_mappings_loaded() -> bool:
    """Check if the mappings have been loaded."""
    global _mappings_loaded
    return _mappings_loaded


def set_mappings_loaded(value: bool):
    """Set the mappings loaded flag."""
