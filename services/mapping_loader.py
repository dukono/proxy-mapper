"""MappingLoader: loads and indexes mapping files from disk into the RulesEngine.

Extracted from ProxyUIBase to separate file I/O + rule registration
from UI concerns.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from utils import get_logger

if TYPE_CHECKING:
    from proxy_server import ProxyServer
    from config.manager import ConfigManager

log = get_logger("LOADER")


class MappingLoader:
    """Loads mapping JSON files from the active profile directory into the RulesEngine."""

    def __init__(self, proxy: "ProxyServer", config: "ConfigManager"):
        self.proxy = proxy
        self.config = config
        # rule_id -> {request_file, response_file, url, full_json, request, response, mapping_type}
        self.file_info: Dict[str, Dict] = {}

    def load_all(self) -> int:
        """
        Clear existing rules and reload all mappings from the current profile directory.
        Returns the number of successfully loaded mappings.
        """
        from strategies import MappingStrategyFactory

        mappings_dir = self.config.get_mappings_dir()
        if not os.path.exists(mappings_dir):
            log.warning("Mappings directory not found: %s", mappings_dir)
            return 0

        profile = self.config.get_current_profile()
        mapping_type = profile.mapping_type if profile else "Wire"
        strategy = MappingStrategyFactory.get_strategy(mapping_type, self)

        engine = self.proxy.get_rules_engine()

        # ── Preserve enabled state by source_file before clearing ────────────
        enabled_by_file: dict = {}
        for rule in engine.rules:
            if rule.source_file:
                enabled_by_file[rule.source_file] = rule.enabled

        engine.rules.clear()
        self.file_info.clear()

        log.info("Loading mappings from: %s  (strategy=%s)", mappings_dir, mapping_type)

        count = 0
        for json_file in Path(mappings_dir).rglob("*.json"):
            filename = str(json_file.relative_to(mappings_dir))
            try:
                with open(json_file, "r") as f:
                    mapping = json.load(f)

                is_valid, errors = strategy.validate_mapping(mapping)
                if not is_valid:
                    log.warning("Validation failed for %s: %s", filename, errors)
                    continue

                rule = strategy.load_mapping(mapping)

                # ── stamp the source file on the rule itself ──────────────────
                rule.source_file = filename

                # ── restore enabled state if rule was toggled before reload ───
                if filename in enabled_by_file:
                    rule.enabled = enabled_by_file[filename]

                request = mapping.get("request", {})
                response = mapping.get("response", {})
                mt_lower = mapping_type.lower()

                if mt_lower == "wire":
                    url = (request.get("urlPath") or request.get("url") or
                           request.get("urlPattern") or request.get("urlPathPattern") or "N/A")
                else:
                    url = request.get("matchValue", "N/A")

                body_file = request.get("bodyFileName") or response.get("bodyFileName", "")

                self.file_info[rule.id] = {
                    "request_file": filename,
                    "response_file": body_file,
                    "url": url,
                    "full_json": json.dumps(mapping, indent=2),
                    "request": request,
                    "response": response,
                    "mapping_type": mapping_type,
                }
                count += 1
                log.debug("Loaded: %s -> rule_id=%s url=%s", filename, rule.id, url)

            except Exception as e:
                log.error("Error loading %s: %s", filename, e)

        log.info("Total loaded: %d mappings", count)
        return count

    def register(self, mapping: dict, mapping_filename: str,
                 body_filename: str = "") -> Optional[str]:
        """
        Register a single mapping dict as a rule (used after save from editor).
        Returns the new rule_id or None on failure.
        """
        from strategies import MappingStrategyFactory

        profile = self.config.get_current_profile()
        mapping_type = profile.mapping_type if profile else "Wire"
        strategy = MappingStrategyFactory.get_strategy(mapping_type, self)

        try:
            rule = strategy.load_mapping(mapping)
            request = mapping.get("request", {})
            response = mapping.get("response", {})
            mt_lower = mapping_type.lower()

            if mt_lower == "wire":
                url = (request.get("urlPath") or request.get("url") or
                       request.get("urlPattern") or request.get("urlPathPattern") or "N/A")
            else:
                url = request.get("matchValue", "N/A")

            self.file_info[rule.id] = {
                "request_file": mapping_filename,
                "response_file": body_filename,
                "url": url,
                "full_json": json.dumps(mapping, indent=2),
                "request": request,
                "response": response,
                "mapping_type": mapping_type,
            }
            return rule.id
        except Exception as e:
            log.error("Error registering mapping: %s", e)
            return None

    def unregister(self, rule_id: str):
        """Remove a rule from the engine and the index."""
        self.proxy.get_rules_engine().remove_rule(rule_id)
        self.file_info.pop(rule_id, None)

    def get_info(self, rule_id: str) -> Optional[Dict]:
        return self.file_info.get(rule_id)
