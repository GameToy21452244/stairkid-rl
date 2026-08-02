from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import PROJECT_ROOT, run_main

from stair_agent.real_game_gate import (
    REAL_GAME_GATE_VERSION,
    apply_video_floor_maxima,
    reclassify_real_micro_episode,
    summarize_real_micro_gate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "以既有實機 controller sidecar 重算目前版本的 "
            "Teacher Real Micro Gate；"
            "不開啟遊戲、不載入輸入後端、不送出按鍵。"
        )
    )
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument(
        "--floor-video-audit",
        type=Path,
        help=(
            "可選：使用同一 run 的離線 MP4 HUD audit，僅允許向上修正"
            " sidecar 漏掉的 terminal-frame 樓層。"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            PROJECT_ROOT
            / "artifacts"
            / (
                "p36_teacher_real_gate_v"
                f"{REAL_GAME_GATE_VERSION}_reclassification.json"
            )
        ),
    )
    return parser.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise RuntimeError(
                    f"{path}:{line_number} 不是 JSON object。"
                )
            rows.append(payload)
    return rows


def main() -> None:
    args = parse_args()
    gate_path = args.gate.resolve()
    output_path = args.output.resolve()
    if not gate_path.is_file():
        raise RuntimeError(f"找不到來源 Gate：{gate_path}")
    if output_path.exists():
        raise RuntimeError(f"拒絕覆寫既有 artifact：{output_path}")

    source = json.loads(gate_path.read_text(encoding="utf-8"))
    source_episodes = source.get("episodes", [])
    if not isinstance(source_episodes, list) or not source_episodes:
        raise RuntimeError("來源 Gate 沒有 episode records。")

    episodes: list[dict[str, Any]] = []
    sidecars: list[dict[str, Any]] = []
    for episode in source_episodes:
        controller_path = Path(str(episode.get("controller_path", "")))
        if not controller_path.is_file():
            raise RuntimeError(f"找不到 controller sidecar：{controller_path}")
        controller_rows = _read_jsonl(controller_path)
        expected = int(episode.get("controller_records", -1))
        if expected != len(controller_rows):
            raise RuntimeError(
                f"sidecar 筆數不一致：{controller_path} "
                f"expected={expected} actual={len(controller_rows)}"
            )
        episodes.append(
            reclassify_real_micro_episode(episode, controller_rows)
        )
        sidecars.append(
            {
                "episode": episode.get("episode"),
                "path": str(controller_path.resolve()),
                "records": len(controller_rows),
            }
        )

    floor_video_audit: dict[str, Any] | None = None
    if args.floor_video_audit is not None:
        floor_video_path = args.floor_video_audit.resolve()
        if not floor_video_path.is_file():
            raise RuntimeError(f"找不到 floor video audit：{floor_video_path}")
        floor_video_audit = json.loads(
            floor_video_path.read_text(encoding="utf-8")
        )
        source_run = Path(
            str(floor_video_audit.get("source_run", ""))
        ).resolve()
        if source_run != gate_path.parent.resolve():
            raise RuntimeError(
                "floor video audit 與 Gate 不是同一個 run："
                f"audit={source_run} gate={gate_path.parent.resolve()}"
            )
        video_checks = floor_video_audit.get("checks", {})
        required_video_checks = (
            "all_videos_read",
            "counter_available_every_frame",
            "initial_floor_one",
        )
        failed_video_checks = [
            name
            for name in required_video_checks
            if video_checks.get(name) is not True
        ]
        if failed_video_checks:
            raise RuntimeError(
                "floor video audit 缺少可信度條件："
                + ", ".join(failed_video_checks)
            )
        observed_maxima = floor_video_audit.get("observed_max_floors")
        if not isinstance(observed_maxima, list):
            raise RuntimeError("floor video audit 缺少 observed_max_floors。")
        episodes = apply_video_floor_maxima(episodes, observed_maxima)

    source_limits = source.get("limits", {})
    expected_episodes = (
        int(source_limits["episodes"])
        if isinstance(source_limits, dict)
        and source_limits.get("episodes") is not None
        else None
    )
    result = summarize_real_micro_gate(
        episodes,
        safety_events=source.get("safety_events", []),
        dry_run=bool(source.get("dry_run", False)),
        expected_episodes=expected_episodes,
    )
    result["audit"] = {
        "mode": "recorded-controller-sidecar-reclassification",
        "source_gate": str(gate_path),
        "source_experiment": source.get("experiment"),
        "source_expected_episodes": expected_episodes,
        "sidecars": sidecars,
        "controller_policy_changed": False,
        "game_input_sent": False,
        "semantic_change": (
            "endless-run terminal labels no longer penalize all bottom deaths; "
            "only bottom failures before floor 3 consume the reach-floor-3 "
            "miss budget. Special-contact braking permits one entry brake and "
            "one brake for the single allowed reversal, with an absolute max "
            "of two. A trusted same-run video replay may only raise a sidecar "
            "floor maximum missed on the terminal frame"
        ),
        "evidence_limit": (
            "此結果可判定來源 run 在目前 Gate 語意下是否通過，因控制器、"
            "輸入與原始 sidecar 均未改變；它不取代後續獨立 10 回合"
            "穩定性 Gate，也不授權 P4.0 Student 正式訓練。"
        ),
    }
    if floor_video_audit is not None:
        result["audit"]["floor_video_audit"] = {
            "path": str(args.floor_video_audit.resolve()),
            "source_run": floor_video_audit.get("source_run"),
            "observed_max_floors": floor_video_audit.get(
                "observed_max_floors"
            ),
            "trusted_checks": {
                name: floor_video_audit["checks"].get(name)
                for name in (
                    "all_videos_read",
                    "counter_available_every_frame",
                    "initial_floor_one",
                )
            },
            "expected_manual_max_match_required": False,
            "game_input_sent": False,
        }
    if "limits" in source:
        result["limits"] = source["limits"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Gate v{REAL_GAME_GATE_VERSION} reclassification："
        f"{result['gate']['status']}"
    )
    print(f"Artifact：{output_path}")


if __name__ == "__main__":
    run_main(main)
