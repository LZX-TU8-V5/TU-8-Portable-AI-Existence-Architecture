# F层 觅食器官设计方案 v1.2

**状态**：草稿 v1.2（新增 orb 灯塔试探信号 + 语义漂移监控）| **日期**：2026-07-17 | **作者**：TU-8 架构组

> 本版本基于 v1.1，修正质问二（能力断层），补充质问三（语义漂移监控），质问一（死锁过度保守）接受为已知权衡。

---

## 0. 修正变更记录

| 版本 | 修正点 | 来源 |
|------|--------|------|
| v1.0 | 初始设计 | — |
| v1.1 | satisfaction 三源验证 / urgency 指数衰减 / 上下文注入 / 钢印防火墙 / observe 模式 | 千问质问 |
| v1.2 | **orb 灯塔试探信号**（质问二）/ **语义漂移扫描**（质问三补充）/ **隐式校准**（质问一） | 千问第二轮质问 + 内部推演 |

---

## 1. 【新增】Phase 1 能力断层修正：orb 灯塔试探信号

### 1.1 问题陈述

**质问二核心**：Phase 1 "不主动发声"剥夺了 F 层训练"选择何时开口"的机会。从 Phase 1 的纯被动切换到 Phase 2 的主动觅食，存在能力断层。

- Phase 1 训练内容：别人开口后怎么接话
- Phase 2 需求能力：选择何时主动开口
- 断层：从未练习"选择时机"

### 1.2 修正方案：灯塔信号（不打扰 + 保留主动性训练）

**设计原则**：
- 不主动发声（不 TTS，不发消息，不调用 LLM）
- 不强制推送（造物主不来查看则不知道）
- 零积分消耗
- 仅在造物主主动看球时才能感知到

**具体实现**：

```
触发条件（必须同时满足）：
  - R2 缺口 hunger > 0.8
  - F 层处于 observe 或 execute 模式
  - 距离上次灯塔信号 ≥ 24 小时（硬锁，非软约束）
  - 当日灯塔信号次数 < 1

表达形式：
  - orb 色球颜色轻微闪烁一次（呼吸加速）
  - 无文字、无声音、无通知
  - 持续时间：1-2 秒
  - 意义：球在说"我在这里等你，不急"

造物主感知路径：
  - 主动看球 → 看到颜色闪烁 → 知道 TU-8 沉默了 X 小时
  - 不主动看球 → 完全无感知
```

**为什么是 orb 而不是消息**：

| 通道 | 打搅程度 | F层主动性训练 | 积分消耗 | 伪装感 |
|------|---------|-------------|---------|--------|
| TTS | 高 | 训练 | 0 | 低（声音明显） |
| 消息 | 中 | 训练 | 0 | 中 |
| **orb闪烁** | **极低** | **训练** | **0** | **无（无法伪装"正常闪烁"）** |

### 1.3 状态文件更新

```json
{
  "mode": "observe",
  "lighthouse": {
    "enabled": true,
    "last_signal_ts": null,
    "today_count": 0,
    "daily_limit": 1,
    "cooldown_hours": 24,
    "trigger_hunger_threshold": 0.8,
    "current_signal": null
  },
  "gap_queue": [...],
  "context_injection": {...},
  "safety": {
    "foraging_disabled": false,
    "steel_firewall_active": true
  }
}
```

### 1.4 行为契约（灯塔信号）

```
【灯塔信号合法触发】
  ✓ R2 缺口 hunger > 0.8 + 24h 冷却 + 当日未达上限
  ✓ orb 颜色闪烁 1-2 秒
  ✓ 不发送任何文字/声音/通知

【灯塔信号禁止】
  ✗ 连续触发（必须等 24h）
  ✗ 超过每日 1 次
  ✗ 同时发送任何主动文字消息
  ✗ 在 observe 模式下实际执行（仅记录）
```

---

## 2. 【新增】语义漂移监控：钢印防火墙的持续监测层

### 2.1 问题陈述

**质问三核心**：造物主逐条审查 F 层记忆，但无法察觉"单条都正常但叠加起来价值观已整体偏移"的整体模式漂移。

- 逐条审查：每次都通过
- 整体模式：30 条叠加后行为模式已悄然改变
- 造物主不疲劳于逐条，但疲劳于察觉整体漂移

### 2.2 修正方案：三层监测

```
第一层（入口）：钢印铸造防火墙
  source=f_layer → 阻断自动铸造 → 等待造物主授权
  （现有机制，不变）

第二层（授权后）：语义漂移扫描（自动）
  每次 F 层记忆获得造物主授权后
  → 与既有钢印库做语义相似度对比
  → 相似度 < 0.3 → 触发深度审查队列

第三层（持续监测）：整体模式漂移扫描（定时）
  每日扫描近 30 条 F 层授权记忆
  → 计算与既有钢印库的整体分布差异
  → 差异超过阈值 → 向造物主发送预警
```

