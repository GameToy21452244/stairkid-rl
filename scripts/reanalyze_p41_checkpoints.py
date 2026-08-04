from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Mapping
from zipfile import ZipFile

import _common  # noqa: F401,E402
import torch

from stair_agent.learnability import evaluate_candidate, learned_selector
from stair_agent.simulator.gates import evaluation_summary
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.p41_ablation import (
    compare_to_s0_gate,
    load_p41_checkpoint,
    make_policy,
)
from stair_agent.training.p41_reanalysis import (
    P41_REANALYSIS_SCHEMA_VERSION,
    risk_first_selected_updates,
    validate_selection_only_source,
)


REPLAY_VARIANTS = ("S0", "S1")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _simulator_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )


def _rollout(model: torch.nn.Module, *, variant: str, seeds: tuple[int, ...]) -> dict[str, object]:
    policy = make_policy(model, variant)
    return evaluation_summary(
        evaluate_candidate(
            f"p41-reanalysis-{variant}",
            learned_selector(policy),
            seeds=seeds,
            max_episode_steps=600,
            config=_simulator_config(),
        )
    )


def _source_selected_updates(summary: Mapping[str, object], variant: str) -> dict[int, int]:
    return {
        int(record["initialization_seed"]): int(record["selected_update"])
        for record in summary["training"][variant]
    }


def _assert_reproduced(replayed: Mapping[str, object], source: Mapping[str, object]) -> None:
    scalar_fields = (
        "episodes",
        "total_steps",
        "mean_deepest_floor",
        "median_deepest_floor",
        "deepest_floor_quantile_25",
        "deepest_floor_cvar25",
        "reach_rate_floor_10",
        "bottom_death_rate",
        "health_death_rate",
        "direction_switches_per_100_steps",
    )
    for field in scalar_fields:
        if abs(float(replayed[field]) - float(source[field])) > 1e-9:
            raise RuntimeError(
                f"checkpoint replay未重現source metric {field}："
                f"{replayed[field]} != {source[field]}"
            )
    replayed_floors = [int(item["deepest_floor"]) for item in replayed["episode_results"]]
    source_floors = [int(item["deepest_floor"]) for item in source["episode_results"]]
    if replayed_floors != source_floors:
        raise RuntimeError("checkpoint replay的per-episode deepest floors與source不一致。")
    if replayed["terminal_reasons"] != source["terminal_reasons"]:
        raise RuntimeError("checkpoint replay的terminal reasons與source不一致。")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument(
        "--digest",
        type=Path,
        default=Path("artifacts/p41_colab_result_digest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/p41_checkpoint_reanalysis_v1.json"),
    )
    args = parser.parse_args()
    archive_path = args.source_archive.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    if args.output.exists():
        raise FileExistsError(args.output)
    digest = json.loads(args.digest.read_text(encoding="utf-8"))
    archive_sha256 = _sha256(archive_path)
    if archive_path.name != digest["source_archive"]:
        raise ValueError("來源ZIP檔名與已核准digest不一致。")
    if archive_sha256 != digest["source_archive_sha256"]:
        raise ValueError("來源ZIP SHA-256與已核准digest不一致。")

    with ZipFile(archive_path) as archive:
        summary = json.loads(
            archive.read("results/p41_ablation_summary.json").decode("utf-8")
        )
        scope = validate_selection_only_source(summary)
        if scope.dataset_sha256 != digest["dataset"]["sha256"]:
            raise ValueError("來源summary與digest的dataset SHA-256不一致。")
        risk_first_updates = risk_first_selected_updates(summary)
        replayed: dict[str, list[dict[str, object]]] = {variant: [] for variant in REPLAY_VARIANTS}
        checkpoint_audit: list[dict[str, object]] = []
        with TemporaryDirectory(prefix="p41-selection-reanalysis-") as directory:
            temporary_root = Path(directory)
            for variant in REPLAY_VARIANTS:
                source_updates = _source_selected_updates(summary, variant)
                if source_updates != risk_first_updates[variant]:
                    raise RuntimeError(
                        f"{variant} risk-first update與archive checkpoint不一致；拒絕重訓替代。"
                    )
                for initialization_seed in (0, 1, 2):
                    update = source_updates[initialization_seed]
                    entry_name = (
                        f"results/{variant.lower()}_seed_{initialization_seed}_selected.pt"
                    )
                    checkpoint_path = temporary_root / Path(entry_name).name
                    with archive.open(entry_name) as source, checkpoint_path.open("xb") as target:
                        shutil.copyfileobj(source, target)
                    model, metadata = load_p41_checkpoint(
                        checkpoint_path,
                        expected_variant=variant,
                    )
                    if (
                        int(metadata["initialization_seed"]) != initialization_seed
                        or int(metadata["update"]) != update
                        or metadata["dataset_sha256"] != scope.dataset_sha256
                    ):
                        raise ValueError(f"{entry_name} checkpoint provenance不一致。")
                    rollout = _rollout(
                        model,
                        variant=variant,
                        seeds=scope.selection_seeds,
                    )
                    source_rollout = summary["selection_summaries"][variant][
                        initialization_seed
                    ]
                    _assert_reproduced(rollout, source_rollout)
                    replayed[variant].append(rollout)
                    checkpoint_audit.append(
                        {
                            "variant": variant,
                            "initialization_seed": initialization_seed,
                            "update": update,
                            "entry": entry_name,
                            "dataset_sha256": metadata["dataset_sha256"],
                            "source_metrics_reproduced": True,
                        }
                    )

    gate = compare_to_s0_gate(replayed["S1"], replayed["S0"])
    output = {
        "schema_version": P41_REANALYSIS_SCHEMA_VERSION,
        "source_archive": archive_path.name,
        "source_archive_sha256": archive_sha256,
        "source_status": summary["status"],
        "training_started": False,
        "final_seeds_used": False,
        "selection_seeds": list(scope.selection_seeds),
        "final_seeds_reserved": list(scope.final_seeds),
        "risk_first_selected_updates": {
            variant: {str(seed): update for seed, update in updates.items()}
            for variant, updates in risk_first_updates.items()
        },
        "replayed_variants": list(REPLAY_VARIANTS),
        "checkpoint_audit": checkpoint_audit,
        "selection_replay": replayed,
        "corrected_s1_gate_vs_s0": gate,
        "status": (
            "SELECTION_PASS_FINAL_NOT_RUN"
            if gate["passed"]
            else "FAIL_STOP_SELECTION_CONFIRMED"
        ),
        "next_stage": (
            "FREEZE_NEW_FINAL_PROTOCOL_WITHOUT_USING_RESERVED_FINAL_SEEDS"
            if gate["passed"]
            else "P41_DATASET_V2_GAP_AUDIT"
        ),
        "rejected_variants": {
            "S2": "original bottom death 50.0%; risk-first checkpoint not archived for every seed",
            "S3": "original bottom death 98.3%; compact representation rejected",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "gate_passed": gate["passed"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
