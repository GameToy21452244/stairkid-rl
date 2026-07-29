from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .window_manager import WindowInfo


def save_image(path: str | Path, frame: np.ndarray) -> None:
    """以記憶體編碼避開 Windows OpenCV imwrite 的 Unicode 路徑限制。"""
    output_path = Path(path)
    extension = output_path.suffix.lower() or ".png"
    success, encoded = cv2.imencode(extension, frame)
    if not success:
        raise RuntimeError(f"OpenCV 無法將畫面編碼為 {extension}。")
    try:
        output_path.write_bytes(encoded.tobytes())
    except OSError as exc:
        raise RuntimeError(f"無法寫入畫面：{output_path}（{exc}）") from exc


def load_image(path: str | Path) -> np.ndarray:
    """支援 Windows Unicode 路徑的 OpenCV 讀圖。"""
    input_path = Path(path)
    try:
        data = np.frombuffer(input_path.read_bytes(), dtype=np.uint8)
    except OSError as exc:
        raise RuntimeError(f"無法讀取畫面：{input_path}（{exc}）") from exc
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError(f"OpenCV 無法解碼畫面：{input_path}")
    return frame


def prepare_preview_window(name: str, target: WindowInfo) -> None:
    """先建立預覽並移到遊戲右側，避免遮住 MSS 的螢幕擷取區域。"""
    cv2.namedWindow(name, cv2.WINDOW_AUTOSIZE)
    preview_left = target.rect.left + target.rect.width + 20
    cv2.moveWindow(name, preview_left, target.rect.top)


def annotate_frame(
    frame: np.ndarray,
    fps: float | None = None,
    draw_border: bool = True,
    message: str | None = None,
) -> np.ndarray:
    output = frame.copy()
    if output.ndim == 2:
        output = cv2.cvtColor(output, cv2.COLOR_GRAY2BGR)
    if draw_border:
        height, width = output.shape[:2]
        cv2.rectangle(output, (1, 1), (width - 2, height - 2), (0, 255, 0), 2)
    if fps is not None:
        cv2.putText(
            output,
            f"FPS: {fps:.1f}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    if message:
        cv2.putText(
            output,
            message,
            (10, output.shape[0] - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return output
