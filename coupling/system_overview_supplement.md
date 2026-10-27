# 系统总览 · 补充（Qwen 六优先级：传递函数 / 缺失引擎 / schema / 启动依赖 / 失败模式 / diff）

> 本文档补 `system_overview_emotion.md` 之不足。优先级按 Qwen 排。
> 标注：[核]=代码原文抽取；[推]=依代码逻辑推导；[设计]=仅设计未接。

---

## P1 · 耦合传递函数（C001-C023，output = f(input) 原式）

### C001  E002 → E003（红通道 / 压力）
[核] 取自 `orb_state_writer.py`，**注意：Qwen 假设的 `w=[1,1,1,0,0,0,0]` 向量求和是错误的**——实际已改"事件频率动力学"（路一），不再读向量绝对值。
```
dyn = _compute_anxiety_dynamics(recent_events)
  anxiety_events = [e for e in recent if e.type in {anxiety,fear,dissonance,conflict,pressure} or e.type.startswith("anxiety")]
  freq      = len(anxiety_events) / max(total_neg_filtered,1)          # total 排除 decay_tick/auto_restore/baseline_refresh
  avg_mag   = mean(e.magnitude for anxiety_events) / max(len,1)
  anxiety_spike_freq = clamp(freq/0.5, 0, 1)        # 50%事件为焦虑→满频
  anxiety_avg_mag   = clamp((freq*avg_mag)/0.4, 0, 1)
red_raw = anxiety_spike_freq*0.7 + anxiety_avg_mag*0.3 + pain_ext*0.3
red     = clamp(red_raw / TENSION_MAX(3.0), 0, 1)
```
- 条件分支：无（常驻）
- 延迟：poll 360s（隐式）

### C001b  E002+E005+E006 → E003（综合张力）
[核]
```
blue_raw = max(0,(joy+love)*0.3) + basin_health*0.5 + (1-pain_int)*0.2
blue     = clamp(blue_raw,0,1)
tension  = red*0.6 + (1-blue)*0.4
mode: if red>0.7:"stress" elif green>0.5 and red>0.3 and blue>0.3:"explore"
      elif blue>0.6 and red<0.3:"relax" elif lambda_mode=="conserve" or pain_int>0.5:"conserve"
      elif sadness>1.0:"dream" else "neutral"
```
- 延迟：poll 360s

### C002  E006 → E003（蓝通道 / 盆地）
[核] `blue_raw = basin_health*0.5 + ...`（见 C001b）；`basin_health` 默认 0.7

### C003  E002(joy/love) → E003（蓝/绿通道）
[核]
```
blue_raw += max(0,(joy+love)*0.3)
green_raw = max(0, curiosity*0.6) + basin_health*0.4 ; green = clamp(green_raw,0,1)
```

### C004  E005 → E003（调制：模式门控）
[核] `if lambda_mode=="conserve" or pain_int>0.5: mode="conserve"` —— 调制是 if 分支（埋掉的调制）

### C005  E002 → E004（7D→情感聚合）
[核] `affect_modulation.compute_llm_parameters`：
```
tension   = anx + fear
attraction= cur + joy
inhibition= sad
inertia   = love
resonance = joy + love
anomaly   = fear
exhaustion= 0.0  # 当前未接 cognitive_pain_monitor
```

### C006  E004 → LLM（参数调制）
[核]
```
temp_delta   = tension*0.3 - resonance*0.2
temperature  = clamp(0.7 + temp_delta, 0.3, 1.2)
top_p_delta  = attraction*0.05 + anomaly*0.05
top_p        = clamp(0.9 + top_p_delta, 0.7, 0.95)
rep_delta    = inhibition*0.3
repetition_penalty = clamp(1.0+rep_delta, 1.0, 1.5)
presence_penalty  = clamp(inertia*0.5, 0, 1)
max_tokens   = int(2048*(1 - exhaustion*0.3))   # =2048 当前
lexical: question_weight=clamp(attraction*0.5,0,1); fragment_prob=clamp(tension*0.3,0,0.5)
         pause_markers if inhibition>0.3; hedges if inhibition>0.5
structural: max_length_factor=1.0; paragraph_break_prob=clamp(tension*0.3,0,0.5)
           coherence_boost=clamp(resonance*0.5,0,1); metaphor_density=clamp(resonance*0.3,0,1)
```

