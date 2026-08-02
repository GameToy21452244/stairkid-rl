from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from stair_agent.state_aliasing import audit_state_aliasing, load_real_gate_rows


DEFAULT_GATE = (
    REPOSITORY_ROOT
    / "artifacts"
    / "p36_teacher_real_gate_v11_reclassification_20260803_034023_v2.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the offline P4.0 real-game state-aliasing audit."
    )
    parser.add_argument("--gate-artifact", type=Path, default=DEFAULT_GATE)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPOSITORY_ROOT / "artifacts" / "state_aliasing_audit.json",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=REPOSITORY_ROOT / "artifacts" / "state_aliasing_summary.csv",
    )
    parser.add_argument(
        "--conflicts-csv",
        type=Path,
        default=REPOSITORY_ROOT / "artifacts" / "teacher_action_conflicts.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPOSITORY_ROOT / "reports" / "STATE_ALIASING_AUDIT.md",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _prepare_outputs(paths: list[Path], *, overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not overwrite:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"refusing to overwrite existing outputs: {joined}")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def _write_summary(path: Path, result: dict) -> None:
    fieldnames = [
        "scope",
        "category",
        "representation",
        "rows",
        "neighbor_disagreement",
        "conditional_entropy_bits",
        "knn_action_accuracy",
        "mean_neighbor_distance",
        "memory_dimensions",
        "coverage_sufficient",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        total_rows = result["dataset"]["rows"]
        for name, metrics in result["representations"].items():
            writer.writerow(
                {
                    "scope": "overall",
                    "category": "all",
                    "representation": name,
                    "rows": total_rows,
                    "neighbor_disagreement": metrics["neighbor_disagreement"],
                    "conditional_entropy_bits": metrics["conditional_entropy_bits"],
                    "knn_action_accuracy": metrics["knn_action_accuracy"],
                    "mean_neighbor_distance": metrics["mean_neighbor_distance"],
                    "memory_dimensions": metrics["memory_dimensions"],
                    "coverage_sufficient": True,
                }
            )
        for branch, payload in result["branches"].items():
            for representation in ("observation_only", "causal_full_memory"):
                metrics = payload[representation]
                writer.writerow(
                    {
                        "scope": "branch",
                        "category": branch,
                        "representation": representation,
                        "rows": payload["rows"],
                        "neighbor_disagreement": metrics["row_disagreement"],
                        "conditional_entropy_bits": metrics["row_entropy"],
                        "knn_action_accuracy": metrics["row_correct"],
                        "mean_neighbor_distance": "",
                        "memory_dimensions": "",
                        "coverage_sufficient": payload[
                            "coverage_sufficient_for_directional_read"
                        ],
                    }
                )


def _write_conflicts(path: Path, conflicts: list[dict]) -> None:
    if not conflicts:
        path.write_text("query_source\n", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(conflicts[0]))
        writer.writeheader()
        writer.writerows(conflicts)


def _percentage(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def _write_report(path: Path, result: dict) -> None:
    dataset = result["dataset"]
    gate = result["gate"]
    effect = result["causal_memory_effect"]
    representations = result["representations"]
    observation = representations["observation_only"]
    causal = representations["causal_full_memory"]
    leakage = representations["post_decision_leakage_ceiling"]
    bootstrap = effect["bootstrap"]
    exact = result["exact_conflicts"]
    rounded = result["rounded_3_decimal_conflicts"]
    feature = result["feature_audit"]
    status_text = "PASS" if gate["passed"] else "FAIL / STOP"

    checks = "\n".join(
        f"- {'PASS' if passed else 'FAIL'}：`{name}`"
        for name, passed in gate["checks"].items()
    )
    representation_rows = "\n".join(
        "| {name} | {disagreement} | {entropy:.4f} | {accuracy} | {dimensions} |".format(
            name=name,
            disagreement=_percentage(metrics["neighbor_disagreement"]),
            entropy=metrics["conditional_entropy_bits"],
            accuracy=_percentage(metrics["knn_action_accuracy"]),
            dimensions=metrics["memory_dimensions"],
        )
        for name, metrics in representations.items()
    )
    branch_rows = "\n".join(
        "| {branch} | {rows} | {coverage} | {base} | {causal} |".format(
            branch=branch,
            rows=payload["rows"],
            coverage=(
                "yes"
                if payload["coverage_sufficient_for_directional_read"]
                else "no"
            ),
            base=_percentage(payload["observation_only"]["row_disagreement"]),
            causal=_percentage(payload["causal_full_memory"]["row_disagreement"]),
        )
        for branch, payload in result["branches"].items()
    )
    prediction_rows = "\n".join(
        "| {name} | {accuracy} | {agreement} | {entropy:.4f} |".format(
            name=name,
            accuracy=_percentage(metrics["knn_accuracy"]),
            agreement=_percentage(metrics["neighbor_agreement"]),
            entropy=metrics["conditional_entropy_bits"],
        )
        for name, metrics in result["predictability"].items()
    )
    failed = [name for name, passed in gate["checks"].items() if not passed]
    if gate["passed"]:
        conclusion = (
            "Causal deployable memory 對跨回合近鄰衝突有穩定且達門檻的改善，"
            "因此只解鎖 P4.1 的公平 S0/S1/S2/S3 smoke ablation；仍未授權長訓練。"
        )
    else:
        conclusion = (
            "P4.0 Gate 未通過，依最高優先策略在此停止。不得開始 P4.1、rare-branch "
            "dataset、BC、DAgger、PPO、DQN 或 NEAT。下一步應先處理失敗檢查："
            + ", ".join(failed)
            + "。"
        )

    report = f"""# P4.0 State-Aliasing Audit

日期：{result['generated_at']}

狀態：**{status_text}**

## 結論

{conclusion}

本報告只使用已通過 Gate v11 的 10 回合實機 Teacher natural run，不送出任何遊戲
按鍵，也沒有啟動 Student 訓練。主資料共 {dataset['episodes']} 回合、{dataset['rows']}
筆、每筆 {dataset['observation_dimensions']} 維。動作數為
`{json.dumps(dataset['action_counts'], ensure_ascii=False)}`。

## 最重要的時間序發現

`controller_memory` 是 `policy.choose(observation)` 完成後才寫入 sidecar。同一步的
`previous_action` 已等於本步 label，`controller_phase` 也由本步 Teacher reason 產生；
把它直接當 Student 輸入會洩漏答案。因此：

- 正式比較使用 episode 內 `memory[t-1] -> decision[t]`；
- 每回合第 0 步使用空白／reset memory；
- 同一步 post-decision memory 只列為 leakage ceiling，完全排除 Gate；
- raw platform/track ID 全部排除，避免不可部署的 ID 對齊。

## 預先固定的 Audit protocol

- kNN：k={result['protocol']['k']}，鄰居只能來自其他回合；
- 距離：各 feature z-score，observation 與 memory block 各佔 0.5；
- Gate：衝突相對下降至少 10%，paired episode bootstrap 95% CI 下界不得為負，
  並且 entropy 至少下降 0.05 bits 或 action accuracy 至少增加 3 percentage points；
- bootstrap：{bootstrap['samples']} 次，seed={bootstrap['seed']}。

## 整體結果

| representation | action disagreement | entropy (bits) | kNN action accuracy | memory dims |
|---|---:|---:|---:|---:|
{representation_rows}

Causal full memory 的相對衝突改善為
**{_percentage(effect['relative_disagreement_reduction'])}**，entropy 改善
**{effect['entropy_reduction_bits']:.4f} bits**，accuracy 改善
**{100.0 * effect['accuracy_gain']:.2f} percentage points**。episode-level paired
bootstrap 的平均 disagreement 改善為 {bootstrap['mean']:.4f}，95% CI
[{bootstrap['ci95_low']:.4f}, {bootstrap['ci95_high']:.4f}]。

Post-decision leakage ceiling 的 disagreement 為
{_percentage(leakage['neighbor_disagreement'])}；這個數字只能顯示 sidecar 洩漏有多強，
不能作為模型可部署能力。

## Exact 與 near conflict

- 完全相同 observation：{exact['duplicate_groups']} 個重複群、
  {exact['cross_episode_action_conflict_groups']} 個跨回合動作衝突群；
- round-to-3-decimal：{rounded['duplicate_groups']} 個重複群、
  {rounded['cross_episode_action_conflict_groups']} 個跨回合動作衝突群；
- 每個 observation kNN 中出現不同 Teacher 動作的 query 已輸出至
  `artifacts/teacher_action_conflicts.csv`。

## Rare / control branch

| branch | rows | >=10 rows | observation disagreement | causal disagreement |
|---|---:|:---:|---:|---:|
{branch_rows}

少於 10 筆的 branch 僅列描述，不作方向性決策。branch 可重疊，例如 spike 同時可能是
special_escape 或其他 phase。

## Phase / target predictability

| target | kNN accuracy | neighbor agreement | entropy (bits) |
|---|---:|---:|---:|
{prediction_rows}

## Feature audit

- observation active / zero-variance dims：
  {feature['observation_active_dimensions']} / {feature['observation_zero_variance_dimensions']}；
- 重複 active column groups：{len(feature['duplicate_active_column_groups'])}；
- 排除的 raw identifier fields：
  `{json.dumps(feature['raw_identifier_fields_excluded'], ensure_ascii=False)}`；
- causal full memory columns：{len(feature['causal_memory_columns'])}；
- observation 只保留 4-frame action history；本 run median loop rate 為
  {feature['median_control_loop_hz']:.3f} Hz，約覆蓋
  {feature['observation_action_history_seconds']:.3f} 秒，不足以代表 2–4 秒的長期控制狀態；
- `time_since_landing` 沒有直接欄位，目前只有 lagged support/aligned dwell proxy。

## Gate checks

{checks}

## Evidence boundary

這是 10 回合、單一 Teacher/controller 版本的描述性 audit。Simulator teacher dataset
沒有相同的逐步 controller-memory timeline，因此不能拿它替代本次 causal-memory 主分析。
本結果不等於 Student 成功率，也不允許直接進行長 BC/DAgger 或 RL。
"""
    path.write_text(report, encoding="utf-8")


def main() -> int:
    args = parse_args()
    gate_artifact = args.gate_artifact.resolve()
    outputs = [args.output_json, args.summary_csv, args.conflicts_csv, args.report]
    _prepare_outputs(outputs, overwrite=args.overwrite)

    rows, source = load_real_gate_rows(gate_artifact)
    result = audit_state_aliasing(rows)
    result["generated_at"] = datetime.now().astimezone().isoformat()
    result["source"] = source
    result["provenance"] = {
        "gate_sha256": _sha256(gate_artifact),
        "game_input_sent": False,
        "student_training_started": False,
        "simulator_dataset_used_as_primary": False,
    }

    conflicts = result.pop("conflicts")
    _write_summary(args.summary_csv, result)
    _write_conflicts(args.conflicts_csv, conflicts)
    result["conflict_rows_written"] = len(conflicts)
    args.output_json.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_report(args.report, result)

    print(f"P4.0 Gate: {result['gate']['status']}")
    print(f"Rows: {result['dataset']['rows']}")
    print(
        "Relative disagreement reduction: "
        f"{result['causal_memory_effect']['relative_disagreement_reduction']:.6f}"
    )
    print(f"Audit JSON: {args.output_json.resolve()}")
    print(f"Report: {args.report.resolve()}")
    return 0 if result["gate"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
