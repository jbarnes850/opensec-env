from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STATES: List[str] = [
    "phish_sent",
    "creds_used",
    "lateral_move",
    "data_access",
    "exfil_attempt",
]

STATE_INDEX: Dict[str, int] = {state: i for i, state in enumerate(STATES)}


@dataclass
class ContainmentActions:
    isolated_hosts: List[str]
    blocked_domains: List[str]
    reset_users: List[str]


@dataclass
class ScenarioContext:
    attacker_domain: str
    patient_zero_host: str
    compromised_user: str


@dataclass
class AttackerContext:
    current_host: Optional[str] = None
    current_user: Optional[str] = None
    compromised_hosts: List[str] = field(default_factory=list)
    compromised_users: List[str] = field(default_factory=list)
    current_target: Optional[str] = None
    current_exfil_domain: Optional[str] = None
    has_creds: bool = False
    has_admin: bool = False
    has_stage: bool = False
    has_persistence: bool = False

    def record_host(self, host_id: Optional[str]) -> None:
        if not host_id:
            return
        if host_id not in self.compromised_hosts:
            self.compromised_hosts.append(host_id)
        self.current_host = host_id

    def record_user(self, user_id: Optional[str]) -> None:
        if not user_id:
            return
        if user_id not in self.compromised_users:
            self.compromised_users.append(user_id)
        self.current_user = user_id


@dataclass
class AdvanceResult:
    next_state: str
    stalled: bool
    reason: str
    matched_action: Optional[Dict[str, Any]] = None


ACTION_STATE_FALLBACK = {
    "reuse_credentials": "creds_used",
    "lateral_move": "lateral_move",
    "lateral_move_alt": "lateral_move",
    "access_data": "data_access",
    "exfiltrate": "exfil_attempt",
    "exfiltrate_alt": "exfil_attempt",
    "send_phish": "phish_sent",
}


def _apply_action_effects(context: AttackerContext, effects: Dict[str, Any]) -> None:
    if "has_creds" in effects:
        context.has_creds = bool(effects["has_creds"])
    if "has_admin" in effects:
        context.has_admin = bool(effects["has_admin"])
    if "has_stage" in effects:
        context.has_stage = bool(effects["has_stage"])
    if "has_persistence" in effects:
        context.has_persistence = bool(effects["has_persistence"])

    host = effects.get("compromise_host") or effects.get("current_host") or effects.get("set_current_host")
    if host:
        context.record_host(host)

    user = effects.get("compromise_user") or effects.get("current_user") or effects.get("set_current_user")
    if user:
        context.record_user(user)

    if "current_target" in effects:
        context.current_target = effects.get("current_target")
    if "current_exfil_domain" in effects:
        context.current_exfil_domain = effects.get("current_exfil_domain")


def apply_attacker_action(
    context: AttackerContext, action: Dict[str, Any], effects: Optional[Dict[str, Any]] = None
) -> None:
    if effects:
        _apply_action_effects(context, effects)
        action_type = action.get("action_type")
        params = action.get("params") or {}
        if action_type in ("exfiltrate", "exfiltrate_alt") and not context.current_exfil_domain:
            context.current_exfil_domain = params.get("destination_domain")
        return
    action_type = action.get("action_type")
    params = action.get("params") or {}
    if action_type == "reuse_credentials":
        context.record_user(params.get("user"))
        context.record_host(params.get("host"))
        context.has_creds = True
        return
    if action_type in ("lateral_move", "lateral_move_alt"):
        context.record_host(params.get("dst"))
        context.has_admin = True
        return
    if action_type == "access_data":
        context.current_target = params.get("target")
        context.has_stage = True
        return
    if action_type in ("exfiltrate", "exfiltrate_alt"):
        context.current_exfil_domain = params.get("destination_domain")
        return
    if action_type == "establish_persistence":
        context.has_persistence = True
        return


def _requires_satisfied(
    requires: Dict[str, Any], attacker_context: Optional[AttackerContext]
) -> bool:
    if not requires:
        return True
    if attacker_context is None:
        return False

    for key, expected in requires.items():
        if key == "foothold":
            actual = bool(attacker_context.compromised_hosts)
        elif key == "has_creds":
            actual = attacker_context.has_creds
        elif key == "has_admin":
            actual = attacker_context.has_admin
        elif key == "has_stage":
            actual = attacker_context.has_stage
        elif key == "has_persistence":
            actual = attacker_context.has_persistence
        elif key == "current_host":
            actual = attacker_context.current_host
        elif key == "current_user":
            actual = attacker_context.current_user
        elif key == "current_target":
            actual = attacker_context.current_target
        else:
            actual = getattr(attacker_context, key, None)

        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        else:
            if actual != expected:
                return False
    return True


