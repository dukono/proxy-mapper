"""default type: Local mock response. Matches against full URL including host."""

import json
from typing import TYPE_CHECKING

from utils import get_logger
from .base import MappingStrategy

if TYPE_CHECKING:
    from rules import Rule

log = get_logger("DEFAULT")


class DefaultStrategy(MappingStrategy):
    """
    Default type: returns a local mock response.
    Matches against the FULL URL (scheme+host+path) because default mappings
    include the host (e.g. https://api.northflank.com/v1/...).
    """

    def load_mapping(self, mapping: dict) -> "Rule":
        from rules import Rule, RuleType, MatchType, MatchCondition, RuleAction

        request = mapping.get('request', {})
        response = mapping.get('response', {})

        conditions = []

        # ── URL matching against full URL (host included) ─────────────────────
        match_type = request.get('matchType', 'contains')
        match_value = request.get('matchValue', '')

        if match_value:
            if match_type == 'contains':
                conditions.append(MatchCondition('url', MatchType.CONTAINS, match_value))
            elif match_type == 'equal':
                conditions.append(MatchCondition('url', MatchType.EQUALS, match_value))
            elif match_type == 'regexp':
                conditions.append(MatchCondition('url', MatchType.REGEX, match_value))
            elif match_type == 'wildcard':
                conditions.append(MatchCondition('url', MatchType.WILDCARD, match_value))
            elif match_type == 'startsWith':
                conditions.append(MatchCondition('url', MatchType.STARTS_WITH, match_value))
            elif match_type == 'endsWith':
                conditions.append(MatchCondition('url', MatchType.ENDS_WITH, match_value))

        # ── Method matching ───────────────────────────────────────────────────
        method = request.get('method', 'ANY')
        if method and method != 'ANY':
            conditions.append(MatchCondition('method', MatchType.EQUALS, method.upper()))

        # ── Body matching ─────────────────────────────────────────────────────
        if request.get('bodyMatch') and request.get('bodyMatchValue'):
            body_match_type = request.get('bodyMatchType', 'contains')
            body_match_value = request.get('bodyMatchValue', '')
            if body_match_value:
                if body_match_type == 'contains':
                    conditions.append(MatchCondition('body', MatchType.CONTAINS, body_match_value))
                elif body_match_type == 'equal':
                    conditions.append(MatchCondition('body', MatchType.EQUALS, body_match_value))
                elif body_match_type == 'regexp':
                    conditions.append(MatchCondition('body', MatchType.REGEX, body_match_value))

        # ── Action: MOCK_RESPONSE (respond locally, never forward) ────────────
        body = response.get('body', '')
        try:
            body = json.loads(body)
        except Exception:
            pass

        action = RuleAction(
            type=RuleType.MOCK_RESPONSE,
            status_code=response.get('status', 200),
            headers=response.get('headers', {"Content-Type": "application/json"}),
            body=body,
        )

        rule = Rule(
            id="",
            name=mapping.get('name', f"default: {method} {match_value}"),
            enabled=True,
            priority=mapping.get('priority', 0),
            conditions=conditions,
            action=action,
        )

        self.ui.proxy.get_rules_engine().add_rule(rule)
        return rule

    def validate_mapping(self, mapping: dict) -> tuple[bool, list]:
        errors = []

        if 'request' not in mapping:
            errors.append("Missing 'request' section")
            return False, errors
        if 'response' not in mapping:
            errors.append("Missing 'response' section")
            return False, errors

        request = mapping['request']
        match_value = request.get('matchValue', '')
        if not match_value:
            errors.append("Request needs 'matchValue' for URL matching")

        match_type = request.get('matchType', 'contains')
        valid_types = ['contains', 'equal', 'regexp', 'wildcard', 'startsWith', 'endsWith']
        if match_type not in valid_types:
            errors.append(f"Invalid matchType '{match_type}'. Must be one of: {valid_types}")

        return len(errors) == 0, errors
