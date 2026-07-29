from stair_agent.game_events import GameEvent, GameEventDetection
from stair_agent.game_state import GamePhase
from stair_agent.hud_detection import HealthEvent, HealthUpdate
from stair_agent.object_detection import (
    BoundingBox,
    GameObjects,
    PlatformDetection,
    PlatformKind,
    PlayerDetection,
)
from stair_agent.object_tracking import (
    MotionState,
    PlatformTrackingState,
    PlayerTrackingState,
)
import json

from stair_agent.observation import ObservationBuilder, ObservationJsonlWriter


def test_observation_is_json_serializable_dictionary() -> None:
    platform = PlatformDetection(
        BoundingBox(40, 100, 96, 16),
        PlatformKind.NORMAL,
        0.98,
        track_id=7,
    )
    player = PlayerDetection(BoundingBox(60, 70, 24, 27), 0.9)
    objects = GameObjects(
        player,
        [platform],
        BoundingBox(40, 64, 383, 363),
    )
    player_state = PlayerTrackingState(
        player,
        3.0,
        12.0,
        MotionState.FALLING,
        platform,
        3,
    )
    platform_state = PlatformTrackingState(objects, -15.0, 1)

    observation = ObservationBuilder().build(
        timestamp=12.5,
        phase=GamePhase.PLAYING,
        player_state=player_state,
        platform_state=platform_state,
        health=HealthUpdate(8, -4, HealthEvent.DECREASED),
        events=[GameEventDetection(GameEvent.SPIKE_DAMAGE, platform, -4)],
    )
    payload = observation.to_dict()

    assert payload["phase"] == "playing"
    assert payload["player"]["motion"] == "falling"
    assert payload["nearest_platform"]["track_id"] == 7
    assert payload["platform_scroll_velocity_y"] == -15.0
    assert payload["events"][0]["type"] == "spike_damage"


def test_observation_jsonl_writer_writes_one_record(tmp_path) -> None:
    platform = PlatformDetection(
        BoundingBox(40, 100, 96, 16),
        PlatformKind.NORMAL,
        0.98,
        track_id=7,
    )
    player = PlayerDetection(BoundingBox(60, 70, 24, 27), 0.9)
    objects = GameObjects(
        player,
        [platform],
        BoundingBox(40, 64, 383, 363),
    )
    observation = ObservationBuilder().build(
        timestamp=1.0,
        phase=GamePhase.PLAYING,
        player_state=PlayerTrackingState(
            player,
            0.0,
            0.0,
            MotionState.STABLE,
            platform,
            3,
        ),
        platform_state=PlatformTrackingState(objects, -10.0, 1),
        health=HealthUpdate(12, 0, HealthEvent.UNCHANGED),
        events=[],
    )
    path = tmp_path / "observations.jsonl"

    with ObservationJsonlWriter(path) as writer:
        writer.write(observation)

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["nearest_platform"]["track_id"] == 7
