import asyncio
import json
import time
import threading
import socket
from datetime import datetime
from typing import Callable, Dict, Any, Optional, List

from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

from models import TrafficEntry, RequestData, ResponseData, Header
from rules import RulesEngine, RuleType, MatchType, MatchCondition, RuleAction
from utils import get_logger

log = get_logger("PROXY")


def _build_request_data(flow: http.HTTPFlow, display_url: str) -> RequestData:
    """Build RequestData from a mitmproxy flow."""
    req_content = None
    if flow.request.content:
        try:
            req_content = flow.request.content.decode('utf-8', errors='replace')[:1_000_000]
        except Exception:
            req_content = "[Binary content]"

    return RequestData(
        id=flow.id,
        timestamp=datetime.now(),
        method=flow.request.method,
        url=display_url,
        host=flow.request.host,
        path=flow.request.path,
        headers=[Header(name=k, value=v) for k, v in flow.request.headers.items()],
        content=req_content,
        size=len(flow.request.content or b''),
        query_params=dict(flow.request.query) if flow.request.query else None
    )


def _build_response_data(flow: http.HTTPFlow, start_time: float) -> Optional[ResponseData]:
    """Build ResponseData from a mitmproxy flow response."""
    if not flow.response:
        return None

    resp_content = None
    if flow.response.content:
        try:
            resp_content = flow.response.content.decode('utf-8', errors='replace')[:1_000_000]
        except Exception:
            resp_content = "[Binary content]"

    return ResponseData(
        status_code=flow.response.status_code,
        headers=[Header(name=k, value=v) for k, v in flow.response.headers.items()],
        content=resp_content,
        size=len(flow.response.content or b''),
        duration_ms=(time.time() - start_time) * 1000
    )


class ProxyAddon:
    def __init__(self, on_request: Callable, on_response: Callable, rules_engine: RulesEngine):
        self.on_request = on_request
        self.on_response = on_response
        self.rules_engine = rules_engine
        self.pending_requests: Dict[str, float] = {}
        self._traffic_entries: Dict[str, TrafficEntry] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        start_time = time.time()
        self.pending_requests[flow.id] = start_time

        original_url = flow.request.url
        original_host = flow.request.host

        request_data = {
            "url": flow.request.url,
            "host": flow.request.host,
            "path": flow.request.path.split('?')[0],
            "path_full": flow.request.path,
            "query_string": flow.request.path.split('?')[1] if '?' in flow.request.path else "",
            "method": flow.request.method,
            "headers": dict(flow.request.headers),
            "query_params": dict(flow.request.query),
            "body": flow.request.content.decode('utf-8', errors='replace') if flow.request.content else ""
        }

        log.debug("Request: %s %s", request_data['method'], request_data['path'])
        log.debug("Full URL: %s", request_data['url'])
        log.debug("Query params: %s", request_data['query_params'])

        result = self.rules_engine.apply_rules(request_data)

        operation_type = "normal"
        redirect_url = None
        matched_file = None  # source_file of the rule that matched

        # Capture the source file from the first matching rule
        matching = self.rules_engine.find_matching_rules(request_data)
        if matching:
            matched_file = matching[0].source_file

        if result.get("mocked"):
            operation_type = "mock"
            log.debug("MOCKED! Status: %s", result['response'].get('status_code'))
        elif result.get("request_modified") and result["request"].get("url") != original_url:
            operation_type = "redirect"
            redirect_url = result["request"]["url"]
            log.debug("REDIRECT: %s -> %s", original_url, redirect_url)
        else:
            log.debug("NORMAL: forwarding to real server")

        if result.get("delayed") and result.get("delay_ms"):
            time.sleep(result["delay_ms"] / 1000)

        if operation_type == "redirect" and redirect_url:
            from urllib.parse import urlparse
            parsed = urlparse(redirect_url)
            scheme = parsed.scheme or 'http'
            host = parsed.hostname or original_host
            port = parsed.port or (443 if scheme == 'https' else 80)
            flow.request.host = host
            flow.request.port = port
            original_path = urlparse(original_url).path
            original_query = urlparse(original_url).query
            if original_query:
                flow.request.url = f"{scheme}://{host}:{port}{original_path}?{original_query}"
            else:
                flow.request.url = f"{scheme}://{host}:{port}{original_path}"

        if result["request"].get("headers"):
            for name, value in result["request"]["headers"].items():
                flow.request.headers[name] = value

        if operation_type == "mock" and result.get("response"):
            resp_data = result["response"]
            body = resp_data.get("body", "")
            if isinstance(body, (dict, list)):
                body = json.dumps(body)
            elif not isinstance(body, str):
                body = str(body)

            resp_headers = dict(resp_data.get("headers", {}))

            flow.response = http.Response.make(
                resp_data.get("status_code", 200),
                body.encode('utf-8'),
                resp_headers
            )
            # Inject proxy metadata headers so clients can detect mocks
            flow.response.headers['X-Proxy-Operation'] = 'mock'
            if matched_file:
                flow.response.headers['X-Proxy-File'] = matched_file
            # Inject active profile name
            try:
                from config.globals import get_global_config
                _cfg = get_global_config()
                _profile = _cfg.get_current_profile()
                if _profile:
                    flow.response.headers['X-Proxy-Profile'] = _profile.name
            except Exception:
                pass
            self._emit(flow, start_time, operation_type="mock", original_url=original_url, has_response=True, matched_file=matched_file)
            return

        self._emit(flow, start_time, operation_type=operation_type,
                   original_url=original_url, redirect_url=redirect_url, matched_file=matched_file)

    def response(self, flow: http.HTTPFlow) -> None:
        start_time = self.pending_requests.pop(flow.id, time.time())
        existing_entry = self._traffic_entries.get(flow.id)
        operation_type = existing_entry.operation_type if existing_entry else "normal"
        # Inject proxy metadata for redirected responses too
        if operation_type == "redirect" and flow.response:
            flow.response.headers['X-Proxy-Operation'] = 'redirect'
        self._emit(flow, start_time, operation_type=operation_type, has_response=True)

    def error(self, flow: http.HTTPFlow) -> None:
        start_time = self.pending_requests.pop(flow.id, time.time())
        log.error("Flow %s: %s", flow.id, flow.error)

        error_html = (
            f"<html><body><h1>Connection Error</h1>"
            f"<p>Error: {flow.error}</p>"
            f"<p>Target: {flow.request.url}</p></body></html>"
        )
        response_data = ResponseData(
            status_code=502,
            headers=[Header(name='Content-Type', value='text/html')],
            content=error_html,
            size=len(error_html.encode('utf-8')),
            duration_ms=(time.time() - start_time) * 1000
        )
        self._emit(flow, start_time, operation_type="normal",
                   prefilled_response=response_data)

    # ── unified emit ────────────────────────────────────────────────────────

    def _emit(self, flow: http.HTTPFlow, start_time: float,
              operation_type: str = "normal",
              original_url: str = None,
              redirect_url: str = None,
              has_response: bool = False,
              prefilled_response: Optional[ResponseData] = None,
              matched_file: Optional[str] = None) -> None:
        """Build/update a TrafficEntry and fire the appropriate callback."""
        display_url = original_url or flow.request.url
        request_data = _build_request_data(flow, display_url)
        response_data = prefilled_response or (_build_response_data(flow, start_time) if has_response else None)

        # Resolve active profile name and mappings dir at emit time
        profile_name = None
        mapping_file_full = None
        try:
            from config.globals import get_global_config
            cfg = get_global_config()
            profile = cfg.get_current_profile()
            if profile:
                profile_name = profile.name
                if matched_file:
                    import os
                    mapping_file_full = os.path.join(cfg.get_mappings_dir(), matched_file)
        except Exception:
            pass

        existing = self._traffic_entries.get(flow.id)

        if existing and response_data:
            existing.response = response_data
            if operation_type == "redirect":
                existing.operation_type = operation_type
                existing.redirect_url = redirect_url
            entry = existing
        else:
            entry = TrafficEntry(
                id=flow.id[:8],
                request=request_data,
                response=response_data,
                operation_type=operation_type,
                redirect_url=redirect_url,
                original_url=original_url,
                profile_name=profile_name,
                mapping_file=mapping_file_full,
            )
            self._traffic_entries[flow.id] = entry

        # Evict oldest entries when cache grows too large
        if len(self._traffic_entries) > 1000:
            for key in list(self._traffic_entries.keys())[:500]:
                del self._traffic_entries[key]

        if response_data:
            self.on_response(entry)
        else:
            self.on_request(entry)


