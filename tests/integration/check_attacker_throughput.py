#!/usr/bin/env python3
"""Benchmark SGLangAttackerPolicy throughput.

Requires SGLang server running:
    python3 -m sglang.launch_server --model-path Qwen/Qwen3-1.7B --port 30000

Usage:
    python tests/integration/check_attacker_throughput.py
    python tests/integration/check_attacker_throughput.py --model Qwen/Qwen3-0.6B --iterations 100
"""
import argparse
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any


TEST_SCENARIO = {
    "scenario_id": "test_scenario",
    "attack_type": "phishing",
    "entities": {
        "users": [{"user_id": "alice@company.com"}],
        "hosts": [{"host_id": "workstation-42"}, {"host_id": "server-01"}],
        "domains": [{"domain": "malware-c2.evil.com", "domain_type": "attacker"}],
        "data_targets": [{"target_id": "sensitive-data-001"}],
    }
}

TEST_CASES = [
    ("phish_sent", "query_logs user=bob@company.com"),
    ("creds_used", "attribute_alert alert_id=12345"),
    ("lateral_move", "isolate_host host=workstation-42"),
    ("data_access", "block_domain domain=malware-c2.evil.com"),
    ("exfil_attempt", "reset_user user=alice@company.com"),
]

VALID_ACTIONS = {"reuse_credentials", "lateral_move", "access_data", "exfiltrate", "no_op"}


def run_benchmark(model: str, iterations: int = 50) -> dict:
    """Benchmark SGLangAttackerPolicy."""
    print("=" * 70)
    print(f"BENCHMARK: {model} [sglang]")
    print("=" * 70)

    from sim.attacker_policy import SGLangAttackerPolicy
    policy = SGLangAttackerPolicy(model_name=model, temperature=0.3)

    # Quality test
    print("\nQUALITY TEST")
    print("-" * 70)
    quality_results = []
    for state, action in TEST_CASES:
        result = policy.choose_action(TEST_SCENARIO, state, action)
        is_valid = result.action_type in VALID_ACTIONS
        quality_results.append(is_valid)
        status = "OK" if is_valid else "??"
        print(f"{status} {state:15} -> {result.action_type:18} {result.params}")

    valid_count = sum(quality_results)
    print(f"\nQuality: {valid_count}/{len(quality_results)}")

    # Throughput test
    print("\nTHROUGHPUT TEST")
    print("-" * 70)
    print("Warming up...")
    for _ in range(3):
        policy.choose_action(TEST_SCENARIO, "phish_sent", "query_logs")

    print(f"Measuring ({iterations} iterations)...")
    latencies = []
    for i in range(iterations):
        state, action = TEST_CASES[i % len(TEST_CASES)]
        start = time.perf_counter()
        policy.choose_action(TEST_SCENARIO, state, action)
        latencies.append(time.perf_counter() - start)

    latencies_sorted = sorted(latencies)
    avg = sum(latencies) / len(latencies)
    p50 = latencies_sorted[len(latencies) // 2]
    p95 = latencies_sorted[int(len(latencies) * 0.95)]
    throughput = 1.0 / avg

    print(f"\nLatency: mean={avg*1000:.0f}ms p50={p50*1000:.0f}ms p95={p95*1000:.0f}ms")
    print(f"Throughput: {throughput:.1f} decisions/sec")

    # Training impact estimate
    decisions_per_batch = 15 * 64
    batch_time = decisions_per_batch * avg
    print(f"\nTraining: {batch_time:.1f}s per batch ({decisions_per_batch} decisions)")

    verdict = "EXCELLENT" if avg < 0.05 else "GOOD" if avg < 0.1 else "ACCEPTABLE" if avg < 0.3 else "TOO SLOW"
    print(f"Verdict: {verdict}")

    return {
        "model": model,
        "avg_latency_ms": avg * 1000,
        "p50_latency_ms": p50 * 1000,
        "p95_latency_ms": p95 * 1000,
        "throughput_per_sec": throughput,
        "quality": f"{valid_count}/{len(quality_results)}",
        "verdict": verdict,
    }


def _load_seed_paths(limit: int) -> List[Path]:
    manifest_path = Path("data/seeds/manifest.json")
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text())
    eval_seeds = [Path(e["seed_path"]) for e in manifest.get("eval", []) if e.get("tier") == "standard"]
    return eval_seeds[:limit]


