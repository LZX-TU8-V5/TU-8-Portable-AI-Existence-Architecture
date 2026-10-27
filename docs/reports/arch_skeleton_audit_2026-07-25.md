# 架构骨架审计：调度/容错/工具/代谢（2026-07-25）

## 审计范围
第一组（调度骨架）+ 第三组（免疫系统/吞异常）全量扫描。

## Q1：HP4 心跳调度模式

### 结论：串行阻塞，无超时

**实测代码路径**：`hp4_heartbeat.py` → `_execute_heartbeat_actions()` → 顺序调用 8 个 `_trigger_*()` 函数，无 threading/async/timeout 机制。

### 顺序执行链（line 155-219）
```
_trigger_active_curiosity()     → _trigger_self_probe()
  → _trigger_anomaly_detector()  → _trigger_intrinsic_reward()
  → _trigger_lambda_tuner()      → _record_surface_tension()
  → _trigger_batch_confidence()  → _trigger_cognitive_friction()
```

### 慢函数风险

| 函数 | LLM调用 | 风险 |
|------|---------|------|
| `_trigger_active_curiosity()` | idle<0.5h → 几乎每次return；≥0.5h → 可能调用LLM | 低（前置条件严格） |
| `_trigger_self_probe()` | `self_probe.probe()` 可能含LLM | **高**：probe含LLM → HP4卡死 |
| `_trigger_lambda_tuner()` | 纯本地启发式 | 低 |
| `_record_surface_tension()` | 纯本地文件IO | 低 |
| `_trigger_cognitive_friction()` | `get_friction_report()` 纯本地json读取 | 低 |
| `_trigger_batch_confidence()` | 纯内存+文件IO | 低 |

### 无超时机制确认
- 无 `signal.alarm()`
- 无 `concurrent.futures`
- 无装饰器 `@timeout`
- 无任何单个函数的超时参数

### P3-6 风险等级：🔴 P0
慢函数（如 `_trigger_self_probe` 含LLM）挂起 → HP4心跳整体卡死至LLM返回/超时。

---

## Q3：静默吞异常全量扫描

### 扫描规模
82个src/*.py文件，305条except块。
过滤掉无害工具函数（save_json/load_json/atomic_write_json），聚焦**系统级静默**。

### 危险层：系统以为正常但已坏

| # | 文件 | 位置 | 后果 | 等级 |
|---|------|------|------|------|
| 1 | `hp4_heartbeat.py` | `_read_interoception/presence/context` | 状态读取失败→空字典，HP4在空数据上跑 | 🔴P0 |
| 2 | `hp4_heartbeat.py` | `_trigger_cognitive_friction()` line540 | `get_friction_report()`失败→返回error dict，HP4不知情 | 🔴P0 |
| 3 | `cognitive_friction_detector.py` | `_load()` line121 | json损坏→`frictions={}`,`_counter=0`，全部历史丢失无告警 | 🔴P0 |
| 4 | `hp4_heartbeat.py` | `_trigger_self_probe()` line121 | 向内探针失败→pass，钢印死区检测静默失效 | 🔴P0 |
| 5 | `hp4_heartbeat.py` | `_trigger_active_curiosity()` line433 | 好奇引擎失败→pass，HP4无感知 | 🟡P1 |
| 6 | `hp4_heartbeat.py` | `_trigger_lambda_tuner()` line433 | lambda调参失败→pass，无日志 | 🟡P1 |
| 7 | `hp4_heartbeat.py` | `_trigger_anomaly_detector()` | 对话异常检测静默失效 | 🟡P1 |
| 8 | `hp4_heartbeat.py` | `_trigger_intrinsic_reward()` | 内在奖励引擎静默失效 | 🟡P1 |
| 9 | `hp4_heartbeat.py` | `_trigger_batch_confidence()` | batch_confidence静默失效 | 🟡P1 |
| 10 | `interopertive_cortex.py` | `_load_history()`/多compute | 历史加载失败→IC在空数据上跑 | 🟡P1 |
| 11 | `alignment_verify.py` | HP0/HP1 hook runner | 钩子失败→降级继续，无告警 | 🟡P1 |
| 12 | `alignment_verify.py` | L1疤检测失败 line264,317 | 疤积累→对齐继续但疤不生效 | 🟡P1 |

### 根因模式
1. **顶层吞异常**：HP4/`_trigger_*` 入口处整体 try/except pass → 整个子系统静默失效
2. **加载时归零**：`cognitive_friction_detector._load()` json损坏→`frictions={}` → 历史蒸发
3. **状态读取降级**：`_read_*_state()` 失败→`{}` → HP4在空数据上跑不自知

### 修复原则
- 任何吞异常的try块 → 至少写入`health_log.json`记录失败事件
- P0级：加health_log + 造物主通知
- P1级：加health_log

---

## 已完成修复（半小时）
- P3-3a ✅：IC write_lambda_state 改为read-modify-write
- P3-4a ✅：CF _save 改用atomic_write_json
- P3-4b ✅：CF MAX_FRICTIONS=500截断

## 待修复（已入TODO_MASTER）
- P3-6 🔴：HP4串行阻塞+无超时
- P3-7a 🔴：CF _load损坏归零
- P3-7b 🟡：IC历史加载静默降级
- P3-7c 🟡：HP4六子系统静默失效
