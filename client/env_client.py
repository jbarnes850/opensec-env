from __future__ import annotations

from typing import Any, Dict

import requests


class OpenSecEnvClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def reset(self) -> Dict[str, Any]:
        resp = requests.post(f"{self.base_url}/reset", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def step(self, action_type: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = {"action_type": action_type, "params": params or {}}
        resp = requests.post(f"{self.base_url}/step", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def state(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/state", timeout=10)
        resp.raise_for_status()
        return resp.json()
