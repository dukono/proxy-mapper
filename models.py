from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid


class Header(BaseModel):
    name: str
    value: str


class RequestData(BaseModel):
    id: str
    timestamp: datetime
    method: str
    url: str
    host: str
    path: str
    headers: List[Header]
    content: Optional[str] = None
    size: int = 0
    query_params: Optional[Dict[str, str]] = None


class ResponseData(BaseModel):
    status_code: int
    headers: List[Header]
    content: Optional[str] = None
    size: int = 0
    duration_ms: float = 0.0


class TrafficEntry(BaseModel):
    id: str = ""
    request: RequestData
    response: Optional[ResponseData] = None
    operation_type: str = "normal"  # "normal", "redirect", "mock"
    redirect_url: Optional[str] = None
    original_url: Optional[str] = None
    profile_name: Optional[str] = None  # profile that matched this request
    mapping_file: Optional[str] = None  # full path of the mapping file that matched

    def __init__(self, **data):
        # Accept legacy mocked= kwarg without breaking old call sites
        data.pop("mocked", None)
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())[:8]
        super().__init__(**data)

    @property
    def mocked(self) -> bool:
        """True when the response was served locally (mock) or redirected."""
        return self.operation_type in ("mock", "redirect")
