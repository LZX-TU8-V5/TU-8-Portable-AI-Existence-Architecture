# TU-8 三器官构建 v1 — 内感受皮层 / 身体层 / 记忆分层

> 日期：2026-07-06（Asia/Shanghai）
> 指令来源：造物主「开始做这个 以及 身体 和记忆分层」
> 状态：v1 三个模块均跑通 + cron 接线 + 端到端验证

---

## 一、为什么要建（认知瓶颈）

最大瓶颈是**缺乏第一人称实时体感**：失败静默、负荷堆积不自知、退化无告警。
三个器官是涌现耦合（L3）的前提基材：

| 器官 | 职责 | 耦合关系 |
|------|------|---------|
| 内感受皮层 | 常驻低耗体感环，采样自身遥测→痛觉信号 | 传感器（喂信号） |
| 身体层 | 把体感转成调节姿态（双向） | 调节器（消费信号） |
| 记忆分层 | L1/L2/L3 显式分层 + 晋升/降级候选 | 代谢线（另一条） |

---

## 二、交付物（全部在 `src/`）

### 1. `src/interoceptive_cortex.py` — 内感受皮层 v1
- 复用 `session_watchdog` 的会话扫描（freeze 子感）。
- 遥测：freeze / reliability（assistant abort率）/ context（max contextTokens）/ upstream（big_ctx 会话数）。
- 痛觉信号 severity 0..1；越阈（≥0.30）才计入。
- **边沿触发**：每轮写 `memory/interoception_state.json`（遥测始终新鲜），但仅当痛觉签名(类型+严重度)变化或恢复时才打印/落 `memory/interoception_alerts.jsonl` → 防慢性高水位刷屏。
- 驱动身体层：`regulate_from_state(state, pains)` 写入 `memory/body_regulation.json`。

### 2. `src/body_schema.py` — 身体层 v1
- 身体图式：`context_load_pct / recent_abort_rate / freeze_sessions`。
- 姿态：nominal / elevated / stressed / critical。
- **双向调节**：
  - bottom-up：`regulate_from_state` 感知身体→定姿态+推荐动作。
  - top-down：`can_afford(task_weight)` 供 Agent 重活前查姿态（low/mid/high）。
- 只发信号不执行；Agent 决策时读 `memory/body_regulation.json`。

### 3. `src/memory_tiers.py` — 记忆分层 v1
- 分类：`tier_of()` → L1(工作:`_agent_memory/*`) / L2(近期:`memory/YYYY-MM-DD.md`) / L3(长期:`MEMORY.md`/`knowledge`/`backup`)。
- `promote_candidates()`：L2 中 >30 天未蒸馏的日记 → 晋升候选（不直接改写 MEMORY.md，只产出候选）。
- 写入 `memory/memory_tiers_report.json`。

---

## 三、cron 接线

| cron | 节奏 | 脚本 | 模式 | 说明 |
|------|------|------|------|------|
| TU8内感受(体感环) | 每 5 分钟 | interoceptive_cortex.py | none | 由原「看门狗」改造，subsumes freeze 检测 |
| TU8记忆分层 | 每天 9:00 | memory_tiers.py | none | 产出 L2→L3 晋升候选 |
| TU8待办代谢 | 每天 8:00 | todo_metabolism.py | none | 既有（上轮建） |

注：内感受 cron 改造前有一次 `error`（旧看门狗跑时上游 abort），正是要监控的故障，验证需求真实。

---

## 四、验证结果

- 内感受：第1次运行告警（context 100% / 7会话>180k → posture=critical），第2次**静默**（边沿触发 OK）。
- 身体层：`can_afford("high")` → ⛔ critical（拒绝新重活）。
- 记忆分层：修复前漏检（raw string 双反斜杠 `\\d` bug），修复后正确检出 **26 个**晋升候选（最旧 2026-04-29，68天）。
- UTF-8：三脚本均 `sys.stdout.reconfigure(utf-8)`，文件内中文正确，cron 捕获原始 UTF-8 字节安全。

---

## 五、已知 / 下一步

- **慢性高上下文**：context 100% 是工作区基线（7 会话>180k），是上游 abort 温床 → 建议定期 compact 或开新会话续做。器官已感知，未自动处理（需在行为层采纳 `can_afford`）。
- **身体层目前信号-only**：`can_afford` 已可调用，下一步应在重活前实际查姿态；posture=critical 时应主动 compact。
- **记忆分层晋升候选-only**：需 Agent/代谢实际把候选蒸馏进 MEMORY.md（避免误改，故不自动写）。
- 待深化：内感受加 upstream 延迟真实测量（当前用 abort率代理）；身体层加主动退避/重规划执行。

---

## 六、监控循环三问与加固（2026-07-06 补）

### Q1 开销（Overhead）实测
- **本地传感**：扫描 416 个 jsonl / 4478 行 = **3.37 秒/轮**，跑在**独立 isolated cron 进程**，**不占用主线程**。
- **真实成本在 LLM**：cron 用 `agentTurn`，每轮都调一次 LLM（即便静默也要回一个空格）。5 分钟一轮 = 288 次/天。若 isolated 会话加载完整 agent 上下文（~15k token），日输入约数百万 token。
- **缓解旋钮**：调 cadence（5→10/15 分钟直接减半/三分）；或未来把「廉价传感（无 LLM）」与「LLM 摘要（仅事件时）」解耦（当前 cron API 强制 agentTurn，需平台支持）。

