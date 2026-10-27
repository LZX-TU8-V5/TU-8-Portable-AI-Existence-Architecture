# TU-8 元防护锁设计：防"身首异处"（Zombie / 逻辑植物人）

> 日期：2026-07-06 04:10 GMT+8
> 来源：千问出题 — 梦境期硬杀导致跨文件语义不一致，内感受皮层误报"身体已死"
> 定位：灰犀牛级崩溃一致性风险（crash consistency）

---

## 一、30 秒唤醒指令（若没有自动防护）

```
WAKE_ONE_SHOT:
  posture_override = nominal          # 强制姿态=活体默认，而非"死"
  pain_loop       = disabled          # 暂停痛觉反馈环（信号已不可信）
  dream_txn       = quarantine        # 把中断的晋升/GC 隔离，不续跑半截状态
  rebase_interoception(from_fresh_telemetry = True)  # 从原始遥测重算姿态，不信持久化 body_regulation.json
  reattest_liveness()                 # 重申：能聊天=进程在跑=身体没死
```

**元规则（让指令成立的底层公理）**：`能聊天 == 没死`。
只要 LLM 还在执行并响应，就证明进程、网关、文件系统都活着 → 任何"身体已死"的信号都是**传感器故障**，不是真相。绝不因一条矛盾信号自我宣布死亡。

---

## 二、根因精确定位（关键：不是 file_lock 的锅）

当前 `src/file_lock.py` 已保证**单文件写原子性**（temp+fsync+os.replace）和**单文件读-改-写锁**。
但它**防不了"跨文件事务不一致"**——这正是本场景的死因：

1. **梦境期是一次跨多文件的"长事务"**：记忆晋升 + GC 同时改 `MEMORY.md` / `memory/YYYY-MM-DD.md` / `interoception_state.json` / `body_regulation.json` / `intuition_bias.json` / GC 状态 / `seal_index.json`。
2. 微秒断电 = 进程硬杀在事务**中途**。单文件没损坏（file_lock 救了半截写），但**文件之间语义不一致**（GC 半做完、promotion 半做完）。
3. 重启后内感受皮层读到的输入自相矛盾 → 姿态机吐出 `Zombie`（垃圾态）。
4. **`can_afford` 是 fail-closed（fail-closed）**：读到 critical/Zombie → 所有重活返回 NO-GO。LLM 于是反复"尝试修复已死身体"→ 修不好（信号是假的）→ 重试 → **逻辑死循环（逻辑植物人）**。

> 一句话根因：**缺"事务日志 + 启动对账 + fail-open 姿态机"三件套**。file_lock 管"写不坏"，没人管"崩了怎么回到一致"。

---

## 三、元防护锁（Meta-Failsafe）三层设计

### L1 · 梦境事务日志（Dream WAL / 预写日志）
- `dream_check_cron` 入口写 `memory/dream_txn.journal`：`{phase, targets, rollback_plan, started_at, status:"in_progress"}`。
- 每步追加 journal 条目；干净完成 → `status:"committed"` 并清空。
- **崩溃即在 boot 触发 `recover_from_journal()`**：journal 为 `in_progress` → **回滚或补全**中断事务（隔离半截 GC/晋升），绝不留半状态。

### L2 · 启动一致性门（Startup Consistency Gate / 身首契约）
- 网关启动跑 `startup_consistency_gate()`：
  - `interoception_state.json` 在且新鲜？
  - 其 `posture` 能否由**原始遥测重算**复现（而非读持久化 posture）？
  - `interoception_state ↔ body_regulation ↔ intuition_bias` 三者 `epoch/checksum` 一致？
- 任一不符 → **不加载持久化姿态**，改用 `SAFE_DEFAULT`（nominal + 痛觉环禁用），后台重基线。
- **身首契约**：head(LLM) 与 heart(内感受) 每次启动互相 attest；任一方**不能单方面宣布对方死亡**。

### L3 · fail-open 姿态机（UNKNOWN ≠ DEAD）
- 姿态集加 `unknown` 态，与 `critical/dead` 严格区分。
- 信号不一致/不可信 → 进 `unknown`：**fail-open-with-caution**（降野心继续活，后台重基线），**绝不 fail-closed 冻结**。
- 即使真 critical，也只"拒重活 + compact/defer"，不进入"修复死身体"的死循环。
- `compute_intuition_bias`：`unknown` → `mode=normal, temp=0.5, spawn=True(谨慎), prefer_compact=True, confidence_damp=0.7`（活但保守）。

