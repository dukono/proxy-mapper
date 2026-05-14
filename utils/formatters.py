"""Formatting utilities for the proxy UI."""


def format_size(size: int) -> str:
    """Format byte size to human readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def format_duration(ms: float) -> str:
    """Format duration in milliseconds to human readable string."""
    if ms < 1:
        return f"{ms * 1000:.0f} μs"
    elif ms < 1000:
        return f"{ms:.1f} ms"
    return f"{ms / 1000:.1f} s"
