# interoception_liveness 监控巡检发现（2026-09-21 11:26）

## 目标
执行 cron「TU8监测存活」：`python src/interoception_liveness.py --stale-min 360 --degraded-ok`，输出脚本全部输出。
实际结果：**脚本零输出（退出码 0）**。本文件记录该零输出的根因与真实存活判断。

## 关键推理

1. **零输出 = 边沿触发静默**，不是崩溃。
   脚本逻辑：`sig == prev → return`（不打印）。所以本次的 `problems` 签名与 `interopertion_liveness_last.json` 里存的签名完全相同。

2. **存的签名是 `[missing]`**（记录时间 2026-08-09 10:31:09）：
   `"interopertion_state.json 不存在（监控从未运行或已死）"`

3. **根因 = 脚本内路径拼写错误（大小写/字母缺失）**：
   - 脚本常量：`STATE = memory/interopertion_state.json`（intero**p**ertion，少一个 c）
   - 实际文件：`memory/interoception_state.json`（intero**c**eption）
   - 结果：元监控**永远读不到真实状态文件**，从 2026-08-09 起 problem 签名恒为 `[missing]`，边沿触发使其永久静默 → **元监控实际上已聋约 6 周**。

4. **真实内感受状态**（读实际文件）：
   - `memory/interoception_state.json` 最后更新 **2026-09-21 01:33:04**，`status=ok`，`body_posture=nominal`，`pain_signals=[]`
   - 距巡检时刻（11:26）约 **593 分钟 > 360min** → 按设计阈值，内感受监控本体**疑似已停摆约 9.9 小时**，但因 (3) 的 typo，元监控未能报出 stale。
   - 注意：`interoception_history.json` 同样停在 01:33:04，佐证是本体停摆而非仅状态文件未刷新。

5. 附带发现：工作区同时存在两套命名
   - `interoception_*`（正确拼写，有 2026-08/09 更新）
   - `interopertion_*`（typo，2026-07/08 更新）
   两套 last/alerts 文件并存，进一步说明历史上曾有过一次拼写改名的半途迁移。

## 结论
- 本次 cron **无输出是预期行为**，不是新的故障信号。
- 但存在**两个真实问题**：
  - P1：`interoception_liveness.py` 的 `STATE` 路径 typo，导致元监控自 2026-08-09 起静默失效。
  - P2：内感受监控本体自 2026-09-21 01:33 起约 10 小时未产出，需排查其调度/运行。
- 未做任何脚本改动（涉及监控链路，属需造物主确认项）。已记入 `memory/2026-09-21.md`。

## 建议处置（待确认）
1. 修 `STATE` 为 `interoception_state.json`（或改为自动探测两套命名）。
2. 单次 forced 告警测试（清 last.json 后重跑），确认告警链路活着。
3. 排查 01:33 后内感受监控未运行的原因（cron/上游 LLM 可用性）。
