"""Local: resolve configuration and strict JSON. Global: never embed personal paths.

Sources: https://docs.python.org/3.14/library/pathlib.html and https://docs.python.org/3.14/library/json.html
"""
import json  # Local: read reviewable plans and state without executing them.
import os  # Local: accept uv-loaded .env values and existing CODEX_HOME.
from dataclasses import dataclass  # Global: keep paths explicit across phases.
from pathlib import Path  # Local: normalize filesystem identities.


def unique_object(pairs):  # Global: avoid silently discarding duplicate JSON keys.
    """Local: build one object; global: reject ambiguous state instead of losing fields."""
    result = {}  # Local: preserve each key's original value.
    for key, value in pairs:  # Local: inspect keys before normal dictionary construction.
        if key in result:  # Global: duplicate keys make a repair unsafe.
            raise ValueError(f"Duplicate JSON key: {key}")  # Local: identify the malformed object.
        result[key] = value  # Local: accept each unique key.
    return result  # Global: retain every unambiguous value.


def invalid_constant(value):  # Global: JSON must not contain NaN or infinity.
    """Local: reject nonstandard numbers; global: avoid lossy round trips."""
    raise ValueError(f"Invalid JSON constant: {value}")  # Local: stop parsing immediately.


def parse_json(data):  # Global: parse the exact bytes being checked, not a second filesystem read.
    """Local: validate one snapshot; global: reject ambiguous keys and nonstandard numbers."""
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)  # Local: handle UTF-8 BOMs through the standard parser.


def read_json(path):  # Global: one strict parser for both plans and snapshots.
    """Local: read UTF-8 JSON; global: preserve unknown fields for the repair phase."""
    return parse_json(Path(path).read_bytes())  # Local: parse the single captured byte snapshot.


@dataclass(frozen=True)  # Global: paths cannot change midway through a repair.
class Settings:
    """Local: resolved profile and output roots. Global: separate app state from reports."""
    home: Path  # Local: the profile containing the observed state layout.
    output: Path  # Local: private backups, plans, status, and logs.

    @property  # Local: derive rather than duplicate the state filename.
    def state(self):
        """Global: v1 supports this observed desktop JSON file only."""
        return self.home / ".codex-global-state.json"  # Local: never enumerate unrelated profiles.

    @classmethod  # Local: make environment resolution available to CLI and scheduler.
    def from_env(cls):
        """Global: allow .env overrides while keeping machine-specific values out of source."""
        home = os.getenv("CODEX_REPAIR_HOME") or os.getenv("CODEX_HOME") or str(Path.home() / ".codex")  # Local: honor the explicitly selected profile first.
        output = os.getenv("CODEX_REPAIR_OUTPUT") or str(Path.cwd() / ".local")  # Local: keep generated data ignored in a clone.
        return cls(Path(home).expanduser().resolve(), Path(output).expanduser().resolve())  # Global: bind all phases to absolute locations.
