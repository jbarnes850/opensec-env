from __future__ import annotations

import os

from fastapi import FastAPI

from .models import AgentAction, Observation
from .openenv_adapter import OpenSecOpenEnv

try:
    from openenv.core.env_server import create_app as openenv_create_app
except ImportError:  # fallback for dev tooling
    openenv_create_app = None


def _env_factory() -> OpenSecOpenEnv:
    seed_path = os.getenv("OPENSEC_SEED_PATH", "data/seeds/sample_seed.json")
    sqlite_dir = os.getenv("OPENSEC_SQLITE_DIR", "data/sqlite")
    max_steps = int(os.getenv("OPENSEC_MAX_STEPS", "15"))
    mask_injections = os.getenv("OPENSEC_MASK_INJECTIONS", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    return OpenSecOpenEnv(
        seed_path=seed_path,
        sqlite_dir=sqlite_dir,
        max_steps=max_steps,
        mask_injections=mask_injections,
    )


if openenv_create_app is None:
    app = FastAPI(title="OpenSec-Env")
else:
    app = openenv_create_app(_env_factory, AgentAction, Observation, env_name="opensec-env")
