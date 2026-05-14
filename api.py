"""REST API endpoints exposed for the Chrome extension."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict

from config import get_global_config, get_global_proxy
from config.globals import (
    get_global_traffic, set_global_traffic,
    increment_traffic_version, get_global_traffic_version,
)

router = APIRouter(prefix="/api")


# ── Status ───────────────────────────────────────────────────────────────────

@router.get("/status")
async def status():
    proxy = get_global_proxy()
    config = get_global_config()
    profile = config.get_current_profile()
    return {
        "ok": True,
        "proxy_running": proxy.running if proxy else False,
        "proxy_port": getattr(proxy, "port", 8080) if proxy else 8080,
        "profile": profile.name if profile else None,
        "mapping_type": profile.mapping_type if profile else None,
    }


# ── Traffic ──────────────────────────────────────────────────────────────────

@router.get("/traffic")
async def get_traffic(limit: int = 200):
    traffic = get_global_traffic()
    entries = []
    for e in list(traffic)[-limit:]:
        entries.append({
            "id":       e.id,
            "method":   e.request.method,
            "url":      e.original_url or e.request.url,
            "path":     e.request.path,
            "host":     e.request.host,
            "code":     str(e.response.status_code) if e.response else "—",
            "duration": f"{e.response.duration_ms:.0f} ms" if e.response and e.response.duration_ms else "",
            "mocked":   e.mocked,
            "mapping_file": getattr(e, "mapping_file", None),
            "time":     e.request.timestamp.strftime("%H:%M:%S"),
        })
    return {"ok": True, "entries": entries, "total": len(traffic)}


@router.delete("/traffic")
async def clear_traffic():
    set_global_traffic([])
    increment_traffic_version()
    return {"ok": True}


# ── Proxy control ─────────────────────────────────────────────────────────────

@router.post("/proxy/start")
async def proxy_start():
    proxy = get_global_proxy()
    if proxy and not proxy.running:
        proxy.start_in_thread()
    return {"ok": True, "running": proxy.running if proxy else False}


@router.post("/proxy/stop")
async def proxy_stop():
    proxy = get_global_proxy()
    if proxy and proxy.running:
        proxy.stop()
    return {"ok": True, "running": proxy.running if proxy else False}


@router.post("/proxy/pause")
async def proxy_pause():
    # Pause is managed in UI state — just return ok for now
    return {"ok": True}


# ── Mappings ─────────────────────────────────────────────────────────────────

@router.get("/mappings")
async def list_mappings():
    config = get_global_config()
    mappings_dir = config.get_mappings_dir()
    import os, json as _json
    result = []
    if os.path.isdir(mappings_dir):
        for root, _, files in os.walk(mappings_dir):
            for f in files:
                if f.endswith(".json"):
                    rel = os.path.relpath(os.path.join(root, f), mappings_dir)
                    try:
                        data = _json.loads(open(os.path.join(root, f)).read())
                        req = data.get("request", {})
                        result.append({
                            "file": rel,
                            "method": req.get("method", ""),
                            "url": req.get("urlPath") or req.get("matchValue") or "",
                        })
                    except Exception:
                        result.append({"file": rel, "method": "", "url": ""})
    return {"ok": True, "mappings": result}


class CreateFromUrlRequest(BaseModel):
    method: str = "GET"
    path: str = "/"
    query: Optional[Dict[str, str]] = None
    host: Optional[str] = None


@router.post("/mappings/create_from_url")
async def create_mapping_from_url(req: CreateFromUrlRequest):
    """Create a stub mapping from a URL (called by the Chrome extension)."""
    import os, json as _json
    config = get_global_config()
    profile = config.get_current_profile()
    mapping_type = profile.mapping_type if profile else "default"
    mappings_dir = config.get_mappings_dir()

    segment = req.path.rstrip("/").split("/")[-1] or "mapping"
    filename = f"{req.method.lower()}-{segment}.json"

    if mapping_type == "Wire":
        body_filename = f"responses/{req.method.lower()}-{segment}.json"
        mapping = {
            "request": {
                "method": req.method,
                "urlPath": req.path,
            },
            "response": {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "bodyFileName": body_filename,
            }
        }
        if req.query:
            mapping["request"]["queryParameters"] = {
                k: {"equalTo": v} for k, v in req.query.items()
            }
    else:
        match_value = req.path
        if req.query:
            qs = "&".join(f"{k}={v}" for k, v in req.query.items())
            match_value = f"{req.path}?{qs}"
        mapping = {
            "request": {
                "method": req.method,
                "matchType": "contains",
                "matchValue": match_value,
            },
            "response": {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": '{"message": "Mock response"}',
            }
        }

    os.makedirs(mappings_dir, exist_ok=True)
    filepath = os.path.join(mappings_dir, filename)
    with open(filepath, "w") as f:
        f.write(_json.dumps(mapping, indent=2))

    return {"ok": True, "file": filename, "mapping": mapping}

