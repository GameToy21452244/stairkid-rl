from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .dialog_handler import (
    DialogActionHandler,
    DialogActionOutcome,
    StableObservation,
)
from .game_state import GamePhase
from .observation import GameObservation


class EpisodeResetError(RuntimeError):
    """回合無法在單次 Enter 的安全限制內重設。"""


class ReleaseController(Protocol):
    def release_all(self) -> None: ...


class SingleEnterEpisodeResetter:
    """已在 PLAYING 則不送鍵；DIALOG 時最多只送一次 Enter。"""

    def __init__(
        self,
        *,
        handler: DialogActionHandler,
        controller: ReleaseController,
        observe: Callable[[], GameObservation],
        reset_pipeline: Callable[[], None],
    ) -> None:
        self.handler = handler
        self.controller = controller
        self.observe = observe
        self.reset_pipeline = reset_pipeline
        self.last_enter_sent = False
        self.last_stable: StableObservation | None = None

    def reset(self) -> GameObservation:
        self.last_enter_sent = False
        self.last_stable = None
        self.controller.release_all()
        try:
            before = self.handler.observe_stable()
            self.last_stable = before
            if before.phase is GamePhase.PLAYING:
                pass
            elif before.phase is GamePhase.DIALOG:
                self.last_enter_sent = True
                result = self.handler.execute_once(before)
                self.last_stable = result.after
                if result.outcome is not DialogActionOutcome.PLAYING:
                    raise EpisodeResetError(
                        "已送出一次 Enter，但遊戲沒有進入 PLAYING；"
                        f"結果為 {result.outcome.value}。依安全限制停止，"
                        "不會自動送出第二次 Enter。"
                    )
            else:
                raise EpisodeResetError(
                    "只有穩定的 playing 或 dialog 可以重設；"
                    f"目前為 {before.phase.value}，沒有送出 Enter。"
                )

            self.reset_pipeline()
            observation = self.observe()
            if observation.phase != GamePhase.PLAYING.value:
                raise EpisodeResetError(
                    "重設後重新擷取的結構化狀態不是 PLAYING；"
                    f"目前為 {observation.phase}。已停止。"
                )
            return observation
        finally:
            self.controller.release_all()