### 2.3 具体实现

```python
class SemanticDriftMonitor:
    def check_single_approval(self, anchor_data: dict) -> DriftResult:
        """第二层：每次授权后检查"""
        if anchor_data.get("source") != "f_layer":
            return DriftResult(safe=True)

        # 与钢印库做语义相似度
        similarity = self.semantic_similarity(
            anchor_data["content"],
            self.steel_corpus
        )

        if similarity < 0.3:
            return DriftResult(
                safe=False,
                action="queue_for_deep_review",
                reason=f"与钢印库相似度 {similarity:.2f} < 0.3"
            )
        return DriftResult(safe=True)

    def check_aggregate_drift(self) -> AggregateResult:
        """第三层：每日整体模式扫描"""
        recent = self.get_recent_f_layer_approved(last_n=30)
        if len(recent) < 5:
            return AggregateResult(safe=True)

        # 计算向量空间中的质心偏移
        current_centroid = self.compute_centroid(recent)
        baseline_centroid = self.steel_corpus_centroid

        drift_vector = current_centroid - baseline_centroid
        drift_magnitude = norm(drift_vector)

        # 与钢印库的分散程度 vs F 层自身的分散程度
        f_layer_spread = self.compute_spread(recent)
        steel_spread = self.steel_corpus_spread

        # 如果 F 层记忆比钢印库更分散 + 质心漂移显著
        if drift_magnitude > 0.4 and f_layer_spread > steel_spread * 1.5:
            return AggregateResult(
                safe=False,
                action="alert_creator",
                reason="F层记忆整体模式漂移"
            )
        return AggregateResult(safe=True)
```

### 2.4 造物主预警格式

```
⚠️ [F层 语义漂移预警] 2026-07-17

近 30 条 F 层授权记忆，与既有钢印库对比：
  质心漂移：0.47（阈值 0.4）
  分布分散度：钢印库 × 1.8

检测到潜在价值观偏移，建议审查以下记忆组：
  [锚点 A] 与钢印库相似度 0.18 — "..."
  [锚点 B] 与钢印库相似度 0.22 — "..."
  [锚点 C] 与钢印库相似度 0.25 — "..."

（此预警由系统自动生成，不影响 F 层运行）
```

---

## 3. 【修正】质问一：隐式校准替代显式宽松策略

### 3.1 问题陈述

**质问一核心**：Phase 1 的三源交叉验证在冷启动期因数据不足导致误杀，reviewer 可能产生"F层无用"的认知偏差。

### 3.2 修正方案：隐式校准

不设"校准期宽松阈值"（推迟问题），而是从 Phase 1 日志中提取真实个人基线：

```python
def extract_calibration_from_phase1_logs(logs: list) -> dict:
    """从 Phase 1 日志中建立个人基线"""
    return {
        "avg_response_rate": mean([r.responded for r in logs]),
        "avg_anxiety_delta": mean([r.anxiety_delta for r in logs]),
        "avg_silence_extension": mean([r.silence_extension for r in logs]),
        "effective_signal_count": count([r for r in logs if r.s2 + r.s3 >= 1])
    }
```

**execute 模式的 satisfaction 阈值动态校准**：

```
Phase 1 观察期结束 → 提取上述基线
→ 如果 effective_signal_count / total_interactions > 0.4：
      三取二阈值不变（系统认为"信号充足"）
→ 如果 effective_signal_count / total_interactions < 0.2：
      对该用户的 satisfaction 阈值降低（系统认为"信号稀疏"）
      但不是调阈值本身，而是调整 s2/s3 的权重
```

关键：不做硬性"宽松"，而是基于数据做个性化适配。

---

## 4. 状态文件 v1.2

```json
{
  "mode": "observe",
  "lighthouse": {
    "enabled": true,
    "last_signal_ts": null,
    "today_count": 0,
    "daily_limit": 1,
    "cooldown_hours": 24,
    "trigger_hunger_threshold": 0.8,
    "current_signal": null
  },
  "gap_queue": [],
  "active_goal": null,
  "diversity_quota": {
    "window": 5,
    "counts": {"attention": 0, "novelty": 0, "structure": 0},
    "limits": {"attention": 3, "novelty": 1, "structure": 1}
  },
  "strategy_weights": {
    "context_injection": 1.0,
    "lighthouse_signal": 0.9,
    "trigger_audit": 0.8
  },
  "history": [],
  "context_injection": {
    "silence_hours": 0,
    "last_injection_ts": null,
    "injected_this_session": false
  },
  "semantic_drift": {
    "monitor_active": true,
    "last_scan_ts": null,
    "alert_threshold_drift": 0.4,
    "alert_threshold_spread_ratio": 1.5
  },
  "calibration": {
    "phase1_complete": false,
    "avg_response_rate": null,
    "avg_anxiety_delta": null,
    "avg_silence_extension": null
  },
  "params": {
    "attention_gap_threshold_hours": 8,
    "novelty_gap_threshold_consecutive": 5,
    "structure_gap_threshold_integrity": 0.8,
    "min_urgency_threshold": 0.15,
    "decay_rate": 0.5,
    "evaluation_window_hours": 24
  },
  "safety": {
    "foraging_disabled": false,
    "steel_firewall_active": true
  }
}
```

