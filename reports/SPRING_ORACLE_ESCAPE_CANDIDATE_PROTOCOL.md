# Spring Oracle Escape Candidate Gate Protocol

日期：2026-08-03  
狀態：**FROZEN BEFORE CANDIDATE IMPLEMENTATION**

## 唯一候選

`oracle-full-v2-spring-clearance`只修改privileged Oracle-full，不修改Simulator physics、
spring 190 px/s、一般Baseline、Teacher-observable或真機controller。

當`last_landed_floor`是spring且player仍在spring top以上時：

1. 依下一層target相對位置選擇離開spring的方向；target近似置中時選擇畫面空間較大側。
2. player body尚未完全離開spring bounds＋2 px clearance時持續向外。
3. 已離開但尚未落到spring top以下時RELEASE，避免過度橫移。
4. player通過spring top後立即恢復原Oracle對下一層target的velocity tracking。
5. 若偏好方向受畫面邊界限制，改選可完成clearance的另一側。

這是Oracle環境可解性修復，不是Student label，也不得移植到真機Teacher而省略獨立Gate。

## Regression與non-regression

- 固定失敗seed 10007：舊Oracle (`enable_spring_escape=false`)維持top death；新Oracle
  必須到第10層。
- 對齊spring／next-target中心時，舊Oracle RELEASE，新Oracle必須選一個可離台方向；
  body完全clear但仍在spring上方時必須RELEASE。
- spike-only reference上的新舊Oracle trajectories必須完全相同。

## Development與holdout

- Development：11000～11099，最多600 steps，這是本協議唯一候選。
- Development Gate：overall reach10>=95%、spring-contact reach10>=90%、至少20個
  spring episodes、top<=5%、health death=0、no-spring 100%成功、無collapse。
- Development通過後凍結source/config fingerprint。
- Untouched holdout：12000～12099只跑一次，門檻完全相同；不得回饋調參。
- 12000～12099 Oracle PASS後，才用相同seeds比較candidate Baseline與spike-only
  reference：retention>=80%、reach3>=90%、health death=0、無collapse，且spring
  episodes top death rate<=10%。

任一Gate失敗立即停止後續。即使全通過，也只解除spring distribution的工程阻擋；
conveyor/flipping、support-phase alignment、Dataset v2與Student訓練仍需各自Gate。
