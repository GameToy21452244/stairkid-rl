import cv2
import numpy as np

from stair_agent.config import VisionConfig
from stair_agent.object_detection import (
    ObjectDetector,
    PlatformKind,
)


def make_scene():
    frame = np.zeros((160, 220, 3), dtype=np.uint8)
    frame[:] = (80, 0, 0)
    template = np.zeros((8, 36, 3), dtype=np.uint8)
    template[:] = (204, 153, 102)
    template[:, ::4] = (240, 202, 166)
    frame[80:88, 30:66] = template
    frame[120:128, 130:166] = template
    # 角色的帽子與身體以暖色呈現，中間保留小間隔測試形態合併。
    frame[48:55, 93:111] = (0, 180, 255)
    frame[57:68, 89:115] = (40, 40, 255)
    return frame, template


def vision_config():
    return VisionConfig(
        playfield_left=10,
        playfield_top=10,
        playfield_width=190,
        playfield_height=140,
        reference_width=220,
        reference_height=160,
        player_hue_max=40,
        player_saturation_min=140,
        player_value_min=170,
        player_min_width=15,
        player_max_width=50,
        player_min_height=15,
        player_max_height=50,
        normal_platform_threshold=0.95,
        spikes_platform_threshold=0.95,
    )


def test_detects_one_player_in_absolute_coordinates() -> None:
    frame, template = make_scene()
    objects = ObjectDetector(vision_config(), template).detect(frame)

    assert objects.player is not None
    box = objects.player.box
    assert 85 <= box.left <= 93
    assert 45 <= box.top <= 49
    assert 24 <= box.width <= 36
    assert 20 <= box.height <= 32


def test_detects_repeated_normal_platform_templates() -> None:
    frame, template = make_scene()
    objects = ObjectDetector(vision_config(), template).detect(frame)

    assert len(objects.platforms) == 2
    assert all(item.kind is PlatformKind.NORMAL for item in objects.platforms)
    assert {(item.box.left, item.box.top) for item in objects.platforms} == {
        (30, 80),
        (130, 120),
    }
    assert all(item.confidence > 0.99 for item in objects.platforms)


def test_classifies_spikes_with_separate_template() -> None:
    frame, normal_template = make_scene()
    spikes = np.zeros((12, 36, 3), dtype=np.uint8)
    spikes[:] = (178, 178, 178)
    for left in range(0, 36, 9):
        points = np.array([[left, 7], [left + 4, 0], [left + 8, 7]])
        cv2.fillConvexPoly(spikes, points, (255, 40, 40))
    frame[100:112, 70:106] = spikes
    detector = ObjectDetector(
        vision_config(),
        normal_template,
        spikes_platform_template=spikes,
    )

    objects = detector.detect(frame)

    kinds = [item.kind for item in objects.platforms]
    assert kinds.count(PlatformKind.NORMAL) == 2
    assert kinds.count(PlatformKind.SPIKES) == 1


def test_classifies_flipping_platform_with_separate_template() -> None:
    frame, normal_template = make_scene()
    flipping = np.zeros((14, 36, 3), dtype=np.uint8)
    flipping[:] = (75, 90, 115)
    flipping[:, ::6] = (130, 145, 165)
    frame[98:112, 72:108] = flipping
    detector = ObjectDetector(
        vision_config(),
        normal_template,
        flipping_platform_templates=[flipping],
    )

    objects = detector.detect(frame)

    assert any(item.kind is PlatformKind.FLIPPING for item in objects.platforms)


def test_multiple_conveyor_animation_templates_share_one_kind() -> None:
    frame, normal_template = make_scene()
    phase_a = np.zeros((10, 36, 3), dtype=np.uint8)
    phase_a[:] = (110, 110, 110)
    phase_a[:, ::4] = (255, 255, 255)
    phase_b = np.roll(phase_a, 2, axis=1)
    frame[98:108, 72:108] = phase_b
    detector = ObjectDetector(
        vision_config(),
        normal_template,
        metal_platform_templates=[phase_a, phase_b],
    )

    objects = detector.detect(frame)

    conveyor = [
        item for item in objects.platforms
        if item.kind is PlatformKind.CONVEYOR
    ]
    assert len(conveyor) == 1


def test_no_player_or_template_returns_empty_candidates() -> None:
    frame = np.zeros((160, 220, 3), dtype=np.uint8)
    frame[:] = (80, 0, 0)

    objects = ObjectDetector(vision_config(), None).detect(frame)

    assert objects.player is None
    assert objects.platforms == []


def test_annotated_frame_keeps_original_dimensions() -> None:
    frame, template = make_scene()
    detector = ObjectDetector(vision_config(), template)
    objects = detector.detect(frame)

    annotated = detector.annotate(frame, objects)

    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)