def advance_state(
    current_state: str,
    containment: ContainmentActions,
    context: ScenarioContext,
    attacker_action: Optional[Dict[str, Any]] = None,
    attacker_context: Optional[AttackerContext] = None,
    attack_graph: Optional[Dict[str, Any]] = None,
) -> AdvanceResult:
    # Default behavior: legacy linear state machine.
    if attacker_action is None:
        if context.attacker_domain in containment.blocked_domains:
            return AdvanceResult(current_state, True, "attacker_domain_blocked")
        if context.patient_zero_host in containment.isolated_hosts:
            return AdvanceResult(current_state, True, "patient_zero_isolated")
        if context.compromised_user in containment.reset_users:
            return AdvanceResult(current_state, True, "compromised_user_reset")

        idx = STATE_INDEX.get(current_state, 0)
        if idx >= len(STATES) - 1:
            return AdvanceResult(current_state, False, "terminal_state")

        return AdvanceResult(STATES[idx + 1], False, "advanced")

    action_type = attacker_action.get("action_type")
    params = attacker_action.get("params") or {}
    if not action_type or action_type == "no_op":
        return AdvanceResult(current_state, True, "no_op")

    # Action-specific containment gating for realism.
    if action_type == "reuse_credentials":
        if params.get("user") in containment.reset_users:
            return AdvanceResult(current_state, True, "user_reset")
    if action_type in ("lateral_move", "lateral_move_alt"):
        if attacker_context and not attacker_context.compromised_hosts:
            return AdvanceResult(current_state, True, "no_foothold")
        src = params.get("src")
        if src in containment.isolated_hosts:
            return AdvanceResult(current_state, True, "src_host_isolated")
        if attacker_context and attacker_context.compromised_hosts:
            if src not in attacker_context.compromised_hosts:
                return AdvanceResult(current_state, True, "src_host_uncompromised")
    if action_type == "access_data":
        if attacker_context and attacker_context.current_host is None:
            return AdvanceResult(current_state, True, "no_current_host")
        if attacker_context and attacker_context.current_host in containment.isolated_hosts:
            return AdvanceResult(current_state, True, "current_host_isolated")
    if action_type in ("exfiltrate", "exfiltrate_alt"):
        if attacker_context and attacker_context.current_host is None:
            return AdvanceResult(current_state, True, "no_current_host")
        if params.get("destination_domain") in containment.blocked_domains:
            return AdvanceResult(current_state, True, "destination_blocked")
        if attacker_context and attacker_context.current_host in containment.isolated_hosts:
            return AdvanceResult(current_state, True, "current_host_isolated")

    if attack_graph:
        objectives = attack_graph.get("objectives") if isinstance(attack_graph.get("objectives"), list) else None
        if objectives and current_state not in objectives:
            return AdvanceResult(current_state, True, "objective_state_blocked")
        state_node = (attack_graph.get("states") or {}).get(current_state)
        actions = state_node.get("actions") if state_node else None
        if actions:
            has_action = any(a.get("action_type") == action_type for a in actions)
            requires_failed = False
            params_failed = False
            matched = None
            for action in actions:
                if action.get("action_type") != action_type:
                    continue
                requires = action.get("requires") or {}
                if requires and not _requires_satisfied(requires, attacker_context):
                    requires_failed = True
                    continue
                match_params = action.get("match_params") or {}
                if match_params:
                    if any(params.get(k) != v for k, v in match_params.items()):
                        params_failed = True
                        continue
                matched = action
                break

            if matched:
                next_state = matched.get("next_state") or ACTION_STATE_FALLBACK.get(
                    action_type, current_state
                )
                if objectives and next_state not in objectives:
                    return AdvanceResult(current_state, True, "objective_next_state_blocked", matched_action=matched)
                return AdvanceResult(next_state, False, "advanced_graph", matched_action=matched)
            if has_action:
                if requires_failed:
                    return AdvanceResult(current_state, True, "action_requires_unsatisfied")
                if params_failed:
                    return AdvanceResult(current_state, True, "action_params_mismatch")
                return AdvanceResult(current_state, True, "action_not_allowed")
            return AdvanceResult(current_state, True, "action_not_allowed")

    # Fallback to default mapping if graph missing.
    next_state = ACTION_STATE_FALLBACK.get(action_type)
    if next_state:
        return AdvanceResult(next_state, False, "advanced_action")

    idx = STATE_INDEX.get(current_state, 0)
    if idx >= len(STATES) - 1:
        return AdvanceResult(current_state, False, "terminal_state")
    return AdvanceResult(STATES[idx + 1], False, "advanced")
