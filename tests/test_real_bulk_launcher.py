from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from stair_agent.core.model_registry import MODEL_IDS


ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "START_REAL_MODEL_TEST.cmd"
LAUNCHER = ROOT / "scripts/run_real_model_launcher.py"
BULK_RUNNER = ROOT / "scripts/bulk_real_evaluation.py"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("real_model_launcher", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launcher_files_and_current_models_only() -> None:
    assert CMD.is_file() and LAUNCHER.is_file() and BULK_RUNNER.is_file()
    module = _load_launcher()
    assert module.MODEL_MENU == {"1": "v3", "2": "r4"}
    assert MODEL_IDS == ("v3", "r4")


def test_launcher_plan_supports_real100_and_confirmed_video_modes(tmp_path: Path) -> None:
    module = _load_launcher()
    plan = module.LaunchPlan(
        model_id="r4",
        mode="control",
        episodes=100,
        failure_diagnostics=True,
        video_mode="best",
        output_dir=tmp_path,
    )
    command = module.build_child_command(ROOT, Path(sys.executable), plan)
    assert "--model" in command and "r4" in command
    assert "--episodes" in command and "100" in command
    assert "--failure-diagnostics" in command
    assert command[command.index("--video-mode") + 1] == "best"
    assert not any("AUTHORIZE" in value for value in command)
    assert "--yes" not in command


def test_invalid_launcher_inputs_fail_closed() -> None:
    module = _load_launcher()
    with pytest.raises(ValueError):
        module.parse_episode_count("0")
    with pytest.raises(ValueError):
        module.parse_episode_count("101")
    with pytest.raises(ValueError):
        module.parse_episode_count("twenty")


def test_missing_and_bad_model_archives_fail_closed(tmp_path: Path, monkeypatch) -> None:
    module = _load_launcher()
    missing = SimpleNamespace(asset_path=tmp_path / "missing.zip", sha256="a" * 64)
    monkeypatch.setattr(module, "load_model_registry", lambda _root: {"v3": missing})
    with pytest.raises(RuntimeError, match="CANONICAL_MODEL_FILE_REQUIRED"):
        module.verify_model_archive(tmp_path, "v3")
    bad_path = tmp_path / "model.zip"
    bad_path.write_bytes(b"wrong")
    bad = SimpleNamespace(asset_path=bad_path, sha256="a" * 64)
    monkeypatch.setattr(module, "load_model_registry", lambda _root: {"v3": bad})
    with pytest.raises(RuntimeError, match="MODEL_SHA_MISMATCH"):
        module.verify_model_archive(tmp_path, "v3")


def test_exact_run_gate_does_not_start_child_on_wrong_confirmation(monkeypatch) -> None:
    module = _load_launcher()
    answers = iter(["1", "1", "1", "n", "1", "not-run"])
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "verify_model_archive", lambda *_args: None)
    result = module.interactive_main(
        project_root=ROOT,
        python_executable=Path(sys.executable),
        input_fn=lambda _prompt: next(answers),
        output_fn=lambda _line: None,
        run_fn=lambda command, **_kwargs: calls.append(command),
    )
    assert result == 2
    assert calls == []


def test_cmd_uses_only_repo_local_venv_and_quoted_repo_relative_paths() -> None:
    source = CMD.read_text(encoding="utf-8-sig").casefold()
    assert "%~dp0" in source
    assert '.venv\\scripts\\python.exe' in source
    assert "where python" not in source
    assert "..\\ai-stair-agent" not in source
    assert "powershell" not in source
    assert "run_real_model_launcher.py" in source


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe path parsing is Windows-only")
def test_cmd_path_with_chinese_space_and_box_drawing_pipe_fails_cleanly_without_venv(
    tmp_path: Path,
) -> None:
    target = tmp_path / "NS Shaft│小朋友下樓梯" / "START_REAL_MODEL_TEST.cmd"
    target.parent.mkdir(parents=True)
    target.write_bytes(CMD.read_bytes())
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", str(target)],
        cwd=target.parent,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env={**os.environ, "STAIRKID_NO_PAUSE": "1"},
        timeout=10,
        check=False,
    )
    assert completed.returncode != 0
    assert ".venv" in (completed.stdout + completed.stderr)


def test_real_stack_has_no_training_or_retired_router() -> None:
    paths = [
        ROOT / "src/stair_agent/real/bulk.py",
        LAUNCHER,
        BULK_RUNNER,
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths).casefold()
    assert ".learn(" not in text
    assert "model.learn" not in text
    assert "hybridlandingrouter" not in text
    assert "expected_v2_sha256" not in text
    assert "frozen_v2" not in text


def test_simulator_evaluator_remains_simulator_only() -> None:
    source = (ROOT / "scripts/evaluate.py").read_text(encoding="utf-8").casefold()
    assert "run_simulator_policy" in source
    assert "create_live_environment" not in source
    assert "inputcontroller" not in source
