from __future__ import annotations

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from server.models import AgentAction, Observation


class OpenSecEnv(EnvClient[AgentAction, Observation, State]):
    """OpenEnv WebSocket client for OpenSec-Env."""

    def _step_payload(self, action: AgentAction) -> Dict:
        return action.model_dump()

    def _parse_result(self, payload: Dict) -> StepResult[Observation]:
        obs_data = payload.get("observation", {})
        observation = Observation(**obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
