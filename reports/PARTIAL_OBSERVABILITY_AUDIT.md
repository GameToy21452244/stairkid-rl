# Partial Observability Audit

日期：2026-07-30

## 結論

原本的 10／30 個「真實 control transition」exact screen-y gate 不適合作為
v0 simulator 的 Go gate。原因不是參數尚未最佳化，而是初始 268 維 state
只包含 viewport 內最多 8 個平台；30 transitions 約 3.75 秒，平台上捲約
360 px，必然依賴初始畫面外、尚未生成到 observation 的隨機平台。

此結論不允許忽略多步 fidelity。替代 gate 是：

1. 可觀測的一步 x/y/vx/vy；
2. landing geometry precision／recall 與 death 誤判；
3. 10／30-step 水平穩定性；
4. 30-step landing／floor 的 seeded 分布 fidelity。

## 證據

- R14 calibration：649 transitions；LEFT 125、RIGHT 131、非零 RELEASE 29、
  free-motion 237、landing 23。
- 一步 fitted MAE：x 3.99 px、y 6.83 px、vx 32.67 px/s、vy 56.17 px/s，
  全部通過既定門檻。
- landing classifier：precision 0.846、recall 0.957、death
  misclassification 0。
- hybrid open-loop 的水平誤差：10-step 7.10 px、30-step 17.28 px，均低於
  25／60 px。
- 同一 hybrid model 的 screen-y 會在漏掉初始 viewport 外平台後發散；
  放寬水平 0–20 px、垂直接觸 2–30 px 仍不能合理修復，因此沒有採用碰撞
  margin 來「過門檻」。
- episode-held-out ridge endpoint predictor 直接使用初始 4-frame state、
  可見平台和完整 action sequence；在探索的 ridge grid 中，樂觀的 y MAE
  仍約為 10-step 52.3 px、30-step 95.4 px，高於 30／70 px。這是偏樂觀的
  可觀測性下界，不是 simulator 成績。
- 實際軌跡可在第 4 與第 8 transition 從畫面底部出現初始 state 未包含的
  新平台；不同回合的平台 x／kind 序列不同，不能由 floor index 固定重建。

## 修訂

exact-pixel y/vy rollout 保留為診斷，不再作為「進入短 simulator
learnability probe」的必要條件。不得以 teacher-forcing 未來平台或未來
motion/event 宣稱 exact rollout 通過。

新的 seeded distribution gate 使用相同 baseline：

- 真實 landing-focused：325 steps、17 landings、12 floors；
- simulator：2,490 steps、150 landings、150 floors；
- landing two-proportion z = −0.569；
- floor two-proportion z = −1.698；
- 雙尾 α=0.05，兩者皆滿足 |z|≤1.96。

## 授權範圍

此修訂只打開固定 seed、固定步數、離線 simulator learnability probe。
BC、DAgger、Residual、DQfD、長 RL 與新增實機 rollout 仍為 No-Go。
