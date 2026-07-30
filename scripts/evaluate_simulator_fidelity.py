from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from _common import PROJECT_ROOT, run_main
from stair_agent.calibration_analysis import two_proportion_z


def event_count(rows: list[dict], name: str) -> int:
    return sum(
        any(event.get("type") == name for event in row["events"])
        for row in rows
    )


def main() -> None:
    sources = sorted(
        (PROJECT_ROOT / "logs").glob(
            "calibration_v1_landing-focused_*.jsonl"
        )
    )
    if not sources:
        raise RuntimeError("找不到 landing-focused calibration telemetry。")
    real_rows = [
        json.loads(line)
        for source in sources
        for line in source.read_text(encoding="utf-8").splitlines()
    ]
    benchmark_path = (
        PROJECT_ROOT
        / "reports"
        / "SIMULATOR_BENCHMARK_V0_1_FIDELITY.json"
    )
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    simulated = benchmark["results"]["baseline"]

    real_steps = len(real_rows)
    real_landings = event_count(real_rows, "landed")
    real_floors = event_count(real_rows, "floor_descended")
    simulated_steps = int(simulated["total_steps"])
    simulated_landings = int(simulated["total_landings"])
    simulated_floors = int(simulated["total_floors"])
    landing_z = two_proportion_z(
        real_landings,
        real_steps,
        simulated_landings,
        simulated_steps,
    )
    floor_z = two_proportion_z(
        real_floors,
        real_steps,
        simulated_floors,
        simulated_steps,
    )
    gates = {
        "real_steps_at_least_300": real_steps >= 300,
        "simulated_steps_at_least_1000": simulated_steps >= 1000,
        "landing_rate_two_proportion_abs_z_le_1_96": abs(landing_z) <= 1.96,
        "floor_rate_two_proportion_abs_z_le_1_96": abs(floor_z) <= 1.96,
        "fixed_seed_benchmark_100_episodes": (
            int(simulated["episodes"]) == 100
        ),
    }
    payload = {
        "schema_version": "simulator-fidelity-gate-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "real_sources": [
            {
                "name": source.name,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
            for source in sources
        ],
        "benchmark": {
            "name": benchmark_path.name,
            "sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        },
        "real": {
            "steps": real_steps,
            "landings": real_landings,
            "floors": real_floors,
            "landing_rate": real_landings / real_steps,
            "floor_rate": real_floors / real_steps,
        },
        "simulator": {
            "steps": simulated_steps,
            "landings": simulated_landings,
            "floors": simulated_floors,
            "landing_rate": simulated_landings / simulated_steps,
            "floor_rate": simulated_floors / simulated_steps,
        },
        "statistics": {
            "landing_two_proportion_z": landing_z,
            "floor_two_proportion_z": floor_z,
            "two_sided_alpha": 0.05,
        },
        "gates": gates,
        "gate_pass": all(gates.values()),
        "scope": (
            "Allows only the bounded simulator learnability probe. "
            "It does not authorize BC, DAgger, RL long training, or real rollout."
        ),
    }
    json_path = (
        PROJECT_ROOT / "reports" / "SIMULATOR_FIDELITY_GATE_V0_1.json"
    )
    md_path = (
        PROJECT_ROOT / "reports" / "SIMULATOR_FIDELITY_GATE_V0_1.md"
    )
    for path in (json_path, md_path):
        if path.exists():
            raise FileExistsError(f"拒絕覆寫 fidelity artifact：{path}")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Simulator Fidelity Gate v0.1",
        "",
        f"- gate pass: **{payload['gate_pass']}**",
        f"- real: {real_landings}/{real_steps} landings "
        f"({real_landings / real_steps:.4f}), "
        f"{real_floors}/{real_steps} floors "
        f"({real_floors / real_steps:.4f})",
        f"- simulator: {simulated_landings}/{simulated_steps} landings "
        f"({simulated_landings / simulated_steps:.4f}), "
        f"{simulated_floors}/{simulated_steps} floors "
        f"({simulated_floors / simulated_steps:.4f})",
        f"- landing two-proportion z: {landing_z:.3f}",
        f"- floor two-proportion z: {floor_z:.3f}",
        "",
        "## Gates",
        "",
    ]
    lines += [
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in gates.items()
    ]
    lines += [
        "",
        "此 gate 只允許固定預算 simulator learnability probe。它不允許 BC、",
        "DAgger、RL 長訓或新增實機 rollout。",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"json={json_path}")
    print(f"report={md_path}")


if __name__ == "__main__":
    run_main(main)
