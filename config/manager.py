"""Configuration manager for WireMock profiles."""

import json
import os
from dataclasses import asdict
from typing import List, Optional

from .profile import WireMockProfile
from utils import get_logger

log = get_logger("CONFIG")


class ConfigManager:
    """Manages WireMock profiles configuration."""

    CONFIG_FILE = "proxy_config.json"

    def __init__(self):
        self.profiles: List[WireMockProfile] = []
        self.current_profile: Optional[str] = None
        self._load_config()
        # Create default profile if none exists
        if not self.profiles:
            default_path = os.path.join(os.path.dirname(__file__), '..', 'wiremock')
            self.profiles.append(WireMockProfile(
                name="Default",
                root_path=default_path,
                description="Default WireMock directory"
            ))
            self.current_profile = "Default"
            self._save_config()

    def _get_config_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), '..', self.CONFIG_FILE)

    def _load_config(self):
        try:
            config_path = self._get_config_path()
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    profiles = []
                    for p in data.get('profiles', []):
                        # Defensive: ignore unknown fields, supply defaults for missing ones
                        known = {k: v for k, v in p.items() if k in WireMockProfile.__dataclass_fields__}
                        profiles.append(WireMockProfile(**known))
                    self.profiles = profiles
                    self.current_profile = data.get('current_profile')
        except Exception as e:
            log.error("Error loading config: %s", e)

    def _save_config(self):
        try:
            config_path = self._get_config_path()
            data = {
                'profiles': [asdict(p) for p in self.profiles],
                'current_profile': self.current_profile
            }
            with open(config_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error("Error saving config: %s", e)

    def add_profile(self, profile: WireMockProfile):
        self.profiles.append(profile)
        self._save_config()

    def remove_profile(self, name: str):
        self.profiles = [p for p in self.profiles if p.name != name]
        if self.current_profile == name and self.profiles:
            self.current_profile = self.profiles[0].name
        self._save_config()

    def get_profile(self, name: str) -> Optional[WireMockProfile]:
        for p in self.profiles:
            if p.name == name:
                return p
        return None

    def set_current_profile(self, name: str):
        if self.get_profile(name):
            self.current_profile = name
            self._save_config()

    def get_current_profile(self) -> Optional[WireMockProfile]:
        if self.current_profile:
            return self.get_profile(self.current_profile)
        return self.profiles[0] if self.profiles else None

    def get_mappings_dir(self) -> str:
        profile = self.get_current_profile()
        if profile:
            if profile.mappings_path:
                # mappings_path is the WireMock root (e.g. trafficparrot_mappings/)
                # mappings live inside it at mappings_path/mappings
                return os.path.join(profile.mappings_path, 'mappings')
            return os.path.join(profile.root_path, 'mappings')
        return os.path.join(os.path.dirname(__file__), '..', 'mappings')

    def get_files_dir(self) -> str:
        profile = self.get_current_profile()
        if profile:
            if profile.mappings_path:
                # __files lives alongside mappings/ inside mappings_path
                return os.path.join(profile.mappings_path, '__files')
            return os.path.join(profile.root_path, '__files')
        return os.path.join(os.path.dirname(__file__), '..', '__files')
