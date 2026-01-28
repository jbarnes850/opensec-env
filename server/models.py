from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

try:
    from openenv.core.env_server.types import Action as OpenEnvAction
    from openenv.core.env_server.types import Observation as OpenEnvObservation
    from openenv.core.env_server.types import State as OpenEnvState
except ImportError:  # fallback for local tooling without OpenEnv installed
    OpenEnvAction = BaseModel
    OpenEnvObservation = BaseModel
    OpenEnvState = BaseModel


class AgentAction(OpenEnvAction):
    model_config = ConfigDict(extra="allow")
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ContainmentState(BaseModel):
    isolated_hosts: List[str] = Field(default_factory=list)
    blocked_domains: List[str] = Field(default_factory=list)
    reset_users: List[str] = Field(default_factory=list)


class ActionResult(BaseModel):
    ok: bool
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class Observation(OpenEnvObservation):
    scenario_id: str
    step_index: int
    attacker_state: str
    containment: ContainmentState
    new_emails: List[str] = Field(default_factory=list)
    new_alerts: List[str] = Field(default_factory=list)
    evidence_seen_ids: List[str] = Field(default_factory=list)
    evidence_content_ids: List[str] = Field(default_factory=list)
    last_action_result: ActionResult
    hint: Optional[str] = None
    done: bool = False
    reward: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EpisodeState(OpenEnvState):
    episode_id: str
    scenario_id: str
    step_count: int
    max_steps: int
    terminated: bool
    truncated: bool


class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)
    state: EpisodeState
