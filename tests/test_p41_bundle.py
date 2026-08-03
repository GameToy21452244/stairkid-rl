from __future__ import annotations

from hashlib import sha256
import json
from zipfile import ZipFile

import pytest

from stair_agent.p41_bundle import create_p41_bundle


def test_p41_bundle_includes_exact_frozen_dataset_and_excludes_local_config(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "artifacts").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "notebooks").mkdir()
    dataset = root / "artifacts" / "spike_teacher_dataset_v1.jsonl"
    dataset.write_text('{"row":1}\n', encoding="utf-8")
    digest = sha256(dataset.read_bytes()).hexdigest()
    manifest = root / "artifacts" / "p41_experiment_manifest.json"
    manifest.write_text(
        json.dumps({"dataset": {"sha256": digest}}), encoding="utf-8"
    )
    source = root / "scripts" / "run_p41_ablation.py"
    source.write_text("print('ok')\n", encoding="utf-8")
    notebook = root / "notebooks" / "ns_shaft_colab.ipynb"
    notebook.write_text("{}\n", encoding="utf-8")
    pyproject = root / "pyproject.toml"
    pyproject.write_text("[project]\nname='test'\n", encoding="utf-8")
    config = root / "config.yaml"
    config.write_text("secret: local\n", encoding="utf-8")
    target = tmp_path / "bundle.zip"

    summary = create_p41_bundle(
        repo_root=root,
        target=target,
        source_files=(manifest, source, notebook, pyproject, config),
        dataset_path=dataset,
        git_commit="abc123",
        dirty=True,
    )

    with ZipFile(target) as archive:
        names = set(archive.namelist())
        assert "ai-stair-agent/artifacts/spike_teacher_dataset_v1.jsonl" in names
        assert "ai-stair-agent/artifacts/p41_experiment_manifest.json" in names
        assert "ai-stair-agent/scripts/run_p41_ablation.py" in names
        assert "ai-stair-agent/config.yaml" not in names
        bundled_manifest = json.loads(
            archive.read("ai-stair-agent/p41_bundle_manifest.json")
        )
    assert summary["dataset_sha256"] == digest
    assert bundled_manifest["git_commit"] == "abc123"
    assert bundled_manifest["dirty"] is True


def test_p41_bundle_rejects_dataset_hash_mismatch(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "artifacts").mkdir(parents=True)
    dataset = root / "artifacts" / "spike_teacher_dataset_v1.jsonl"
    dataset.write_text("different", encoding="utf-8")
    manifest = root / "artifacts" / "p41_experiment_manifest.json"
    manifest.write_text(
        json.dumps({"dataset": {"sha256": "0" * 64}}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="SHA-256"):
        create_p41_bundle(
            repo_root=root,
            target=tmp_path / "bundle.zip",
            source_files=(manifest,),
            dataset_path=dataset,
            git_commit="abc123",
            dirty=False,
        )
