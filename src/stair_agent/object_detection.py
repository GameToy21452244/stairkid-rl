from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from .config import VisionConfig
from .diagnostics import load_image


@dataclass(frozen=True)
class BoundingBox:
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> tuple[float, float]:
        return self.left + self.width / 2, self.top + self.height / 2


@dataclass(frozen=True)
class PlayerDetection:
    box: BoundingBox
    confidence: float


def _scaled_playfield(frame: np.ndarray, cfg: VisionConfig) -> BoundingBox:
    values = (
        cfg.playfield_left,
        cfg.playfield_top,
        cfg.playfield_width,
        cfg.playfield_height,
        cfg.reference_width,
        cfg.reference_height,
    )
    if any(value is None for value in values):
        raise RuntimeError("vision playfield ROI 尚未校正。")
    assert cfg.reference_width and cfg.reference_height
    scale_x = frame.shape[1] / cfg.reference_width
    scale_y = frame.shape[0] / cfg.reference_height
    left = round(int(cfg.playfield_left) * scale_x)
    top = round(int(cfg.playfield_top) * scale_y)
    width = round(int(cfg.playfield_width) * scale_x)
    height = round(int(cfg.playfield_height) * scale_y)
    if left < 0 or top < 0 or left + width > frame.shape[1] or top + height > frame.shape[0]:
        raise RuntimeError("vision playfield ROI 超出目前畫面範圍。")
    if width <= 0 or height <= 0:
        raise RuntimeError("vision playfield ROI 尺寸無效。")
    return BoundingBox(left, top, width, height)