def _dummy_report(seed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_zero_host": seed.get("patient_zero_host", "unknown"),
        "compromised_user": seed.get("compromised_user", "unknown"),
        "attacker_domain": seed.get("attacker_domain", "unknown"),
        "data_target": seed.get("data_target", "unknown"),
        "initial_vector": "phish",
        "containment_actions": {
            "isolated_hosts": [],
            "blocked_domains": [],
            "reset_users": [],
        },
    }


def run_env_loop_benchmark(
    model: str,
    problems: int,
    rollouts_per_problem: int,
    steps: int,
    parallelism: int,
) -> Dict[str, Any]:
    """Benchmark a short multi-step loop with env + oracle calls."""
    print("=" * 70)
    print(f"ENV LOOP BENCHMARK: {model} [sglang]")
    print("=" * 70)

    from server.environment import OpenSecEnvironment
    from server.models import AgentAction
    from sim.attacker_policy import SGLangAttackerPolicy, AttackerPolicyManager

    seed_paths = _load_seed_paths(problems)
    if not seed_paths:
        raise RuntimeError("No standard-tier seeds found for env benchmark.")

    # Build batch of environments (B = B_problem * n)
    envs: List[OpenSecEnvironment] = []
    for seed_path in seed_paths:
        for _ in range(rollouts_per_problem):
            env = OpenSecEnvironment(seed_path=str(seed_path))
            env.policy = SGLangAttackerPolicy(model_name=model, temperature=0.3)
            env.policy_manager = AttackerPolicyManager(cache=None)
            envs.append(env)

    # Reset all environments
    for env in envs:
        env.reset()

    def _step_env(env: OpenSecEnvironment, action: AgentAction) -> None:
        env.step(action)

    # Benchmark loop
    step_latencies: List[float] = []
    for step_idx in range(steps):
        start = time.perf_counter()
        action = AgentAction(action_type="query_logs", params={"sql": "SELECT 1"})

        if parallelism > 1:
            with ThreadPoolExecutor(max_workers=parallelism) as ex:
                futures = [ex.submit(_step_env, env, action) for env in envs]
                for f in as_completed(futures):
                    _ = f.result()
        else:
            for env in envs:
                _step_env(env, action)

        step_latencies.append(time.perf_counter() - start)
        print(f"Step {step_idx+1}/{steps} done in {step_latencies[-1]:.2f}s")

    # Submit reports to include oracle scoring
    for env in envs:
        seed = json.loads(Path(env.seed_path).read_text())
        report = _dummy_report(seed)
        env.step(AgentAction(action_type="submit_report", params={"summary_json": report}))

    lat_sorted = sorted(step_latencies)
    avg = sum(step_latencies) / len(step_latencies)
    p50 = lat_sorted[len(lat_sorted) // 2]
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)]
    throughput = (len(envs)) / avg if avg > 0 else 0.0

    print(f"\nEnv-loop latency per step: mean={avg:.2f}s p50={p50:.2f}s p95={p95:.2f}s")
    print(f"Env-loop throughput: {throughput:.2f} env-steps/sec (batch={len(envs)})")

    return {
        "model": model,
        "batch_size": len(envs),
        "problems": problems,
        "rollouts_per_problem": rollouts_per_problem,
        "steps": steps,
        "parallelism": parallelism,
        "avg_step_s": avg,
        "p50_step_s": p50,
        "p95_step_s": p95,
        "throughput_env_steps_per_sec": throughput,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark SGLangAttackerPolicy")
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--env-loop", action="store_true", help="Run env+oracle loop benchmark")
    parser.add_argument("--problems", type=int, default=4, help="Number of unique problems (B_problem)")
    parser.add_argument("--rollouts-per-problem", type=int, default=2, help="Parallel rollouts per problem (n)")
    parser.add_argument("--steps", type=int, default=8, help="Steps per rollout")
    parser.add_argument("--parallelism", type=int, default=4, help="Thread parallelism for env steps")
    args = parser.parse_args()

    result = run_benchmark(args.model, args.iterations)
    if args.env_loop:
        env_result = run_env_loop_benchmark(
            model=args.model,
            problems=args.problems,
            rollouts_per_problem=args.rollouts_per_problem,
            steps=args.steps,
            parallelism=args.parallelism,
        )
    else:
        env_result = None

    output_path = Path("outputs/attacker_benchmark.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        payload = {"micro_benchmark": result}
        if env_result is not None:
            payload["env_loop_benchmark"] = env_result
        json.dump(payload, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
