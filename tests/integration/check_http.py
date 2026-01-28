#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
import os


def wait_for_server(url: str, timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = httpx.get(url + "/state", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def main() -> int:
    python = Path(".venv/bin/python")
    if not python.exists():
        print(".venv not found; create it first")
        return 1

    os.environ["OPENSEC_DISABLE_ENV_LOAD"] = "1"
    os.environ.pop("OPENAI_API_KEY", None)

    proc = subprocess.Popen(
        [str(python), "-m", "uvicorn", "server.app:app", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        if not wait_for_server("http://127.0.0.1:8001"):
            print("Server did not start")
            return 1

        client = httpx.Client(base_url="http://127.0.0.1:8001", timeout=5.0)
        reset = client.post("/reset")
        step = client.post("/step", json={"action_type": "query_logs", "params": {"sql": "SELECT 1"}})
        state = client.get("/state")

        print(json.dumps({"reset": reset.json(), "step": step.json(), "state": state.json()}, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