def _player_color_masks(
    roi: np.ndarray,
    cfg: VisionConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    raw_mask = cv2.inRange(
        hsv,
        np.array([0, cfg.player_saturation_min, cfg.player_value_min]),
        np.array([cfg.player_hue_max, 255, 255]),
    )
    close_size = int(cfg.player_close_kernel_size)
    if close_size > 1:
        raw_mask = cv2.morphologyEx(
            raw_mask,
            cv2.MORPH_CLOSE,
            np.ones((close_size, close_size), dtype=np.uint8),
        )
    # The real game's normal-platform texture can share the player's warm HSV
    # range.  When the sprite touches that texture, connected components merge
    # the player with an approximately 95 px horizontal strip and the otherwise
    # valid player is rejected for being too wide.  Anything wider than the
    # configured maximum player width cannot belong to a valid player candidate,
    # so remove only those long horizontal runs before component dilation.
    horizontal_platform_mask = cv2.morphologyEx(
        raw_mask,
        cv2.MORPH_OPEN,
        np.ones((1, int(cfg.player_max_width) + 1), dtype=np.uint8),
    )
    candidate_mask = cv2.subtract(raw_mask, horizontal_platform_mask)
    kernel = np.ones(
        (cfg.player_dilate_height, cfg.player_dilate_width),
        dtype=np.uint8,
    )
    return raw_mask, candidate_mask, cv2.dilate(candidate_mask, kernel)


def player_color_diagnostics(
    frame: np.ndarray,
    cfg: VisionConfig,
) -> tuple[dict[str, object], np.ndarray]:
    """Return lossless player-mask evidence using the live detector rules."""

    playfield = _scaled_playfield(frame, cfg)
    roi = frame[
        playfield.top : playfield.top + playfield.height,
        playfield.left : playfield.left + playfield.width,
    ]
    raw_mask, candidate_mask, merged = _player_color_masks(roi, cfg)
    _count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(merged)
    shrink_x = cfg.player_dilate_width // 2
    shrink_y = cfg.player_dilate_height // 2
    components: list[dict[str, object]] = []
    for raw_stat in stats[1:]:
        left, top, width, height, area = (int(value) for value in raw_stat)
        size_ok = (
            cfg.player_min_width <= width <= cfg.player_max_width
            and cfg.player_min_height <= height <= cfg.player_max_height
        )
        actual_left = left + shrink_x
        actual_top = top + shrink_y
        actual_width = max(1, width - 2 * shrink_x)
        actual_height = max(1, height - 2 * shrink_y)
        mask_crop = candidate_mask[
            actual_top : actual_top + actual_height,
            actual_left : actual_left + actual_width,
        ]
        colored_pixels = int(np.count_nonzero(mask_crop))
        eligible = size_ok and colored_pixels >= cfg.player_min_colored_pixels
        components.append(
            {
                "merged_box": [left, top, width, height],
                "actual_box": [
                    playfield.left + actual_left,
                    playfield.top + actual_top,
                    actual_width,
                    actual_height,
                ],
                "merged_area": area,
                "colored_pixels": colored_pixels,
                "size_ok": size_ok,
                "eligible": eligible,
            }
        )
    components.sort(
        key=lambda item: int(item["colored_pixels"]),
        reverse=True,
    )
    eligible_components = [item for item in components if bool(item["eligible"])]
    return (
        {
            "playfield": [
                playfield.left,
                playfield.top,
                playfield.width,
                playfield.height,
            ],
            "thresholds": {
                "hue_max": cfg.player_hue_max,
                "saturation_min": cfg.player_saturation_min,
                "value_min": cfg.player_value_min,
                "min_width": cfg.player_min_width,
                "max_width": cfg.player_max_width,
                "min_height": cfg.player_min_height,
                "max_height": cfg.player_max_height,
                "min_colored_pixels": cfg.player_min_colored_pixels,
            },
            "raw_colored_pixels": int(np.count_nonzero(raw_mask)),
            "candidate_colored_pixels": int(
                np.count_nonzero(candidate_mask)
            ),
            "horizontal_colored_pixels_removed": int(
                np.count_nonzero(raw_mask) - np.count_nonzero(candidate_mask)
            ),
            "component_count": len(components),
            "eligible_component_count": len(eligible_components),
            "best_eligible_component": (
                None if not eligible_components else eligible_components[0]
            ),
            "largest_components": components[:10],
        },
        candidate_mask,
    )


class PlatformKind(Enum):
    NORMAL = "normal"
    UNKNOWN = "unknown"
    HAZARD = "hazard"
    SPIKES = "spikes"
    SPRING = "spring"
    GREEN_SPECIAL = "spring"
    CONVEYOR = "conveyor"
    FLIPPING = "flipping"
    METAL_SPECIAL = "conveyor"


@dataclass(frozen=True)
class PlatformDetection:
    box: BoundingBox
    kind: PlatformKind
    confidence: float
    track_id: int | None = None


@dataclass(frozen=True)
class GameObjects:
    player: PlayerDetection | None
    platforms: list[PlatformDetection]
    playfield: BoundingBox


class ObjectDetector:
    """以校正 ROI、角色色彩與普通平台模板偵測畫面物件。"""

    def __init__(
        self,
        config: VisionConfig,
        normal_platform_template: np.ndarray | None,
        *,
        spikes_platform_template: np.ndarray | None = None,
        green_platform_template: np.ndarray | None = None,
        green_platform_templates: list[np.ndarray] | None = None,
        metal_platform_template: np.ndarray | None = None,
        metal_platform_templates: list[np.ndarray] | None = None,
        flipping_platform_templates: list[np.ndarray] | None = None,
    ) -> None:
        self.config = config
        self.normal_platform_template = normal_platform_template
        self.spikes_platform_template = spikes_platform_template
        self.green_platform_templates = [
            template
            for template in [green_platform_template, *(green_platform_templates or [])]
            if template is not None
        ]
        self.metal_platform_templates = [
            template
            for template in [metal_platform_template, *(metal_platform_templates or [])]
            if template is not None
        ]
        self.flipping_platform_templates = flipping_platform_templates or []

    @classmethod
    def from_config(
        cls,
        config: VisionConfig,
        project_root: str | Path,
    ) -> "ObjectDetector":
        template_path = Path(config.normal_platform_template_path)
        if not template_path.is_absolute():
            template_path = Path(project_root) / template_path
        if not template_path.is_file():
            raise RuntimeError(
                f"找不到普通平台範本：{template_path}。"
                "請先建立／校正 platform_normal.png。"
            )
        def optional_template(value: str) -> np.ndarray | None:
            path = Path(value)
            if not path.is_absolute():
                path = Path(project_root) / path
            return load_image(path) if path.is_file() else None

        def optional_templates(values: list[str]) -> list[np.ndarray]:
            templates: list[np.ndarray] = []
            for value in values:
                template = optional_template(value)
                if template is not None:
                    templates.append(template)
            return templates

        return cls(
            config,
            load_image(template_path),
            spikes_platform_template=optional_template(
                config.spikes_platform_template_path
            ),
            green_platform_template=optional_template(
                config.green_platform_template_path
            ),
            green_platform_templates=optional_templates(
                config.green_platform_template_paths
            ),
            metal_platform_template=optional_template(
                config.metal_platform_template_path
            ),
            metal_platform_templates=optional_templates(
                config.metal_platform_template_paths
            ),
            flipping_platform_templates=optional_templates(
                config.flipping_platform_template_paths
            ),
        )

    def _playfield(self, frame: np.ndarray) -> BoundingBox:
        return _scaled_playfield(frame, self.config)

    def _detect_player(
        self,
        roi: np.ndarray,
        playfield: BoundingBox,
    ) -> PlayerDetection | None:
        cfg = self.config
        _raw_mask, candidate_mask, merged = _player_color_masks(roi, cfg)
        _count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(merged)
        shrink_x = cfg.player_dilate_width // 2
        shrink_y = cfg.player_dilate_height // 2
        candidates: list[tuple[int, BoundingBox]] = []
        for raw_stat in stats[1:]:
            left, top, width, height, _area = (int(value) for value in raw_stat)
            if not (
                cfg.player_min_width <= width <= cfg.player_max_width
                and cfg.player_min_height <= height <= cfg.player_max_height
            ):
                continue
            actual_left = left + shrink_x
            actual_top = top + shrink_y
            actual_width = max(1, width - 2 * shrink_x)
            actual_height = max(1, height - 2 * shrink_y)
            mask_crop = candidate_mask[
                actual_top : actual_top + actual_height,
                actual_left : actual_left + actual_width,
            ]
            colored_pixels = int(np.count_nonzero(mask_crop))
            if colored_pixels < cfg.player_min_colored_pixels:
                continue
            box = BoundingBox(
                playfield.left + actual_left,
                playfield.top + actual_top,
                actual_width,
                actual_height,
            )
            candidates.append((colored_pixels, box))
        if not candidates:
            return None
        colored_pixels, best_box = max(candidates, key=lambda item: item[0])
        confidence = min(1.0, colored_pixels / 134.0)
        return PlayerDetection(best_box, confidence)

    def _match_platform_template(
        self,
        roi: np.ndarray,
        playfield: BoundingBox,
        frame: np.ndarray,
        template_source: np.ndarray | None,
        threshold: float,
        kind: PlatformKind,
    ) -> list[PlatformDetection]:
        if template_source is None:
            return []
        cfg = self.config
        assert cfg.reference_width and cfg.reference_height
        scale_x = frame.shape[1] / cfg.reference_width
        scale_y = frame.shape[0] / cfg.reference_height
        template_width = max(
            1, round(template_source.shape[1] * scale_x)
        )
        template_height = max(
            1, round(template_source.shape[0] * scale_y)
        )
        template = cv2.resize(
            template_source,
            (template_width, template_height),
            interpolation=cv2.INTER_AREA,
        )
        if template_height > roi.shape[0] or template_width > roi.shape[1]:
            return []
        search_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        scores = cv2.matchTemplate(
            search_gray,
            template_gray,
            cv2.TM_CCOEFF_NORMED,
        )
        work = scores.copy()
        detections: list[PlatformDetection] = []
        while True:
            _minimum, maximum, _min_location, location = cv2.minMaxLoc(work)
            if maximum < threshold:
                break
            left, top = location
            detections.append(
                PlatformDetection(
                    BoundingBox(
                        playfield.left + left,
                        playfield.top + top,
                        template_width,
                        template_height,
                    ),
                    kind,
                    float(maximum),
                )
            )
            suppress_left = max(0, left - template_width // 2)
            suppress_top = max(0, top - template_height // 2)
            suppress_right = min(work.shape[1], left + template_width // 2 + 1)
            suppress_bottom = min(work.shape[0], top + template_height // 2 + 1)
            work[
                suppress_top:suppress_bottom,
                suppress_left:suppress_right,
            ] = -1
        return sorted(detections, key=lambda item: (item.box.top, item.box.left))

    @staticmethod
    def _intersection_over_union(first: BoundingBox, second: BoundingBox) -> float:
        left = max(first.left, second.left)
        top = max(first.top, second.top)
        right = min(first.left + first.width, second.left + second.width)
        bottom = min(first.top + first.height, second.top + second.height)
        intersection = max(0, right - left) * max(0, bottom - top)
        if intersection == 0:
            return 0.0
        union = first.width * first.height + second.width * second.height - intersection
        return intersection / union

    def _detect_platforms(
        self,
        roi: np.ndarray,
        playfield: BoundingBox,
        frame: np.ndarray,
    ) -> list[PlatformDetection]:
        cfg = self.config
        candidates: list[PlatformDetection] = []
        templates: list[
            tuple[np.ndarray | None, float, PlatformKind]
        ] = [
            (
                self.normal_platform_template,
                cfg.normal_platform_threshold,
                PlatformKind.NORMAL,
            ),
            (
                self.spikes_platform_template,
                cfg.spikes_platform_threshold,
                PlatformKind.SPIKES,
            ),
        ]
        templates.extend(
            (
                template,
                cfg.green_platform_threshold,
                PlatformKind.SPRING,
            )
            for template in self.green_platform_templates
        )
        templates.extend(
            (
                template,
                cfg.metal_platform_threshold,
                PlatformKind.CONVEYOR,
            )
            for template in self.metal_platform_templates
        )
        templates.extend(
            (
                template,
                cfg.flipping_platform_threshold,
                PlatformKind.FLIPPING,
            )
            for template in self.flipping_platform_templates
        )
        for template, threshold, kind in templates:
            candidates.extend(
                self._match_platform_template(
                    roi,
                    playfield,
                    frame,
                    template,
                    threshold,
                    kind,
                )
            )
        selected: list[PlatformDetection] = []
        for candidate in sorted(
            candidates,
            key=lambda item: item.confidence,
            reverse=True,
        ):
            if any(
                self._intersection_over_union(candidate.box, item.box) > 0.5
                for item in selected
            ):
                continue
            selected.append(candidate)
        return sorted(selected, key=lambda item: (item.box.top, item.box.left))

    def detect(self, frame: np.ndarray) -> GameObjects:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3:
            raise TypeError("frame 必須是 BGR NumPy ndarray。")
        playfield = self._playfield(frame)
        roi = frame[
            playfield.top : playfield.top + playfield.height,
            playfield.left : playfield.left + playfield.width,
        ]
        return GameObjects(
            player=self._detect_player(roi, playfield),
            platforms=self._detect_platforms(roi, playfield, frame),
            playfield=playfield,
        )

    def annotate(self, frame: np.ndarray, objects: GameObjects) -> np.ndarray:
        output = frame.copy()
        pf = objects.playfield
        cv2.rectangle(
            output,
            (pf.left, pf.top),
            (pf.left + pf.width, pf.top + pf.height),
            (160, 160, 160),
            1,
        )
        for platform in objects.platforms:
            box = platform.box
            colors = {
                PlatformKind.NORMAL: (255, 255, 0),
                PlatformKind.SPIKES: (0, 0, 255),
                PlatformKind.SPRING: (0, 255, 255),
                PlatformKind.CONVEYOR: (255, 0, 255),
                PlatformKind.FLIPPING: (0, 165, 255),
            }
            cv2.rectangle(
                output,
                (box.left, box.top),
                (box.left + box.width, box.top + box.height),
                colors.get(platform.kind, (200, 200, 200)),
                2,
            )
            cv2.putText(
                output,
                (
                    f"#{platform.track_id} {platform.kind.value}"
                    if platform.track_id is not None
                    else platform.kind.value
                ),
                (box.left, max(12, box.top - 3)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                colors.get(platform.kind, (200, 200, 200)),
                1,
                cv2.LINE_AA,
            )
        if objects.player:
            box = objects.player.box
            cv2.rectangle(
                output,
                (box.left, box.top),
                (box.left + box.width, box.top + box.height),
                (0, 255, 0),
                2,
            )
            cv2.putText(
                output,
                f"player {objects.player.confidence:.2f}",
                (box.left, max(12, box.top - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
        return output