class ProxyServer:
    def __init__(self, port: int = 8080):
        self.port = port
        self.master: Optional[DumpMaster] = None
        self.addon: Optional[ProxyAddon] = None
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.rules_engine = RulesEngine()
        self._callbacks: List[Callable] = []

    def set_callback(self, callback: Callable):
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self, entry: TrafficEntry):
        for cb in self._callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    def _on_request(self, entry: TrafficEntry):
        self._notify(entry)

    def _on_response(self, entry: TrafficEntry):
        self._notify(entry)

    def get_rules_engine(self) -> RulesEngine:
        return self.rules_engine

    async def start(self):
        opts = Options(listen_host='0.0.0.0', listen_port=self.port, ssl_insecure=True)
        self.master = DumpMaster(opts)
        self.addon = ProxyAddon(
            on_request=self._on_request,
            on_response=self._on_response,
            rules_engine=self.rules_engine
        )
        self.master.addons.add(self.addon)
        self.running = True
        await self.master.run()

    async def _stop_async(self):
        if self.master:
            self.running = False
            try:
                self.master.shutdown()
            except Exception:
                pass
            self.master = None
            await asyncio.sleep(1)

    def _wait_for_port_release(self, max_wait=10):
        for _ in range(max_wait * 2):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('0.0.0.0', self.port))
                sock.close()
                return True
            except socket.error:
                time.sleep(0.5)
        return False

    def start_in_thread(self):
        if not self._wait_for_port_release(max_wait=5):
            raise RuntimeError(f"Port {self.port} is still in use, please wait a moment")

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.start())

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the proxy (thread-safe, callable from sync code)."""
        if self._loop and self.running:
            future = asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            try:
                future.result(timeout=10)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
            self._thread = None

        if self._loop:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None

        time.sleep(2)
        self.running = False

    # Keep old name as alias so existing callers don't break
    stop_thread = stop
