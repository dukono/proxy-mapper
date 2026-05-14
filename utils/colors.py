"""Color utilities for the proxy UI."""


def get_status_color(status: int) -> str:
    """Get CSS color class for HTTP status code."""
    if status < 200:
        return "text-blue-500"
    elif status < 300:
        return "text-green-500"
    elif status < 400:
        return "text-yellow-500"
    elif status < 500:
        return "text-orange-500"
    return "text-red-500"


def get_method_color(method: str) -> str:
    """Get CSS color class for HTTP method."""
    colors = {
        "GET": "text-blue-400",
        "POST": "text-green-400",
        "PUT": "text-yellow-400",
        "DELETE": "text-red-400",
        "PATCH": "text-purple-400",
        "OPTIONS": "text-gray-400",
        "HEAD": "text-gray-400"
    }
    return colors.get(method.upper(), "text-gray-400")
