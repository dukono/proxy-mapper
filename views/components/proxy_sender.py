"""Utility to send HTTP requests through the local proxy."""

import threading
import requests as req_lib
from nicegui import ui

PROXY_URL = 'http://localhost:8080'
HOP_BY_HOP = {'host', 'content-length', 'transfer-encoding', 'connection',
               'proxy-connection', 'keep-alive'}


def send_via_proxy(method: str, url: str, headers: dict, body, on_done=None):
    """Send a request through the local mitmproxy instance.

    Args:
        method:  HTTP verb.
        url:     Full target URL.
        headers: Dict of headers (hop-by-hop already stripped by caller).
        body:    Raw body bytes / str or None.
        on_done: Optional callback(response) called in the background thread.
    """
    proxies = {'http': PROXY_URL, 'https': PROXY_URL}

    def _run():
        try:
            resp = req_lib.request(
                method, url,
                headers=headers,
                data=body.encode() if isinstance(body, str) else body,
                timeout=30,
                verify=False,
                allow_redirects=False,
                proxies=proxies,
            )
            if on_done:
                on_done(resp)
        except Exception as exc:
            if on_done:
                on_done(exc)

    threading.Thread(target=_run, daemon=True).start()


def headers_for_repeat(entry_headers) -> dict:
    """Strip hop-by-hop headers from a traffic entry's header list."""
    return {h.name: h.value for h in entry_headers
            if h.name.lower() not in HOP_BY_HOP}