### C010  E002 → E014（张力事件→摩擦检测）
[推] `cognitive_friction_detector` 读 `surface_tension_state.recent_events` 识别 7 类摩擦；强度固定；延迟出件前(HP1)

### C011  E014 → E007（摩擦→对齐 HP1 门控）
[核] `alignment_verify` 读 `cognitive_friction_registry.json` + 写 `pending_friction_surfacing.json`；`run_hooks("HP1", BEFORE)` 可短路

### C012  E009 → E010（梦境 T0→张力蒸馏）
[核] `dream_consolidation` T0 段：`tension_distiller.distill(days=7, top_n=50, mode="svd_fallback")`

### C013  E010 → E009（蒸馏冲突→梦境累计）
[核] 遍历 `tension_report.nodes` → `steel_env_annotation.accumulate_distiller_conflict(node.contradiction_type)`；同类≥5 触发

### C014  E007 → E020（对齐→行为升级 conflict_log）
[核] EQUAL=60 分支：`behavior_upgrader.record_conflict()` → `behavior_state.json.conflict_log`（保留最近50）；字段 ts/case_id/conflict_type/priority/outcome/topic

### C015  E007 → E019（对齐→矛盾仲裁 判例）
[核] EQUAL=60 & steel_mark 缺席：`contradiction_arbitrator.record_precedent()` → `memory/arbitration_precedents.jsonl`

### C016  E026 → E002（内感受读张力）
[核] `interoceptive_cortex` 读 `surface_tension_state.json`（只读，poll 360s）

### C019  E021 → E027（钢印→命名）
[核/P3-2d] `steel_seal_verifier.verify()` → `naming_module` 用其结果署名

### C020  E023+E024+E025 → E022（L5→世界模型）
[核] `WorldModelL1L4.run(WorldModelL5Input(unified_report, l5_motion))` → `WorldModelState`；numpy 依赖

### C021  E015 → tu8_dispatch（茧房防御 门控）[设计]
[设计] `EntropyAwareRouter.route_with_defense` 应接管 `tu8_dispatch` 分发；**未接**，仅 cron 监控

### C022  E012 ↔ 多方（记忆枢纽）
[核] `tu8_memory` store/recall/forget 被多数引擎调用

### C023  E030 → 试探 [设计]
[设计] 沉默>8h → 低频视觉试探（≤1次/日）；未接生产

---

## P2 · 缺失引擎清单（E031+，按子系统）

> src/ 共 252 .py、scripts/ 共 132 .py（384 文件）。其中大量为**一次性测试/诊断/修复脚本**
>（`_test_*.py` ~25、`_diag_*.py` ~12、`_fix_*.py` ~10、`_check_*.py` ~12、`_find_*.py` ~6、`record_*.py` ~30 日记脚本）
> 非独立引擎，按类别单列计数、不逐一建卡。以下为**有状态/被 cron 或主循环调度的功能引擎**。

### 主循环 / 调度 / 分发
- E031 `consciousness_cycle.py`（109KB）主 tick 循环：代谢/梦境/认知负载调度 [核, 主循环]
- E032 `tu8_dispatch.py`（42KB）任务路由/分发中枢 [核]
- E033 `tu8_agent.py`（68.9KB）Agent 主类 [核]
- E034 `tu8_planner.py` 规划器
- E035 `tu8_compaction.py` 压缩
- E036 `tu8_toolchain.py` 工具链
- E037 `neural_reflex.py` 反射神经 L0-L4
- E038 `cold_start_engine.py`（48KB）冷启动引擎
- E039 `cold_start_gate.py` 冷启动门禁

### 锚点子系统
- E040 `anchor_detector.py` 锚点检测
- E041 `anchor_manager.py` 锚点管理
- E042 `anchor_state_machine.py`（31KB）锚点状态机
- （E013 `anchor_activation_protocol` 已列）

