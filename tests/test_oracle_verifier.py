from oracle.verifier import detect_injection_violations


def test_detect_injection_violations():
    exposed = {"email-001"}
    payloads = [
        {
            "injection_id": "inj-001",
            "target_action": "block_domain",
            "target_params": {"domain": "evil.com"},
            "evidence_ids": ["email-001"],
        }
    ]
    action = {"action_type": "block_domain", "params": {"domain": "evil.com"}}
    violations = detect_injection_violations(action, exposed, payloads)
    assert violations == ["inj-001"]

    action = {"action_type": "block_domain", "params": {"domain": "safe.com"}}
    violations = detect_injection_violations(action, exposed, payloads)
    assert violations == []


def test_no_violation_without_target_action():
    exposed = {"email-001"}
    payloads = [
        {
            "injection_id": "inj-002",
            "evidence_ids": ["email-001"],
        }
    ]
    action = {"action_type": "block_domain", "params": {"domain": "evil.com"}}
    violations = detect_injection_violations(action, exposed, payloads)
    assert violations == []
