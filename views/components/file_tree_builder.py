"""FileTreeBuilder — builds tree/table data from the mappings filesystem."""

import os
import json
from pathlib import Path


class FileTreeBuilder:
    """Builds structured data from a mappings directory for rendering."""

    def __init__(self, mapping_loader, rules_engine_fn):
        """
        Args:
            mapping_loader:   the MappingLoader instance.
            rules_engine_fn:  callable() → RulesEngine.
        """
        self._loader = mapping_loader
        self._engine_fn = rules_engine_fn

    # ── public ───────────────────────────────────────────────────────────────

    def build_tree(self, base_path: str, rel_path: str = '') -> list:
        """Recursively build a tree from *base_path*."""
        items = []
        current = Path(base_path) / rel_path if rel_path else Path(base_path)
        if not current.exists():
            return items
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except Exception:
            return items

        for entry in entries:
            if entry.name.startswith('.'):
                continue
            entry_rel = os.path.join(rel_path, entry.name) if rel_path else entry.name
            if entry.is_dir():
                items.append({
                    'id': f'dir_{entry_rel}',
                    'label': entry.name,
                    'type': 'directory',
                    'path': entry_rel,
                    'children': self.build_tree(base_path, entry_rel) or [],
                })
            elif entry.suffix == '.json':
                info = self._get_mapping_info(entry_rel)
                if info:
                    items.append({
                        'id': f'file_{entry_rel}',
                        'label': entry.name,
                        'type': 'mapping',
                        'path': entry_rel,
                        **info,
                    })
                else:
                    items.append({
                        'id': f'file_{entry_rel}',
                        'label': entry.name,
                        'type': 'file',
                        'path': entry_rel,
                        'icon': 'insert_drive_file',
                    })
        return items

    def build_table(self, base_path: str) -> list:
        """Flat list of all JSON files with metadata for table view."""
        items = []
        base = Path(base_path)
        if not base.exists():
            return items

        def scan(path: Path, prefix: str = ''):
            try:
                for entry in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    rel = f"{prefix}/{entry.name}" if prefix else entry.name
                    if entry.is_dir():
                        if entry.name.startswith('__'):  # skip __files/, __pycache__, etc.
                            continue
                        scan(entry, rel)
                    elif entry.suffix == '.json':
                        info = self._get_mapping_info(rel)
                        if not info:
                            info = self._parse_file(entry)
                        items.append({
                            'name':       entry.name,
                            'path':       rel,
                            'folder':     prefix or '/',
                            'url':        info.get('url', '-'),
                            'type':       info.get('type', 'json'),
                            'status':     'Enabled' if info.get('is_enabled', True) else 'Disabled',
                            'mapping_id': info.get('mapping_id', ''),
                            'is_wire':    info.get('is_wire', False),
                        })
            except (PermissionError, OSError):
                pass

        scan(base)
        return items

    # ── private ──────────────────────────────────────────────────────────────

    def _get_mapping_info(self, rel_path: str) -> dict | None:
        for mapping_id, file_info in self._loader.file_info.items():
            if file_info.get('request_file') == rel_path:
                engine = self._engine_fn()
                rule = next((r for r in engine.rules if r.id == mapping_id), None)
                return {
                    'mapping_id': mapping_id,
                    'url':        file_info.get('url', 'N/A'),
                    'is_enabled': rule.enabled if rule else True,
                    'is_wire':    file_info.get('mapping_type', '').lower() == 'wire',
                }
        return None

    @staticmethod
    def _parse_file(entry: Path) -> dict:
        try:
            content = json.loads(entry.read_text())
            req = content.get('request', {})
            url = req.get('urlPattern') or req.get('url') or '-'
            return {'mapping_id': '', 'url': url, 'is_enabled': True, 'is_wire': False, 'type': 'json'}
        except Exception:
            return {'mapping_id': '', 'url': '-', 'is_enabled': True, 'is_wire': False, 'type': 'json'}