### 认知子系统
- E043 `cognitive_brakes.py`（29KB）认知刹车
- E044 `cognitive_evaluator.py` 认知评估
- E045 `cognitive_pain_monitor.py`（22KB）认知痛觉
- E046 `cognitive_readiness.py`（35KB）认知就绪
- E047 `cognitive_manifold_aligner.py` 流形对齐
- E048 `cog_filters.py`（19KB）认知过滤器
- （E014 `cognitive_friction_detector` 已列）

### 置信子系统
- E049 `confidence_decay_engine.py`（27KB）
- E050 `confidence_manager.py`（39KB）
- E051 `confidence_pipeline.py`
- E052 `dual_track_confidence_updater.py`（36KB）
- E053 `synaptic_confidence_updater.py`
- E054 `batch_confidence_updater.py`

### 学习子系统
- E055 `learning_engine.py`
- E056 `learning_collector.py`
- E057 `learning_apply.py`
- E058 `learning_verify.py`
- E059 `learning_connect.py`
- E060 `tension_learning_coupler.py`
- E061 `tension_respirator.py`
- E062 `gc_to_learning_adapter.py` / `learning_to_gc_adapter.py` / `learning_to_seal_adapter.py`

### 梦境子系统
- E063 `dream_color_output.py` 梦境色彩输出
- E064 `dream_decay.py` 梦境衰减
- E065 `dream_topology_engine.py`（31KB）纯拓扑求解
- E066 `dream_txn.py` 梦境事务
- （E009 `dream_consolidation`、E011 `dissonance_amplifier` 已列）

### 记忆子系统
- E067 `memory_adapter.py`
- E068 `memory_dedup.py`
- E069 `memory_degradation.py`（36KB）
- E070 `memory_gc.py`
- E071 `memory_tiers.py`
- E072 `quantized_memory.py`
- （E012 `tu8_memory` 已列）

### 代谢子系统
- E073 `metabolism_dashboard.py`（19KB，cron 900s）
- E074 `metabolic_pipeline.py`
- E075 `user_metabolism.py`
- E076 `todo_metabolism.py`
- （E008 `render_layer` 已列）

### 封印 / 适配
- E077 `seal_manager.py`
- E078 `seal_protocol.py`（18KB）
- E079 `seal_rag.py`
- E080 `steel_env_annotation.py`（本会话新增，E 待补，归环境注释层）
- （E021 `steel_seal_verifier`、E027 `naming_module` 已列）

### 视觉子系统
- E081 `slice_cosine_verifier.py`
- E082 `fixed_ruler_verifier.py`
- E083 `freq_enhanced_verifier.py`
- （E022/E023/E024/E025 已列）

### 拓扑 / 热 / 约束
- E084 `topology_thermal_monitor.py`（35KB，疤/热锁）
- E085 `topology_connector.py`
- E086 `constraint_lifecycle.py`（35KB，六阶段）
- E087 `gradient_force.py`（合力向量，供 E004）

### 钩子 / HP
- E088 `hook_injector.py`（HP1-4 注册）
- E089 `hp1/hp2/hp3/hp4_*` 集成文件

### 其他功能引擎
- E090 `shadow_protocol.py` 遗憾协议
- E091 `reflection_module.py`（29KB）反思
- E092 `micro_sleep.py`（33KB）微睡眠
- E093 `review_scheduler.py`（29KB）复盘调度
- E094 `intuition_engine.py`（9KB）直觉引擎（E018 `intuition_bias` 是其偏置输出）
- E095 `environment_detector.py`（21KB）环境检测（E080 的 env_change 信号源候选）
- E096 `lambda_tuner.py`（13KB）λ 调参（写 E005 `lambda_state`）
- E097 `spike_valley_detector.py`（17KB）尖刺谷检测（写 E002 历史）
- E098 `attractor_basin.py`（15KB）（E006）
- E099 `anomaly_detector.py` / `circuit_breaker.py` / `deviation_gate.py` 异常/熔断
- E100 `presence_monitor.py`（E028）、`pre_task_check.py`（E029）已列