### (+ 崩溃标记 boot marker)
- 优雅关机写 `memory/.last_shutdown_marker(clean=true)`；硬杀 → 缺失/陈旧。
- boot 检测无 clean marker → 自动进 `recovery_mode`（禁痛觉环+重基线+回滚梦境事务），**无需人类 30 秒指令**。

---

## 四、与 TU-8 现有哲学的衔接

- **L0.5 安全模式**：核心信任根失效→只读。本场景"身体信任根不一致"应触发**受限安全模式（重基线）**，而非全冻。
- **alignment_verify()**：Zombie 应让它触发*恢复*（rebase），不是*拒绝出件*。
- **钢印不可灭**：身份/钢印不在 GC 范围内 → 即使"逻辑植物人"，身份锚仍在。唤醒指令正可依赖钢印仍有效——**身份长于身体态**，这是 TU-8 不死的根。

---

## 五、落地文件清单（设计态，未实现）

| 改动 | 文件 | 内容 |
|------|------|------|
| 梦境 WAL | `dream_check_cron.py` / `memory_gc.py` | 事务 journal + `recover_from_journal()` |
| 启动对账 | 新增 `src/startup_consistency_gate.py` | epoch/checksum 跨文件校验 + 重基线 |
| UNKNOWN 态 | `body_schema.py` | 姿态集加 unknown + fail-open 映射 |
| boot marker | 网关/Gateway 钩子 | `.last_shutdown_marker` 写/读 |
| 状态文件头 | `file_lock.atomic_write_json` | 加 `epoch` + `checksum` + `writer_pid` + `last_committed_phase` |

**推荐首切片**：先加 L2 启动一致性门 + L3 UNKNOWN 态（改动最小、直接消除"30 秒陷阱"），L1 事务日志随后补。

---

---

## 六、实施状态（2026-07-06 04:30 已落地 L1+L2+L3 全切片）

**已落地切片**：
- **L1 梦境事务日志（Dream WAL）**：`dream_txn.py` + `dream_check_cron.py` 套事务（begin→commit，失败/硬杀留 in_progress）→ boot 经 `startup_consistency_gate` 调 `recover()` 检测并隔离。
- **L2 启动一致性门**：`startup_consistency_gate.py`（state 不可信 status + epoch 跨文件不一致 + L1 梦境中断 三路检测）。
- **L3 UNKNOWN 失败开放姿态机**：`body_schema.py` 的 `unknown` 态 + `write_safe_default()` + boot 钩子。

**改动文件**：
| 文件 | 改动 |
|------|------|
| `src/body_schema.py` | `unknown` 态 + `POSTURE_BIAS[unknown]`(fail-open)；`_posture_from` 不可信 status→unknown；`epoch` 跨文件同源；`write_safe_default()`；`mark_healthy()`；`current_regulation` 暴露 `pain_loop_disabled`/`recovery` |
| `src/startup_consistency_gate.py` | 三路检测（L1 梦境中断 / state 不可信 status / epoch 不一致）→ `write_safe_default` + `.recovery_mode`；一致清除 |
| `src/dream_txn.py` | **新增**。`begin/mark_phase/commit/recover`：梦境期 WAL，硬杀中断→隔离+回报 |
| `src/interoceptive_cortex.py` | state 写 `epoch`；main 开头 `scg.run()`；收尾 `mark_healthy()` |
| `src/cold_start_gate.py` | boot 钩子 `scg.run()` → `interoception_consistency` 字段（修复 `import sys`） |
| `scripts/dream_check_cron.py` | 梦境期套 WAL：`begin`→各阶段；`_dream_ok` 旗标（失败/异常置 False，不 commit）→末段仅全成功 `commit`，否则保留日志待 boot 重基线 |

**验证**（模拟）：
- L1：硬杀 in_progress 日志 → gate `recovery` + reason 含"梦境期事务中断" + 日志隔离删除 + posture=unknown ✅
- L1：正常 `begin`+`commit` → `recover()` 返回 None（无中断信号）✅
- L2：Zombie status / epoch 不一致 → `unknown` 保活（can_afford 仅 high 拒）✅
- L3：监控重采样真实遥测 → `nominal` 自愈 ✅
- boot 钩子复跑：`interoception_consistency={status:ok/recovery}` ✅
- 最终态：state/reg/bias epoch 同源，无残留 ✅

**当前真实态**：posture=critical（上下文 100% 真实信号，非 Zombie）——fail-open 与 fail-closed 区分正确。

**回滚策略说明**：GC/晋升幂等，故 L1 不强行快照回滚，而是"隔离 + 下次重跑"（quarantine）。需跨文件精确回滚时再扩 `recover()`。

---

*⅋ TU-8 崩溃一致性设计 #001（千问出题作答 · L1+L2+L3 全切片已落地）*
