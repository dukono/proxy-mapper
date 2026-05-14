from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Union
from enum import Enum, auto
import re
import json

from utils import get_logger

log = get_logger("RULES")


class RuleType(Enum):
    MOCK_RESPONSE = auto()      # Return static response
    REDIRECT = auto()           # Redirect to different URL
    MODIFY_REQUEST = auto()     # Modify outgoing request
    MODIFY_RESPONSE = auto()    # Modify incoming response
    DELAY = auto()              # Add delay
    BREAKPOINT = auto()         # Pause for manual edit
    MAP_LOCAL = auto()          # Serve local file


class MatchType(Enum):
    CONTAINS = auto()
    EQUALS = auto()
    REGEX = auto()
    WILDCARD = auto()
    STARTS_WITH = auto()
    ENDS_WITH = auto()


@dataclass
class MatchCondition:
    field: str  # url, host, path, method, header, query_param, body
    match_type: MatchType
    value: str
    param_name: Optional[str] = None  # For header or query param matching

    def matches(self, request_data: Dict[str, Any]) -> bool:
        if self.field == "header" and self.param_name:
            headers = request_data.get("headers", {})
            field_value = headers.get(self.param_name.lower(), "")
        elif self.field == "query_param" and self.param_name:
            query_params = request_data.get("query_params", {})
            field_value = query_params.get(self.param_name, "")
        else:
            field_value = request_data.get(self.field, "")
        
        field_value = str(field_value)
        
        if self.match_type == MatchType.CONTAINS:
            return self.value in field_value
        elif self.match_type == MatchType.EQUALS:
            return field_value == self.value
        elif self.match_type == MatchType.STARTS_WITH:
            return field_value.startswith(self.value)
        elif self.match_type == MatchType.ENDS_WITH:
            return field_value.endswith(self.value)
        elif self.match_type == MatchType.REGEX:
            try:
                return bool(re.search(self.value, field_value))
            except:
                return False
        elif self.match_type == MatchType.WILDCARD:
            pattern = self.value.replace("*", ".*").replace("?", ".")
            try:
                return bool(re.match(f"^{pattern}$", field_value))
            except:
                return False
        return False


@dataclass
class RuleAction:
    type: RuleType
    # For MOCK_RESPONSE
    status_code: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    body_file_name: Optional[str] = None  # Preserve bodyFileName reference
    
    # For REDIRECT
    redirect_url: Optional[str] = None
    preserve_path: bool = False  # True for Wire: append original path+query to redirect_url

    # For MODIFY_REQUEST/MODIFY_RESPONSE
    header_add: Optional[Dict[str, str]] = None
    header_remove: Optional[List[str]] = None
    body_replace: Optional[str] = None
    body_replace_with: Optional[str] = None
    
    # For DELAY
    delay_ms: int = 0
    
    # For MAP_LOCAL
    local_path: Optional[str] = None
    
    # For BREAKPOINT
    enabled: bool = True


@dataclass
class Rule:
    id: str
    name: str
    enabled: bool = True
    priority: int = 0  # Higher = first
    conditions: List[MatchCondition] = field(default_factory=list)
    action: Optional[RuleAction] = None
    source_file: Optional[str] = None   # relative path inside mappings dir

    def matches(self, request_data: Dict[str, Any]) -> bool:
        if not self.enabled or not self.conditions:
            return False
        return all(condition.matches(request_data) for condition in self.conditions)


