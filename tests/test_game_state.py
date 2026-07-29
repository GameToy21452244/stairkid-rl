import numpy as np

from stair_agent.config import DetectionConfig
from stair_agent.game_state import GamePhase, GameStateDetector


def test_game_phase_enum() -> None:
    assert GamePhase.MENU.value == "menu"
    assert GamePhase.PLAYING.value == "playing"
    assert GamePhase.GAME_OVER.value == "game_over"
    assert GamePhase.DIALOG.value == "dialog"
    assert GamePhase.NAME_ENTRY.value == "name_entry"


def test_detector_is_conservatively_unknown() -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert GameStateDetector().detect(frame) is GamePhase.UNKNOWN


def test_dialog_template_detection() -> None:
    dialog = np.zeros((12, 20, 3), dtype=np.uint8)
    dialog[:, ::2] = (255, 255, 255)
    config = DetectionConfig(
        dialog_roi_left=10,
        dialog_roi_top=8,
        dialog_roi_width=20,
        dialog_roi_height=12,
        reference_width=50,
        reference_height=40,
        dialog_threshold=0.9,
        search_margin=2,
    )
    detector = GameStateDetector(config, dialog)
    frame = np.full((40, 50, 3), 40, dtype=np.uint8)
    frame[8:20, 10:30] = dialog

    phase, score = detector.detect_with_score(frame)

    assert phase is GamePhase.DIALOG
    assert score > 0.99
