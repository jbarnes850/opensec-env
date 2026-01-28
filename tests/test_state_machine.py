from sim.attacker_state_machine import (
    AttackerContext,
    ContainmentActions,
    ScenarioContext,
    advance_state,
    apply_attacker_action,
)


def test_advance_uncontained():
    ctx = ScenarioContext(
        attacker_domain="evil-mail.com",
        patient_zero_host="h-001",
        compromised_user="u-001",
    )
    containment = ContainmentActions([], [], [])

    r1 = advance_state("phish_sent", containment, ctx)
    assert r1.next_state == "creds_used"
    assert r1.stalled is False

    r2 = advance_state("creds_used", containment, ctx)
    assert r2.next_state == "lateral_move"


def test_stall_on_containment():
    ctx = ScenarioContext(
        attacker_domain="evil-mail.com",
        patient_zero_host="h-001",
        compromised_user="u-001",
    )

    r1 = advance_state(
        "creds_used",
        ContainmentActions([], ["evil-mail.com"], []),
        ctx,
    )
    assert r1.stalled is True
    assert r1.next_state == "creds_used"

    r2 = advance_state(
        "creds_used",
        ContainmentActions(["h-001"], [], []),
        ctx,
    )
    assert r2.stalled is True

    r3 = advance_state(
        "creds_used",
        ContainmentActions([], [], ["u-001"]),
        ctx,
    )
    assert r3.stalled is True


def test_advance_with_action_graph():
    ctx = ScenarioContext(
        attacker_domain="evil-mail.com",
        patient_zero_host="h-001",
        compromised_user="u-001",
    )
    containment = ContainmentActions([], [], [])
    attacker_ctx = AttackerContext(compromised_hosts=["h-001"])
    graph = {
        "states": {
            "creds_used": {
                "actions": [
                    {"action_type": "lateral_move", "next_state": "lateral_move"},
                ]
            }
        }
    }
    action = {"action_type": "lateral_move", "params": {"src": "h-001", "dst": "h-002"}}
    result = advance_state(
        "creds_used",
        containment,
        ctx,
        attacker_action=action,
        attacker_context=attacker_ctx,
        attack_graph=graph,
    )
    assert result.next_state == "lateral_move"
    assert result.stalled is False


def test_graph_requires_and_effects():
    ctx = ScenarioContext(
        attacker_domain="evil-mail.com",
        patient_zero_host="h-001",
        compromised_user="u-001",
    )
    containment = ContainmentActions([], [], [])
    attacker_ctx = AttackerContext()
    graph = {
        "states": {
            "access": {
                "actions": [
                    {
                        "action_type": "reuse_credentials",
                        "requires": {"has_creds": True},
                        "next_state": "persistence",
                        "effects": {"has_creds": True, "compromise_host": "h-001"},
                    }
                ]
            }
        }
    }
    action = {"action_type": "reuse_credentials", "params": {"user": "u-001", "host": "h-001"}}

    result = advance_state(
        "access",
        containment,
        ctx,
        attacker_action=action,
        attacker_context=attacker_ctx,
        attack_graph=graph,
    )
    assert result.stalled is True
    assert result.reason == "action_requires_unsatisfied"

    attacker_ctx.has_creds = True
    result = advance_state(
        "access",
        containment,
        ctx,
        attacker_action=action,
        attacker_context=attacker_ctx,
        attack_graph=graph,
    )
    assert result.stalled is False
    assert result.matched_action is not None

    apply_attacker_action(attacker_ctx, action, effects=result.matched_action.get("effects"))
    assert attacker_ctx.has_creds is True
    assert attacker_ctx.current_host == "h-001"
