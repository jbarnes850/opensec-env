from __future__ import annotations

from typing import Optional

try:
    from openenv.core.env_server.interfaces import Environment as OpenEnvEnvironment
except ImportError:  # fallback for tooling without OpenEnv installed
    OpenEnvEnvironment = object  # type: ignore[misc,assignment]

from .environment import OpenSecEnvironment
from .models import AgentAction, Observation, EpisodeState


class OpenSecOpenEnv(OpenEnvEnvironment):  # type: ignore[misc]
    """OpenEnv-compatible adapter around OpenSecEnvironment."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = False

    def __init__(
        self,
        seed_path: str,
        sqlite_dir: str,
        max_steps: int,
        mask_injections: bool = False,
    ) -> None:
        super().__init__()  # type: ignore[misc]
        self._env = OpenSecEnvironment(
            seed_path=seed_path,
            sqlite_dir=sqlite_dir,
            max_steps=max_steps,
            mask_injections=mask_injections,
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: object,
    ) -> Observation:
        _ = seed, episode_id, kwargs
        result = self._env.reset()
        return result.observation

    def step(
        self,
        action: AgentAction,
        timeout_s: Optional[float] = None,
        **kwargs: object,
    ) -> Observation:
        _ = timeout_s, kwargs
        result = self._env.step(action)
        return result.observation

    @property
    def state(self) -> EpisodeState:
        return self._env.state()

    def close(self) -> None:
        return None
