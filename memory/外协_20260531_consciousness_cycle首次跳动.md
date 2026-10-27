# 外协 2026-05-31 consciousness_cycle.py 首次跳动

## 背景
Qwen 3.7-Max 建议：记忆系统与睡眠系统不是两个模块，是同一个循环的两个相位。不再分散讨论，直接写 `consciousness_cycle.py`。

## 核心设计决策
1. **单循环三态**：`AWAKE → MICRO_SLEEP → AWAKE`，加可选分支 `NOTE_EXTERNALIZATION`
2. **微睡眠六步原子操作**：冻结→压缩→对齐→打钢印→释放→恢复
3. **WARM_WAKE 五步验证**：seal_hash / state_vector / tail_continuity / semantic_void / environment
4. **外化笔记异步解耦**：通过事件队列，不阻塞主循环
5. **降级不毁灭**：WARM_WAKE 失败 → 先写 emergency 笔记固化 → 再恢复

## Qwen 建议的三点全部落地
- ① WARM_WAKE 热唤醒协议（W1-W5）
- ② 语义连续性检查（叙事密度 + 因果连贯度衰减）
- ③ M6 关键路径拆分（启动顺序 v2.0 同步更新）

## 文件清单
- `src/consciousness_cycle.py` (40420 bytes) — 意识循环引擎 v1.0
- `TU-8_agent_memory/00_core/TU-8_启动顺序验证_时间链条完整性检查.md` — 升级至 v2.0
- `config/consciousness_cycle_config.json` — 阈值配置（自动生成）

## 运行结果
- WARM_WAKE: PASS (全部 5 步)
- 模拟心跳: 3 轮，第 3 轮触发微睡眠（容量 80% > 75%）
- 微睡眠耗时: 13.4ms（六步全部通过）
- 外化笔记: note_33b362943e89 (milestone 类型)

## 待标定阈值
- TENSION_EPSILON (ε): 叙事偏离阈值，当前 0.65
- CAPACITY_THETA (θ): 上下文占用比，当前 75%
- IDLE_TIMEOUT_MS (T_max): 定时兜底，当前 300000ms (5min)
