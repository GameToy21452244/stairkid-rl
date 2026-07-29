import cv2
import numpy as np

from stair_agent.diagnostics import load_image, save_image


def test_save_image_supports_unicode_path(tmp_path) -> None:
    directory = tmp_path / "小朋友下樓梯│畫面"
    directory.mkdir()
    path = directory / "對話框.png"
    frame = np.zeros((12, 20, 3), dtype=np.uint8)

    save_image(path, frame)

    restored = load_image(path)
    assert path.is_file()
    assert restored.shape == (12, 20, 3)