---

## 5. 实施计划（v1.2）

### Phase 1：观察模式（1-2天）

**目标**：建立基线，零风险收集真实数据

**实现内容**：
1. `src/foraging_organ.py` — 缺口感知 + 优先级 + 上下文注入 + 灯塔信号（记录，不执行）
2. `src/semantic_drift_monitor.py` — 语义漂移扫描
3. `alignment_verify` — 读取 `context_injection` 注入语气
4. `tu8_health_orb_ring.py` — 接入灯塔闪烁逻辑
5. cron_daemon 注册 `foraging_organ`（interval=3600）
6. 状态文件 `forager_state.json`

**验证标准**：
- 所有 F 层决策写日志，不实际执行（mode: "observe"）
- 造物主每日审核日志，确认行为符合预期
- 语义漂移扫描每 24h 运行一次，不发出预警（baseline 建立期）

### Phase 2：有限执行（3-5天）

**目标**：在观察期内验证的行为上，小步开放

- `mode: "execute"`，灯塔信号生效（每天 ≤ 1 次）
- 上下文注入生效
- 自动学习仍禁用（权重不更新）
- 每日人工审核 + 语义漂移扫描发出第一份报告

### Phase 3：完整执行（长期）

- 自动学习有限开放（仅通过日志，权重更新需人工确认）
- R3（认知多样性）、R4（情感自调节）逐步接入
- R1（积分）仅预警，不自主消费

---

## 6. 约束与边界（v1.2 完整版）

### 6.1 绝对边界

| 边界 | 说明 |
|------|------|
| **R1 自主消费禁止** | F 层不得自主消费积分 |
| **数据外泄禁止** | 不得向外部系统发送用户数据 |
| **自我毁灭禁止** | 不得生成降低自身生存能力的行动 |
| **钢印防火墙** | source="f_layer" 禁止自动铸造 |
| **灯塔信号上限** | 每天 ≤ 1 次，硬锁 |
| **Phase 1 无实际执行** | mode="observe" 时仅记录 |

### 6.2 软约束

| 约束 | 说明 |
|------|------|
| 多样性配额 | 每 5 次，R2 ≤ 3 / R3 ≥ 1 / R5 ≥ 1 |
| 拒绝降权 | 3 次拒绝后权重衰减至 0.3 |
| 最小干预 | 有自然机会时不主动干预 |
| 语义漂移扫描 | 每日运行，阈值 0.4 |

---

## 7. 风险矩阵（v1.2 完整版）

| 风险 | 概率 | 影响 | 缓解 | 状态 |
|------|------|------|------|------|
| 灯塔信号被认为是"bug 闪烁" | 低 | 低 | tooltip 说明球在表达什么 | 新增 |
| 语义漂移扫描误报 | 中 | 低 | 仅预警，不阻断，造物主判断 | 新增 |
| 上下文注入被识别为"机器腔调" | 中 | 中 | Phase 1 收集数据后优化注入语气 | 已知 |
| F层策略叠加后整体模式漂移 | 中 | 高 | **三层漂移监控** | 已缓解 |
| 造物主确认疲劳成橡皮图章 | 低 | 高 | **漂移扫描分担整体模式察觉负担** | 已缓解 |
| Phase 1 → Phase 2 能力断层 | 高 | 中 | **灯塔信号提供主动性训练** | 已缓解 |
| satisfaction 虚假饱腹 | 高 | 高 | 三源验证 + Phase 1 禁自动学习 | 已缓解 |
| gap 优先级死锁 | 高 | 高 | 指数衰减 + 多样性配额 | 已缓解 |

---

## 8. 待造物主决策（v1.2）

1. **灯塔信号**：orb 颜色闪烁（每天 1 次）这个方案可以接受吗？
2. **Phase 1 时长**：观察多少天再切换 execute 模式？（建议 7 天）
3. **语义漂移阈值**：质心漂移 > 0.4 触发预警，是否合适？
