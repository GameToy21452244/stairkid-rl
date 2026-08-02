from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import _common  # noqa: F401,E402

from stair_agent.learnability import baseline_selector, evaluate_candidate
from stair_agent.simulator.gates import (
    evaluation_summary,
    oracle_selector,
    run_reachability_gate,
)
from stair_agent.simulator.state import ShaftEnvConfig


SEEDS = tuple(range(100))
MAX_EPISODE_STEPS = 600


def timed_evaluation(name, selector, config, *, success_floor=None):
    started = perf_counter()
    result = evaluate_candidate(
        name,
        selector,
        seeds=SEEDS,
        max_episode_steps=MAX_EPISODE_STEPS,
        config=config,
        success_floor=success_floor,
    )
    elapsed = perf_counter() - started
    payload = evaluation_summary(result)
    payload["elapsed_seconds"] = elapsed
    payload["simulation_steps_per_second"] = result.total_steps / max(elapsed, 1e-9)
    payload["mean_action_duration_ms"] = 1000.0 / config.fps
    payload["oscillation_rate"] = result.direction_switches / max(1, result.total_steps)
    payload["missed_platform_proxy_rate"] = (
        result.terminal_reasons.get("bottom", 0) / result.episodes
    )
    return result, payload


def main() -> int:
    artifacts = Path("artifacts")
    reports = Path("reports")
    artifacts.mkdir(exist_ok=True)
    reports.mkdir(exist_ok=True)

    config8 = ShaftEnvConfig(distribution="easy", fps=8)
    reach100 = run_reachability_gate(100, config=config8)
    reach1000 = run_reachability_gate(1000, config=config8)

    evaluations = {}
    raw_results = {}
    for frequency in (8, 10, 12):
        config = ShaftEnvConfig(distribution="easy", fps=frequency)
        raw_oracle, oracle = timed_evaluation(
            f"oracle_full_{frequency}hz",
            oracle_selector(),
            config,
            success_floor=10,
        )
        raw_baseline, baseline = timed_evaluation(
            f"baseline_{frequency}hz",
            baseline_selector(),
            config,
        )
        evaluations[str(frequency)] = {
            "oracle_full": oracle,
            "baseline": baseline,
        }
        raw_results[(frequency, "oracle_full")] = raw_oracle
        raw_results[(frequency, "baseline")] = raw_baseline

    from stair_agent.learnability import random_selector, release_selector

    raw_random, random_payload = timed_evaluation(
        "random_8hz", random_selector, config8
    )
    raw_release, release_payload = timed_evaluation(
        "release_8hz", release_selector, config8
    )
    evaluations["8"]["random"] = random_payload
    evaluations["8"]["release"] = release_payload
    raw_results[(8, "random")] = raw_random
    raw_results[(8, "release")] = raw_release

    oracle8 = evaluations["8"]["oracle_full"]
    baseline8 = evaluations["8"]["baseline"]
    oracle_pass = oracle8["reach_rate_floor_10"] >= 0.95
    baseline_pass = (
        baseline8["mean_floors"] >= 5.0
        and baseline8["success_rate_floor_3"] >= 0.90
        and baseline8["mean_floors"] > random_payload["mean_floors"]
        and baseline8["mean_floors"] > release_payload["mean_floors"]
    )
    gates = {
        "reachability_100": asdict(reach100),
        "reachability_1000": asdict(reach1000),
        "oracle_full": {
            "passed": oracle_pass,
            "threshold": ">=95% reach floor 10",
        },
        "baseline": {
            "passed": baseline_pass,
            "threshold": "mean>=5, >=90% reach floor 3, >random/release",
        },
    }

    baseline_floors = {
        result.seed: result.floors
        for result in raw_results[(8, "baseline")].episode_results
    }
    paired = {}
    for comparison in ("random", "release"):
        other = {
            result.seed: result.floors
            for result in raw_results[(8, comparison)].episode_results
        }
        differences = [baseline_floors[seed] - other[seed] for seed in SEEDS]
        paired[f"baseline_minus_{comparison}"] = {
            "mean": sum(differences) / len(differences),
            "positive_fraction": sum(value > 0 for value in differences) / len(differences),
        }

    payload = {
        "environment_version": config8.environment_version,
        "physics_hz": config8.physics_hz,
        "seeds": list(SEEDS),
        "max_episode_steps": MAX_EPISODE_STEPS,
        "gates": gates,
        "evaluations": evaluations,
        "paired_differences": paired,
    }
    (artifacts / "simulator_v02_gate_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    columns = (
        "frequency_hz",
        "candidate",
        "mean_floors",
        "median_floors",
        "std_floors",
        "ci95_low",
        "ci95_high",
        "success_floor_3",
        "success_floor_10",
        "missed_platform_proxy_rate",
        "brake_too_late_rate",
        "oscillation_rate",
        "mean_action_duration_ms",
        "simulation_steps_per_second",
    )
    with (artifacts / "control_frequency_results.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for frequency, candidates in evaluations.items():
            for candidate, item in candidates.items():
                writer.writerow(
                    {
                        "frequency_hz": frequency,
                        "candidate": candidate,
                        "mean_floors": item["mean_floors"],
                        "median_floors": item["median_floors"],
                        "std_floors": item["std_floors"],
                        "ci95_low": item["floors_bootstrap_ci95"][0],
                        "ci95_high": item["floors_bootstrap_ci95"][1],
                        "success_floor_3": item["success_rate_floor_3"],
                        "success_floor_10": item["success_rate_floor_10"],
                        "missed_platform_proxy_rate": item["missed_platform_proxy_rate"],
                        "brake_too_late_rate": "not_observable",
                        "oscillation_rate": item["oscillation_rate"],
                        "mean_action_duration_ms": item["mean_action_duration_ms"],
                        "simulation_steps_per_second": item["simulation_steps_per_second"],
                    }
                )

    lines = [
        "# Control Frequency Experiment",
        "",
        "日期：2026-07-30",
        "",
        "固定 physics 60 Hz；相同 100 easy seeds 比較 policy 8／10／12 Hz。",
        "真實遊戲仍維持約 8 Hz，本實驗不會送出真實輸入。",
        "",
        "| Hz | candidate | mean floors | median | 95% CI | reach 3 | reach 10 | oscillation | steps/s |",
        "|---:|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for frequency in ("8", "10", "12"):
        for candidate in ("oracle_full", "baseline"):
            item = evaluations[frequency][candidate]
            lines.append(
                f"| {frequency} | {candidate} | {item['mean_floors']:.3f} | "
                f"{item['median_floors']:.3f} | "
                f"[{item['floors_bootstrap_ci95'][0]:.3f}, "
                f"{item['floors_bootstrap_ci95'][1]:.3f}] | "
                f"{item['success_rate_floor_3']:.1%} | "
                f"{item['success_rate_floor_10']:.1%} | "
                f"{item['oscillation_rate']:.4f} | "
                f"{item['simulation_steps_per_second']:.1f} |"
            )
    lines.extend(
        [
            "",
            "`missed_platform_proxy_rate` 目前以 bottom death 代理；",
            "`brake_too_late` 無可靠直接觀測，CSV 明確標為 `not_observable`，",
            "不可當成 0。控制率選擇需依整體 gate 結果，不只看 throughput。",
        ]
    )
    (reports / "CONTROL_FREQUENCY_EXPERIMENT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(gates, ensure_ascii=False, indent=2))
    return 0 if reach100.passed and reach1000.passed and oracle_pass and baseline_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