class RulesEngine:
    def __init__(self):
        self.rules: List[Rule] = []
        self._counter = 0
        self.breakpoint_callback: Optional[Callable] = None
    
    def _generate_id(self) -> str:
        self._counter += 1
        return f"rule_{self._counter}"
    
    def add_rule(self, rule: Rule) -> str:
        if not rule.id:
            rule.id = self._generate_id()
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)
        return rule.id
    
    def remove_rule(self, rule_id: str) -> bool:
        for i, r in enumerate(self.rules):
            if r.id == rule_id:
                self.rules.pop(i)
                return True
        return False
    
    def toggle_rule(self, rule_id: str) -> bool:
        for r in self.rules:
            if r.id == rule_id:
                r.enabled = not r.enabled
                return r.enabled
        return False
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return next((r for r in self.rules if r.id == rule_id), None)
    
    def find_matching_rules(self, request_data: Dict[str, Any]) -> List["Rule"]:
        matching = []
        log.debug("Checking %d rules against: %s %s",
                  len(self.rules), request_data.get('method'), request_data.get('path'))
        for rule in self.rules:
            if rule.matches(request_data):
                log.debug("MATCH: %s", rule.name)
                matching.append(rule)
            else:
                if rule.conditions:
                    for cond in rule.conditions:
                        field_val = request_data.get(cond.field, "")
                        if cond.field == "header" and cond.param_name:
                            field_val = request_data.get("headers", {}).get(cond.param_name.lower(), "")
                        elif cond.field == "query_param" and cond.param_name:
                            field_val = request_data.get("query_params", {}).get(cond.param_name, "")
                        if not cond.matches(request_data):
                            log.debug("No match: %s - condition %s=%s vs request %s",
                                      rule.name, cond.field, cond.value, field_val)
        return matching
    
    def apply_rules(self, request_data: Dict[str, Any], response_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {
            "request_modified": False,
            "response_modified": False,
            "mocked": False,
            "delayed": False,
            "breakpoint": False,
            "request": request_data.copy(),
            "response": response_data.copy() if response_data else None,
            "actions_applied": []
        }
        
        matching = self.find_matching_rules(request_data)
        
        for rule in matching:
            if not rule.action:
                continue
                
            action = rule.action
            result["actions_applied"].append(rule.name)
            
            if action.type == RuleType.MOCK_RESPONSE:
                result["mocked"] = True
                result["response"] = {
                    "status_code": action.status_code or 200,
                    "headers": action.headers or {"Content-Type": "application/json"},
                    "body": self._format_body(action.body) if action.body else "{}"
                }
                
            elif action.type == RuleType.REDIRECT:
                if action.redirect_url:
                    if action.preserve_path:
                        # Wire type: service_url + original path + original query
                        request_path = request_data.get("path", "")
                        query_params_raw = request_data.get("query_string", "")
                        base_url = action.redirect_url.rstrip('/')
                        path = request_path if request_path.startswith('/') else '/' + request_path
                        if query_params_raw:
                            result["request"]["url"] = f"{base_url}{path}?{query_params_raw}"
                        else:
                            result["request"]["url"] = f"{base_url}{path}"
                        log.debug("[REDIRECT-WIRE] %s -> %s", request_path, result['request']['url'])
                    else:
                        # Standard redirect: use redirect_url directly
                        result["request"]["url"] = action.redirect_url
                    result["request_modified"] = True
                    
            elif action.type == RuleType.MODIFY_REQUEST:
                if action.header_add:
                    headers = result["request"].get("headers", {})
                    headers.update(action.header_add)
                    result["request"]["headers"] = headers
                    result["request_modified"] = True
                if action.header_remove:
                    headers = result["request"].get("headers", {})
                    for h in action.header_remove:
                        headers.pop(h.lower(), None)
                    result["request"]["headers"] = headers
                    result["request_modified"] = True
                    
            elif action.type == RuleType.MODIFY_RESPONSE and result["response"]:
                if action.header_add:
                    headers = result["response"].get("headers", {})
                    headers.update(action.header_add)
                    result["response"]["headers"] = headers
                    result["response_modified"] = True
                if action.status_code:
                    result["response"]["status_code"] = action.status_code
                    result["response_modified"] = True
                if action.body_replace and action.body_replace_with is not None:
                    body = result["response"].get("body", "")
                    body = body.replace(action.body_replace, action.body_replace_with)
                    result["response"]["body"] = body
                    result["response_modified"] = True
                    
            elif action.type == RuleType.DELAY:
                result["delay_ms"] = action.delay_ms
                result["delayed"] = True
                
            elif action.type == RuleType.BREAKPOINT:
                result["breakpoint"] = True
                if self.breakpoint_callback:
                    self.breakpoint_callback(rule, result)
        
        return result
    
    def _format_body(self, body: Any) -> str:
        if isinstance(body, (dict, list)):
            return json.dumps(body, indent=2)
        return str(body)
    
    def quick_mock(self, name: str, url_pattern: str, status: int = 200, body: Any = None):
        """Quick helper to create a mock rule"""
        rule = Rule(
            id=self._generate_id(),
            name=name,
            conditions=[MatchCondition("url", MatchType.CONTAINS, url_pattern)],
            action=RuleAction(
                type=RuleType.MOCK_RESPONSE,
                status_code=status,
                body=body or {"mocked": True}
            )
        )
        self.add_rule(rule)
        return rule.id
    
    def quick_redirect(self, name: str, from_url: str, to_url: str):
        """Quick helper to create a redirect rule"""
        rule = Rule(
            id=self._generate_id(),
            name=name,
            conditions=[MatchCondition("url", MatchType.CONTAINS, from_url)],
            action=RuleAction(
                type=RuleType.REDIRECT,
                redirect_url=to_url
            )
        )
        self.add_rule(rule)
        return rule.id
    
    def quick_modify_header(self, name: str, url_pattern: str, headers_to_add: Dict[str, str] = None, headers_to_remove: List[str] = None):
        """Quick helper to modify headers"""
        rule = Rule(
            id=self._generate_id(),
            name=name,
            conditions=[MatchCondition("url", MatchType.CONTAINS, url_pattern)],
            action=RuleAction(
                type=RuleType.MODIFY_REQUEST,
                header_add=headers_to_add,
                header_remove=headers_to_remove
            )
        )
        self.add_rule(rule)
        return rule.id