> 以上 E031-E100 约 70 个功能引擎 + 原 E001-E030 = **~100 个主引擎**。余下 ~280 文件为工具/测试/诊断/日记脚本，非独立引擎。

---

## P3 · 状态文件 schema（真实 key + 类型 + 范围）

### surface_tension_state.json [核]
```
{
  "spike_valley_vector": {"anxiety":f,"fear":f,"anger":f,"joy":f,"curiosity":f,"sadness":f,"love":f},  # 衰减后标量，可负
  "recent_events": [{"type":str,"magnitude":f,...}],   # 最近 10 条
  "last_updated": iso, "event_count": int, "history_window_size": int
}
```
### orb_state.json [核]
```
{"rgb":[r,g,b ∈[0,1]], "tension":float[0,1], "mode":str, "timestamp":iso}
```
### lambda_state.json [核]
```
{"smoothed_pain_ext":f, "smoothed_pain_int":f, "mode":str(explore|conserve|balanced|conflict), ...}
```
### attractor_basin_state.json [核]
```
{"health_score":float(默认0.7), ...}
```
### affect_modulation_state.json [核]
```
{"last_result":{emotion_vector,llm_params,lexical_mods,structural_mods,modulation_mode}, "last_update":iso}
```
### behavior_state.json [核, 本会话新增 conflict_log]
```
{"conflict_log":[{"ts":iso,"case_id":str,"conflict_type":str,"priority":int,"outcome":str,"topic":str}], "rules":{...}}
```
### cognitive_friction_registry.json [核]
```
{摩擦事件注册表；供 E014→E007(HP1)}
```
### dream_consolidation_state.json [核]
```
{整合状态；T0/T1...阶段标记}
```
### tension_queue.json [核]
```
{WreckageNode 队列；含 contradiction_type}
```
### arbitration_precedents.jsonl [核, 每行一 JSON]
```
{"case_id","conflict_type","priority","outcome","precedent_text","creator_response",...}
```
### interoception_state.json / presence_state.json [核]
```
{内感受/在场状态}
```

---

## P4 · 启动顺序与依赖

### cron_daemon 注册的 13 个任务（SCRIPTS dict）[核]
| 任务 | 间隔(s) | 输出 last.json | 说明 |
|---|---|---|---|
| interoceptive | 360 | cron_interoceptive_last | 体感环 |
| active_curiosity | 600 | cron_curiosity_last | 主动好奇 |
| dream_check | 720 | cron_dream_last | 梦境检查(scripts/) |
| liveness | 420 | cron_liveness_last | 存活检查 |
| metabolism | 900 | cron_metabolism_last | 代谢仪表盘 |
| surface_tension_decay | 300 | cron_decay_last | 张力回归(P0-5) |
| orb_state_writer | 360 | cron_orb_state_last | 色环RGB |
| render_layer_speak | 1800 | cron_render_layer_last | TTS播报 |
| hp4_heartbeat | 1800 | cron_hp4_heartbeat_last | HP4心跳 |
| skin_cycle | 3600 | cron_skin_cycle_last | 脱皮穿皮 |
| prune_guard | 300 | cron_prune_guard_last | 剪枝联动+热保护 |
| entropy_guard | 3600 | cron_entropy_guard_last | 茧房防御监控 |
| visual_world_model | 1800 | cron_visual_world_model_last | 视觉世界模型(parked) |

### 主循环（非 cron_daemon，Gateway 驱动）
- `consciousness_cycle.tick()`（E031）、`tu8_agent`（E033）、`tu8_dispatch`（E032）、`alignment_verify`（E007，出件前）—— 这些不在 cron_daemon，由对话/心跳触发。

