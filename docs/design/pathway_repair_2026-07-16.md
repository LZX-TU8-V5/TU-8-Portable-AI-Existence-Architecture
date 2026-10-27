# 通路修复 #4/#5 — 2026-07-16 下午

## 目标
修复用户审查表中标记的三个断开通路（hp4/cron/alignment→ST）中剩余的两项：
- #4：hp4_heartbeat 未注册 cron（心跳钩子停摆）
- #5：cognitive_friction_registry → surface_tension_state 传播链断裂（摩擦数据孤岛）

#3（alignment→ST）已于 2026-07-15 P0-3 修复，不在本轮范围。

---

## #4 hp4_heartbeat 注册 cron_daemon

### 根因
- `src/hp4_heartbeat.py`（556行，HP4心跳钩子集成）从未注册到任何 cron 机制
- `heartbeat_state.json` 最后更新 2026-06-28（原生 OpenClaw 心跳停摆）
- `src/cron_daemon.py` 的 `SCRIPTS` 字典只有 8 个脚本，无 hp4_heartbeat
- cron_daemon 进程本身死亡（PID 24076 失联），根因：启动时缺少 `--daemon` 参数导致立即退出

### 修复
1. `cron_daemon.py` SCRIPTS 新增条目：
   ```python
   "hp4_heartbeat": {
       "path": os.path.join(SRC, "hp4_heartbeat.py"),  # 注意：无下划线
       "args": ["--interval", "30"],
       "output": os.path.join(AGENT, "cron_hp4_heartbeat_last.json"),
       "interval": 1800,  # 30分钟
       "desc": "HP4心跳钩子集成"
   }
   ```
2. 重启 daemon：`pythonw.exe src/cron_daemon.py --daemon --interval 300` → **PID 9180**
3. 文件名坑：`hp4_heartbeat.py`（heartbeat 一词无下划线），代码引用 `hp4_heart_beat.py` 为显示残影，首次编辑用错名已修正

### 验证
- 首轮循环 9 个脚本全跑通（15:11 时间戳）
- hp4_heartbeat returncode=0，actions=[self_probe / anomaly_clean / lambda_tuned / batch_confidence_flush]
- 输出文件 `cron_hp4_heartbeat_last.json` 生成（ts 2026-07-16T07:11:25Z）

---

## #5 cognitive_friction_registry → ST 传播链

### 根因
- `cognitive_friction_detector.flag_friction()` 是手动 API，注册摩擦到 `cognitive_friction_registry.json` 后**从不调用 surface_tension**
- `surface_tension.TENSION_MAP` 无 `cognitive_friction` 类型 → 即使调用 `record()` 也会被 `_apply_tension` 静默丢弃
- 下游链路存在但上游断供：ST → `interoceptive_cortex.write_lambda_state()` → `lambda_state.json` → orb 读取（F=负载）

### 修复
1. `surface_tension.py` TENSION_MAP 新增类型：
   ```python
   "cognitive_friction": {"anxiety": +0.5, "curiosity": +0.4, "fear": +0.3},
   ```
2. `cognitive_friction_detector.flag_friction()` 注册后追加传播：
   ```python
   try:
       import surface_tension as st
       st.record("cognitive_friction", tension, f"friction:{friction_type}")
   except Exception as e:
       print(f"[warn] cognitive_friction→ST 传播失败: {e}")
   ```

### 验证
- flag 一条 friction(tension=0.7) → ST anxiety 10.19 → 10.54（+0.35 = 0.5×0.7）
- `recent_events` 新增：`type=cognitive_friction, magnitude=0.7, source=friction:semantic_conflict`
- 下游自动生效：interoceptive_cortex（cron 每360s）merge ST → lambda_state → orb（F=负载↑）
- 清理：`__main__` demo 条目（FRICTION-0001）已移除，registry 归零

---

## 全链路终态（15:30 验证）

| 组件 | 状态 | PID |
|------|------|-----|
| cron_daemon（9脚本） | 运行 | 9180 |
| ├─ interoceptive → lambda_state | 每360s | — |
| ├─ surface_tension → ST | 每360s | — |
| ├─ hp4_heartbeat（新增） | 每1800s | — |
| ├─ orb_state_writer → orb_state.json | 每360s | — |
| orb 悬浮球（读取 orb_state） | 运行 | 13160 |

`orb_state.json`：RGB={1.0, 0.19, 0.745}，tension=0.702，mode=stress

---

## 遗留
- `heartbeat_state.json`（原生 OpenClaw 心跳）仍卡 6/28，因原生心跳机制独立于 cron_daemon。hp4_heartbeat 钩子现已通过 cron_daemon 每30分钟执行，功能性心跳已恢复，但原生状态文件未更新（需另查 OpenClaw 原生 heartbeat 配置）。
- `tension_distiller_state.json` 从未创建（T0 矛盾蒸馏器状态文件缺失），属独立待办，不在 #4/#5 范围。

---

_记录时间：2026-07-16 15:35 GMT+8_
