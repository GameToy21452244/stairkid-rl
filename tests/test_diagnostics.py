import cv2
import numpy as np

from stair_agent.diagnostics import annotate_frame, load_image, save_image


def test_save_image_supports_unicode_path(tmp_path) -> None:
    directory = tmp_path / "小朋友下樓梯│畫面"
    directory.mkdir()
    path = directory / "對話框.png"
    frame = np.zeros((12, 20, 3), dtype=np.uint8)

    save_image(path, frame)

    restored = load_image(path)
    assert path.is_file()
    assert restored.shape == (12, 20, 3)


def test_annotate_frame_accepts_multiple_panel_lines() -> None:
    frame = np.zeros((120, 240, 3), dtype=np.uint8)

    annotated = annotate_frame(
        frame,
        fps=15.0,
        message=["event=spring_bounce", "life=8 delta=-4", "near=spring"],
    )

    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)