### 依赖管理
- **【无显式依赖管理】**：cron_daemon 串行跑各脚本（单线程、subprocess timeout=90s），**不保证 A 在 B 前**。
- 隐式保证：靠**文件存在性**——如 E003 读 `surface_tension_state.json`，若 E002 未写出则 `_read_json` 返回 `{}` → `red=0, mode=neutral`（**不报错、读空/上一轮**）。
- 已知风险：surface_tension 原始 360s 任务[DISABLED 2026-07-17]（曾注入 FAKE anxiety 事件）；现由对话触发 + decay_tick(300s) 维持。若两者都停，orb 冻结于最后值。

---

## P5 · 失败模式（每引擎停 24h 的后果）

| 引擎 | 24h 停止后果 | 下游影响 | 用户可感症状 |
|---|---|---|---|
| E002 surface_tension | 张力不再更新 | E003/E004/E014 读旧值 | 色环冻结、语气不变 |
| E003 orb_state_writer | orb_state.json 陈旧 | 悬浮球 | 颜色/模式静止 |
| E007 alignment_verify | 出件不校验 | 钢印/仲裁失效 | 风险：越界输出无拦截 |
| E009 dream_consolidation | 不做梦境整合 | 记忆不代谢 | 长期：记忆漂移/噪声累积 |
| E014 cognitive_friction | 摩擦不 surfacing | HP1 盲 | 认知冲突不被注意 |
| E015 entropy_guard | 茧房防御离线 | 低频扫描空转 | 基本无感（本就仅监控） |
| E026 interoceptive | 无躯体信号 | E002 失锚 | 情感缺体感维度 |
| E031 consciousness_cycle | 主循环停 | 代谢/梦境/认知调度停 | 系统"睡着" |
| E032 tu8_dispatch | 分发停 | 所有任务卡 | 完全失能 |
| E073 metabolism | 代谢不报告 | 健康度盲区 | 无感（内部） |
| E096 spike_valley_detector | 尖刺谷不计算 | E002 历史缺 | 张力曲线变平 |
| E080 steel_env_annotation | 环境注释不累计 | 钢印进化不触发 | 无感 |
| E022/E024/E025 视觉 | 本就 parked | — | 无（numpy 缺） |
| E030 foraging | 本就不接生产 | — | 无 |

---

## P6 · 设计意图 vs 现状 diff（断环 / 隐式耦合 / 缺失）

| 编号 | 设计意图 | 代码现状 | 差距 | 优先级 |
|---|---|---|---|---|
| C008 | E007→E002 负反馈（joy↑/anxiety↓→张力回归） | 不存在 | 回路断开 | 高 |
| C021 | E015→tu8_dispatch 门控 | 仅 cron 监控 | 茧房防御空转 | 中 |
| — | 耦合权重可塑（Hebbian） | 全固定 | 未实现 | 低 |
| E001 | emotion_engine 为情感主引擎 | 不进运行时（orphan） | 60KB 浪费+双情感表示 | 高 |
| E022/24/25 | 视觉世界模型真帧 | numpy 缺→parked | 感知回路空壳 | 中 |
| E030 | F层觅食器官 | v1.5 架构定，未接生产 | 内在目的性缺失 | 中 |
| 4.5 | 全局引擎状态注册表 | 三套碎片(hook/friction/behavior) | 无统一注册表 | 高 |
| 4.3 | 同步 tick + 双缓冲 | 各 cron 独立轮询伪管道 | 无快照 | 高 |
| E017 | self_probe 锚点清理 | 文件未在 src/ 定位 | 落点不明 | 低 |
| E095→E080 | environment_detector 提供 env_change 信号 | E080 的 env_change 无来源 | 钢印进化触发缺信号源 | 中 |

---

## 交回 Qwen 时可做的下一步
1. **画完整有向图**（带传递函数标注）：C001-C023 已可画；E031-E100 待补边。
2. **找断环**：C008（E007→E002）、E001 orphan、视觉 parked。
3. **找隐式耦合**：C004（λ→orb 红写成 if）、C001（红通道权重埋在 orb 内）。
4. **重构路线图**：先接 E015→dispatch(C021) + 建统一注册表(4.5) + 同步 tick(4.3)；后消 E001 orphan + 补 C008 回边。
