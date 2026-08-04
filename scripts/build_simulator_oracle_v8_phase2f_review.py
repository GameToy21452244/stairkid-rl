"""Build the bounded, offline-only Oracle v8 Phase 2F review artifact."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


FORMAL = Path("artifacts/simulator_oracle_v8_terminal_guard_development_v1.json")
TRIGGERS = Path("artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.json")
COUNTERFACTUALS = Path("artifacts/simulator_oracle_v8_phase2f_counterfactuals_v1.json")
PRUNING = Path("artifacts/simulator_oracle_v8_phase2f_branch_pruning_v1.json")
ALIGNMENT = Path("artifacts/simulator_real_alignment_audit_v3.json")
PROTOCOL = Path("reports/SIMULATOR_ORACLE_V8_TERMINAL_GUARD_PROTOCOL.md")
ORACLE_SOURCE = Path("src/stair_agent/policies/simulator_teachers.py")
PLANNER_SOURCE = Path("src/stair_agent/policies/simulator_route_planner.py")
OUTPUT = Path("artifacts/simulator_oracle_v8_phase2f_review_v1.json")

EXPECTED_FROZEN_HASHES = {
    FORMAL: "b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166",
    PROTOCOL: "78df06c393ff8123d559a98657fadbd791eee3ce3f532aa6a3fabe2cc3f5289e",
    ORACLE_SOURCE: "18018669ed6e97056be20bf07642afd766dfa0b3c0bf4e232e476c26c295cbbb",
    PLANNER_SOURCE: "c52671e08c607d919e8c83b5f63b5c0faaf8b92541322996bdc736b66444a394",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate(
    rating: str,
    supporting: list[str],
    opposing: list[str],
    switch_risk: str,
    magic_threshold: str,
    real_alignment: str,
    minimum_validation: str,
    partitions: str,
) -> dict[str, object]:
    return {
        "rating": rating,
        "supporting_evidence": supporting,
        "opposing_evidence": opposing,
        "v7_switch_inflation_risk": switch_risk,
        "depends_on_magic_threshold": magic_threshold,
        "real_alignment_packet_calibration": real_alignment,
        "minimum_verifiable_implementation": minimum_validation,
        "required_new_partitions": partitions,
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫Phase 2F artifact：{OUTPUT}")
    frozen_hashes = {str(path): _sha256(path) for path in EXPECTED_FROZEN_HASHES}
    mismatches = {
        str(path): {"expected": expected, "actual": frozen_hashes[str(path)]}
        for path, expected in EXPECTED_FROZEN_HASHES.items()
        if frozen_hashes[str(path)] != expected
    }
    if mismatches:
        raise RuntimeError(f"凍結證據hash不一致：{mismatches}")

    formal = _load(FORMAL)
    triggers = _load(TRIGGERS)
    counterfactuals = _load(COUNTERFACTUALS)
    pruning = _load(PRUNING)
    alignment = _load(ALIGNMENT)
    if formal["status"] != "FAIL_STOP_V8_DEVELOPMENT":
        raise RuntimeError("formal v8 status不是FAIL_STOP_V8_DEVELOPMENT。")
    if formal["holdout"]["used"] is not False:
        raise RuntimeError("17000-17099 holdout已被使用，停止建立review。")
    if not all(
        item.get("holdout", {}).get("used") is False
        for item in (triggers, counterfactuals, pruning)
    ):
        raise RuntimeError("Phase 2F子artifact的holdout ledger不一致。")

    dev = formal["development"]
    trigger_summary = triggers["summary"]
    counterfactual_summary = counterfactuals["summary"]
    pruning_summary = pruning["summary"]
    evidence_paths = [FORMAL, TRIGGERS, COUNTERFACTUALS, PRUNING, ALIGNMENT]
    evidence_hashes = {str(path): _sha256(path) for path in evidence_paths}

    new_partitions = (
        "任何獲准的新production候選都需先另凍結全新development與one-time holdout；"
        "建議預留18000-18099／19000-19099，須先完成seed ledger查核。"
        "本review不批准或消耗任何partition。"
    )
    payload = {
        "schema_version": "simulator-oracle-v8-phase2f-review-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_completed": True,
        "review_scope": "offline_oracle_failure_design_review",
        "formal_gate": False,
        "formal_v8_status_unchanged": "FAIL_STOP_V8_DEVELOPMENT",
        "project_status": "BLOCKED_WITH_EVIDENCE",
        "production_modified": False,
        "protocol_modified": False,
        "source_hashes": frozen_hashes,
        "evidence_hashes": evidence_hashes,
        "formal_result": {
            "v6": dev["v6"],
            "v8": dev["v8"],
            "paired_outcomes": dev["paired_outcomes"],
            "first_divergence_taxonomy": dev["first_divergence_taxonomy"],
            "failed_frozen_check": "v6_top_failures_repaired_at_least_one",
            "both_failure_seeds": {
                "top": [16002, 16030],
                "bottom": [16009, 16086],
            },
        },
        "core_diagnosis": {
            "terminal_plan_calls": trigger_summary["terminal_plan_calls"],
            "terminal_risk_replans": trigger_summary["terminal_risk_replans"],
            "why_actions_remained_identical": (
                "每次v8 replan的共享24-beam搜尋都重新得到與v6 cached suffix完全相同的"
                "RELEASE_ALL terminal plan。離線按first-action隔離的同界限12/24搜尋可找到"
                "RIGHT存活／進樓分支，但14條可完整救回reach10的RIGHT路徑全在共享beam"
                "depth 4因中間score排名35-39、低於24名cutoff而被剪除；故final selector"
                "從未看到它們。選出的RELEASE確實寫入且執行。"
            ),
            "primary_classifications": [
                "BEAM_PRUNING_LIMITATION",
                "SURVIVING_CANDIDATE_EXISTS_BUT_SCORE_REJECTS_IT_AT_INTERMEDIATE_PRUNING",
            ],
            "qualified_classifications": {
                "NO_SURVIVING_CANDIDATE_WITHIN_CURRENT_SEARCH": (
                    "對production共享beam輸出為真，但原因是成功分支已在depth 4被剪除；"
                    "不是同一12/24 bounds下物理無解。"
                ),
                "SURVIVING_CANDIDATE_EXISTS_BUT_SCORE_REJECTS_IT": (
                    "只在中間beam ranking層成立；不是final completed-candidate比較選錯。"
                ),
            },
            "rejected_classifications": {
                "TRIGGER_TOO_LATE": "兩seed均在不可避免點前6-8 decisions觸發。",
                "SAME_FIRST_ACTION_DIFFERENT_SUFFIX": "0/22；重算suffix與v6 cached suffix完全相同。",
                "REPLAN_RESULT_OVERWRITTEN_OR_NOT_COMMITTED": "22/22 selected first actions確實執行。",
                "SNAPSHOT_OR_RESTORE_SEMANTIC_ISSUE": "state、RNG與platform identity restore checks全PASS。",
                "HORIZON_LIMITATION": "完整救回路徑已存在於12-step界限。",
                "FAILURE_NOT_REPAIRABLE_BY_ACTION_PLANNING": "14個不同首動作counterfactual完整reach10。",
            },
        },
        "top_failure_diagnoses": {
            "16002": {
                "formal_outcome": "top at floor 5",
                "terminal_risk_entry_step": 39,
                "last_rescuable_step": 46,
                "first_persistently_unavoidable_step": 47,
                "lead_before_unavoidable_decisions": 8,
                "rescuing_forced_first_action": "RIGHT",
                "full_reach10_counterfactual_trigger_steps": list(range(39, 47)),
                "root_cause": [
                    "BEAM_PRUNING_LIMITATION",
                    "INTERMEDIATE_SCORE_RANKING_BRANCH_EXTINCTION",
                ],
                "trigger_too_late": False,
                "score_selected_wrong_final_candidate": False,
            },
            "16030": {
                "formal_outcome": "top at floor 7",
                "terminal_risk_entry_step": 51,
                "last_rescuable_step": 56,
                "first_persistently_unavoidable_step": 57,
                "lead_before_unavoidable_decisions": 6,
                "rescuing_forced_first_action": "RIGHT",
                "full_reach10_counterfactual_trigger_steps": list(range(51, 57)),
                "root_cause": [
                    "BEAM_PRUNING_LIMITATION",
                    "INTERMEDIATE_SCORE_RANKING_BRANCH_EXTINCTION",
                ],
                "trigger_too_late": False,
                "score_selected_wrong_final_candidate": False,
            },
        },
        "forced_first_action_counterfactual": {
            "trigger_count": counterfactual_summary["trigger_count"],
            "forced_action_count": counterfactual_summary["counterfactual_count"],
            "local_nonterminal_or_floor_progress_count": counterfactual_summary[
                "local_nonterminal_or_floor_progress_count"
            ],
            "different_first_action_full_reach10_count": counterfactual_summary[
                "different_first_action_full_reach_floor_10_count"
            ],
            "full_rescues_by_seed": counterfactual_summary["full_rescues_by_seed"],
            "rescue_action": "RIGHT",
            "not_merely_delayed_death": True,
        },
        "branch_pruning": {
            "full_rescue_path_count": pruning_summary["full_rescue_path_count"],
            "first_prune_depth_counts": pruning_summary["first_prune_depth_counts"],
            "all_pruned_scores_below_beam_cutoff": pruning_summary[
                "all_pruned_scores_below_beam_cutoff"
            ],
            "forced_unique_rank_range": [35, 39],
            "production_beam_width": 24,
            "interpretation": (
                "共享beam的intermediate score偏好大量RELEASE prefixes；成功RIGHT lane在"
                "floor progress bonus實現前消失。"
            ),
        },
        "horizon_beam_diagnostic": {
            "formal_baseline": "12-step/24-beam",
            "horizon_primary_cause": False,
            "beam_pruning_primary_cause": True,
            "late_all_terminal_state_results": {
                "24-step/24-beam_survivors": trigger_summary[
                    "h24_b24_surviving_trigger_count"
                ],
                "12-step/96-beam_survivors": trigger_summary[
                    "h12_b96_surviving_trigger_count"
                ],
                "24-step/96-beam_representative_survivors": trigger_summary[
                    "h24_b96_surviving_representative_count"
                ],
                "24-step/96-beam_representative_triggers": trigger_summary[
                    "h24_b96_representative_trigger_count"
                ],
            },
            "repairable_state_wide_beam_not_run": (
                "依Phase 2F限制，forced-first於正式bounds已有survivor時不執行extended組合。"
            ),
            "observed_compute": trigger_summary["compute_cost"],
            "compute_interpretation": (
                "extended只跑已接近terminal的states並提早結束，observed runtime不可用來"
                "估計一般成本；理論search caps相對12/24為h24/b24約2x、h12/b96約4x、"
                "h24/b96約8x。"
            ),
        },
        "trigger_timing": trigger_summary["trigger_timing"],
        "candidate_directions": {
            "A_uncertainty_aware_event_triggered_cached_planner": _candidate(
                "REJECT",
                ["真機alignment確有cadence與phase mismatch，理論上需要處理不確定性。"],
                [
                    "本次失敗在完全可重現Simulator內發生，無觀測不確定性。",
                    "現有trigger已提早6-8 decisions，改trigger不會保留被剪掉的RIGHT branch。",
                ],
                "高；uncertainty crossing可反覆觸發replan，可能重現v7逐步改動。",
                "是；uncertainty band與觸發門檻尚無凍結依據。",
                "只能部分校正pose/cadence；alignment audit目前FAIL且缺special-platform coverage。",
                "不實作；若未來另有real uncertainty failure evidence，先做離線shadow replay。",
                new_partitions,
            ),
            "B_survival_margin_trigger": _candidate(
                "REJECT",
                ["binary terminal與survival margin可作更連續的風險telemetry。"],
                [
                    "v8 entry並不晚；兩seed在不可避免前6-8 decisions已觸發。",
                    "同一shared beam已錯誤剪除可救branch，margin會繼承同一錯誤。",
                ],
                "高；更早且更多replan會增加v7式switch風險。",
                "是；margin threshold未由本證據辨識。",
                "可部分校正時間尺度，但無法校正privileged search margin正確性。",
                "不實作；先修search branch visibility後才可能重評。",
                new_partitions,
            ),
            "C_score_function_correction": _candidate(
                "INSUFFICIENT_EVIDENCE",
                ["14條成功RIGHT prefix在depth 4的score rank為35-39，均低於beam cutoff。"],
                [
                    "尚未識別非magic的新feature或weight。",
                    "全域score變更可能改動96個既有成功episode，且final score本身沒有選錯。",
                ],
                "中高；全域plan重排可能增加方向切換與成功軌跡回歸。",
                "目前是；任何bonus/penalty數值都缺獨立證據。",
                "real packet可限制物理量scale，不能提供privileged oracle ranking label。",
                "先在獨立offline corpus比較prefix ranking且要求v6成功path identity；未批准production。",
                new_partitions,
            ),
            "D_forced_first_action_diversity_branch_preservation": _candidate(
                "SUPPORTED_FOR_NEW_PROTOCOL",
                [
                    "同一12/24 bounds按first action保留lane，找到18個local survivor/progress branches。",
                    "其中14個不同首動作RIGHT counterfactual完整reach10，涵蓋兩個top failures。",
                    "14/14成功路徑只因shared beam depth 4 rank 35-39而消失。",
                ],
                [
                    "證據只涵蓋兩個development top failures。",
                    "尚未在100-seed新partition驗證non-regression與action-switch。",
                ],
                "中；若每decision重新選lane仍可能切換；新protocol須凍結commit語意與switch Gate。",
                "否；每個離散first action保留至少一lane是結構約束，不需連續閾值。",
                "根因不依賴real packet；packet可在後續校正action cadence/dynamics，但不能取代sim Gate。",
                "test-first加入terminal-only、first-action-stratified beam；保留v6非terminal path，"
                "先跑全新development的paired reach/tail/switch/non-regression Gate。",
                new_partitions,
            ),
            "E_increase_horizon": _candidate(
                "REJECT",
                ["較長horizon理論上能觀察較晚terminal。"],
                [
                    "救回方案已在12 steps內完成floor progress並可完整reach10。",
                    "在已全terminal的晚期states，24-step/24-beam沒有產生survivor。",
                ],
                "中；新長suffix可能改變更多action，但沒有本次收益。",
                "否；但horizon 24本身仍是未獨立驗證的設計選擇。",
                "packet可校正秒數對應，不會修復depth-4 branch extinction。",
                "不實作。",
                new_partitions,
            ),
            "F_increase_beam": _candidate(
                "INSUFFICIENT_EVIDENCE",
                ["成功prefix在depth 4 rank 35-39，顯示beam>24可能延後該次剪枝。"],
                [
                    "依限制未在仍可救state執行12/96，故未知成功路徑是否能一路留到完成。",
                    "單純加寬缺乏first-action保障，且理論node cap約4x。",
                ],
                "中；全域plan排序改變可能改變既有成功paths。",
                "否；但beam大小是算力超參數。",
                "real packet不能校正beam width。",
                "若D的新protocol設計審查要求比較，只能在全新development做預先凍結的D-vs-wide-beam ablation。",
                new_partitions,
            ),
            "G_minimum_commitment_cooldown_hysteresis": _candidate(
                "INSUFFICIENT_EVIDENCE",
                ["可限制未來branch-preserved replanning可能造成的action chatter。"],
                [
                    "v8目前action switches與v6完全相同，沒有現存switch inflation。",
                    "commit/cooldown不會讓被剪掉的RIGHT branch重新出現，且可能鎖住錯誤action。",
                ],
                "低至中；目的可抑制switch，但錯誤commit是另一風險。",
                "是；commit長度/cooldown目前沒有證據。",
                "packet cadence可換算時間，但不足以定義安全commit window。",
                "只可作D候選的預先指定companion ablation，不可單獨宣稱修復。",
                new_partitions,
            ),
        },
        "scientific_judgment": {
            "selected": "A_SAFE_BUT_INEFFECTIVE_NO_OP_RETIRE_V8",
            "v8_disposition": "REJECT_AND_RETAIN_FOR_REPRODUCIBILITY_ONLY",
            "repair_gate_overly_strict": False,
            "reason": (
                "frozen repair Gate正確揭露v8雖安全non-regression卻沒有因果效用；同界限"
                "branch-preserved counterfactual已證明兩個top failures可由action planning救回，"
                "因此不能以門檻過嚴解釋，也沒有足夠證據放棄privileged Oracle Gate作為"
                "Student上游阻擋。"
            ),
            "new_protocol_evidence_sufficient": True,
            "new_protocol_scope_supported": (
                "只足夠建立以terminal-only first-action branch preservation為唯一production"
                "變因的新protocol；不代表候選已PASS，也不批准實作或seed消耗。"
            ),
        },
        "artifacts": {
            "per_trigger_json": str(TRIGGERS),
            "per_trigger_csv": "artifacts/simulator_oracle_v8_phase2f_trigger_diagnostics_v1.csv",
            "timeline_visualization": "artifacts/simulator_oracle_v8_phase2f_trigger_timeline.svg",
            "committed_counterfactuals": str(COUNTERFACTUALS),
            "branch_pruning": str(PRUNING),
        },
        "safety_invariants": {
            "no_game_input": True,
            "no_training": True,
            "holdout": {
                "partition": "17000-17099",
                "used": False,
            },
            "dataset_generated": False,
            "student_checkpoint_created": False,
            "colab_bundle_created": False,
            "production_planner_hash_unchanged": True,
            "frozen_v8_artifact_hash_unchanged": True,
            "frozen_protocol_hash_unchanged": True,
        },
        "alignment_context": {
            "artifact": str(ALIGNMENT),
            "status": alignment.get("status"),
            "interpretation": (
                "現有alignment evidence不足以支持uncertainty thresholds，且本次deterministic"
                "beam pruning根因不依賴real alignment。"
            ),
        },
        "next_step": (
            "先撰寫並審核全新的branch-preserving Oracle protocol與seed ledger；"
            "在使用者另行批准前，不實作production候選、不跑development或holdout。"
        ),
        "holdout": formal["holdout"],
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} sha256={_sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