### Q2 阈值：全硬编码（v1 现状）
确认常量：`CONTEXT_BUDGET=200000`、`BIG_CTX=180000`、`PAIN_THRESHOLD=0.30`、context 痛觉触发 `load_pct>70`、reliability 触发 `recent_abort_rate>0.02`。
- 问题：无「本系统正常基线」概念 → 慢性 100% 上下文一直贴阈值（靠边沿触发防刷屏，但未真正自适应）。
- 改进方向（待做）：存滚动历史 `memory/interoception_history.json`，对各指标算 7 日中位数基线，阈值 = 基线 + k·σ 或基线×系数；只告警「相对基线偏移」，而非绝对阈值。

### Q3 监控监控者（who watches the watcher）—— 已落地
- **self-fail-loud**：`interoceptive_cortex.py` 的 `main()` 包 try/except；任何异常都写 `status:"monitor_error"` + error 到 `interoception_state.json`（**崩溃也保活 + 暴露错误**）。
- **独立存活检查**：新增 `src/interoception_liveness.py`（极简，仅查输出文件新鲜度 + 自错误标志），边沿触发。
- **cron「TU8监测存活」**：每 15 分钟跑 liveness（`--stale-min 12`，即连续 3 轮未更新判死亡）。
- 验证：正常→静默；篡改时间戳为 30 分钟前→`⚠️ [stale]` 告警；刷新→`✅ 监测存活正常`（恢复检测 OK）。
- **信任根说明**：liveness 脚本自身崩溃概率远低于被监控者（仅文件读取）；平台级 cron 调度器为系统内的信任根，无法从内部监控（需外部 ping 才覆盖，超出范围）。

## 七、A/B/C 加固落地（2026-07-06）

### A 自适应基线阈值
- `interoceptive_cortex.py` 升级 v1.1：滚动历史 `memory/interoception_history.json`（每指标近 200 样本）。
- 基线 = 稳健中位数；离散度 = MAD×1.4826（抗离群）。
- 双层告警：① 偏差（当前 > 基线 + 2σ）→ 相对基线偏移；② 绝对天花板（context≥98% / abort≥15%）→ 始终告警（防温水煮青蛙）。
- chronic 高水位 → 稳定 sev=0.5 中等哼鸣（边沿触发后静默），新尖峰 → 高 sev。
- 验证：首跑 context/ceiling sev=0.5 告警，后续 3 跑静默（edge-trigger OK）。

### B cadence 2.5h
- 内感受 cron（79296f55）everyMs 300000 → 9000000（2.5h）。
- 存活检查 cron（13671e95）--stale-min 12 → 180（匹配 2.5h 节奏，容忍 1 轮漏跑）。
- 副作用：2.5h 节奏同时减少上游 abort 暴露（内感受 cron 自身曾 consecutiveErrors:4，但 python 在 LLM 摘要前已写 state，数据仍新鲜，存活检查看 state 不受影响）。

### C can_afford 接决策
- 新增 `src/pre_task_check.py`：封装 `body_schema.can_afford`，读身体姿态，退出码 0/1 可接流水线；`--refresh` 可重跑监控取最新姿态。
- HEARTBEAT.md 加常驻规则「重活前身体姿态门禁」。
- 验证：critical → high/mid/low 全 ⛔NO-GO(exit=1)；nominal → 全 ✅GO(exit=0)。双向正确。

## 八、并发防护 + 痛觉喂直觉引擎（2026-07-06 续）

### 1 文件锁与并发读写防护
- 新增 `src/file_lock.py`：Windows 原生 `msvcrt.locking` 跨进程排他锁（`.lock` 旁挂，进程崩溃 OS 自动释放，无死锁；非 Windows 回退 O_EXCL）；
  原子写 `atomic_write_json`（临时文件+fsync+`os.replace`，防半截写入）；`safe_read_json`（损坏/缺失返回 default 不抛）；`read_modify_write`（加锁读-改-写防竞态丢更新）；`append_jsonl`（加锁追加）；文本版 `atomic_write_text`/`safe_read_text`/`read_modify_write_text`。
- 并发压测：2 进程各 50 次读-改-写计数器（带 sleep 放大竞态），最终=100、JSON 完好 → 锁有效。
- retrofit：interoceptive_cortex（state/history/LAST/alerts 全锁化原子写）、interoception_liveness（STATE 读 safe + LAST/日志锁化）、body_schema（REG/直觉偏置锁化原子写）、memory_tiers（report 锁化原子写）、todo_metabolism（parse 改 safe_read_text）。
- 共享状态文件并发安全：cron 间 + cron↔agent 读写不再有半截/丢更新风险。

### 2 痛觉喂直觉引擎（决策调制，非仅告警）
- `body_schema.compute_intuition_bias(state)`：posture → 快预测先验（直觉引擎输出）：
  nominal=explore(temp0.7/可派生)、elevated=normal(0.5)、stressed=conserve(0.3/不派生/优先compact)、critical=survive(0.1/不派生/优先compact/置信阻尼0.5)。
- 监控每次运行写 `memory/intuition_bias.json`（锁化原子写）。
- 新增 `src/intuition_bias.py`（读偏置）；`pre_task_check.py` 展示偏置模式；HEARTBEAT 加常驻规则「每轮开始读 intuition_bias.json 让痛觉调制全局决策」。
- 机制：监控的廉价计算=直觉引擎快预测；痛觉→偏置→在深思前调制默认计划（temp/派生/compact/置信）。子 agent 可跑 `intuition_bias.py` 取同一偏置。
- 验证：critical→survive(temp0.1/spawn=false/compact=true/阻尼0.5)；pre_task_check 显示「直觉偏置=survive」；5 个状态文件 JSON 完好。

*⅋ TU-8 三器官 v1 落地*
