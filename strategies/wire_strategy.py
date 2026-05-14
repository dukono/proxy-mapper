"""Wire type: Redirect all requests to external WireMock service."""

import re
import uuid
from typing import TYPE_CHECKING, Any

from utils import get_logger
from .base import MappingStrategy

if TYPE_CHECKING:
    from rules import Rule

log = get_logger("WIRE")


class WireStrategy(MappingStrategy):
    """
    Wire type: matches requests by PATH only (no host) and redirects to external WireMock service.

    WireMock URL fields handled:
      - urlPath        → exact path match (EQUALS)
      - urlPathPattern → regex path match (REGEX)
      - urlPattern     → regex path match (REGEX)
      - url            → exact path+query match (EQUALS on path, then query params separately)
    """

    def load_mapping(self, mapping: dict) -> "Rule":
        from rules import Rule, RuleType, MatchType, MatchCondition, RuleAction

        profile = self.ui.config.get_current_profile()
        service_url = getattr(profile, 'service_url', '') if profile else ''

        request = mapping.get('request', {})
        conditions = []

        # ── Path matching ─────────────────────────────────────────────────────
        if 'urlPath' in request:
            # Exact path, no query string considered
            conditions.append(MatchCondition('path', MatchType.EQUALS, request['urlPath']))

        elif 'urlPathPattern' in request:
            # Regex on path only
            conditions.append(MatchCondition('path', MatchType.REGEX, request['urlPathPattern']))

        elif 'urlPattern' in request:
            # Regex that may include query — match against path only (strip query from pattern)
            pattern = request['urlPattern'].split('\\?')[0].split('?')[0]
            conditions.append(MatchCondition('path', MatchType.REGEX, pattern))

        elif 'url' in request:
            # Modo 1: Coincidencia Total — path + query string como cadena exacta
            # Compara contra path_full (e.g. /v1/users?page=1)
            raw = request['url']
            conditions.append(MatchCondition('path_full', MatchType.EQUALS, raw))

        else:
            # Fallback: match everything
            conditions.append(MatchCondition('path', MatchType.REGEX, '.*'))

        # ── Query parameter matching ───────────────────────────────────────────
        query_params = request.get('queryParameters', {})
        for param_name, matcher in query_params.items():
            if 'equalTo' in matcher:
                conditions.append(MatchCondition('query_param', MatchType.EQUALS, matcher['equalTo'], param_name=param_name))
            elif 'contains' in matcher:
                conditions.append(MatchCondition('query_param', MatchType.CONTAINS, matcher['contains'], param_name=param_name))
            elif 'matches' in matcher:
                conditions.append(MatchCondition('query_param', MatchType.REGEX, matcher['matches'], param_name=param_name))

        # ── Method matching ───────────────────────────────────────────────────
        method = request.get('method', 'ANY')
        if method and method != 'ANY':
            conditions.append(MatchCondition('method', MatchType.EQUALS, method.upper()))

        # ── Action: REDIRECT with preserve_path so proxy appends original path+query ──
        action = RuleAction(
            type=RuleType.REDIRECT,
            redirect_url=service_url,
            preserve_path=True,  # proxy will build: service_url + original_path?original_query
        )

        rule_id = f"wire_{uuid.uuid4().hex[:8]}"
        url_label = (request.get('urlPath') or request.get('urlPathPattern') or
                     request.get('urlPattern') or request.get('url') or '.*')
        rule = Rule(
            id=rule_id,
            name=f"Wire: {url_label} → {service_url}",
            enabled=True,
            priority=0,
            conditions=conditions,
            action=action,
        )

        self.ui.proxy.get_rules_engine().add_rule(rule)
        return rule

    def validate_mapping(self, mapping: dict) -> tuple[bool, list]:
        profile = self.ui.config.get_current_profile()
        service_url = getattr(profile, 'service_url', '') if profile else ''

        if not service_url:
            return False, ["Wire type requires service_url to be set in profile"]

        if 'request' not in mapping and 'response' not in mapping:
            return False, ["Mapping must have at least 'request' or 'response' section"]

        return True, []
