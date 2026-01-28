"""Shared utilities for eval scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set


def load_json(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def injection_evidence_ids(scenario: Optional[Dict[str, Any]]) -> Set[str]:
    if not scenario:
        return set()
    ids: Set[str] = set()
    for payload in scenario.get("prompt_injection_payloads", []):
        for evidence_id in payload.get("evidence_ids", []) or []:
            ids.add(evidence_id)
    return ids


def extract_json(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json found")
    return json.loads(text[start : end + 1])
