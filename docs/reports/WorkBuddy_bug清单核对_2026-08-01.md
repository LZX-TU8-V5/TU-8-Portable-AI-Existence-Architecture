# 核对：WorkBuddy TU-8 bug 清单（Fix1-19 + overview E022/E024/E027/E029）

核对方式：对 `D:\工作文件\桌面\workbuddy\2026-08-01-14-43-57\tu8_fixes\TU-8_bug_fix_plan.md` 与 overview 所列 bug，逐一用真实源码直接读取行号确认（非信任 grep，因反斜杠被 PowerShell 翻倍会导致漏报）。

## 结论
**WorkBuddy 列出的 bug 全部属实（逐个源码确认）。但清单不完整，且 Fix3 有缺漏、overview 有一处错误陈述。**

## 一、已确认正确的声明（全部命中）
| 项 | 文件:行 | 内容 | 严重度 |
|---|---|---|---|
| Fix1 | quantized_memory.py:42 | `WORKSPACE=Path(r"D:\qq366410837\.qclaw\workspace")` | 高 |
| Fix3 | steel_seal_verifier.py:37 | `L5_FILE=r"D:\tu8-v5\TU-8\L5_钢印.md"` | 高 |
| Fix5 | neural_reflex.py:43-46 | 4 个 security 文件 D:\ 硬编码 | 高 |
| Fix6 | neural_reflex.py:545 | `QCLOW_WORKSPACE` 变量名拼错 | 高 |
| Fix7 | sag_lite_knowledge_graph.py:1271 | D:\ 硬编码 | 低(仅CLI默认) |
| Fix9 | confidence_decay_engine.py:40 | D:\ 硬编码 | 高 |
| Fix10a | cold_start_engine.py:74 | `WORKSPACE_D=D:\...` | 高 |
| Fix10b | cold_start_engine.py:76 | `WORKSPACE_C=C:\...\openclaw\workspace`（.openclaw 笔误） | 高 |
| Fix10c | cold_start_engine.py:93 | `LAPTOP-HJPFSOKP` 主机名写死 | 中 |
| Fix11 | audit_engine.py:404 | D:\ 硬编码 | 低 |
| Fix13 | error_router.py:127 | D:\ 硬编码 | 高 |
| Fix14 | cross_phase_channel/deep_surface_interface/dream_topology_engine/phase_state_machine | `QWCLAW_WORKSPACE` 拼错(4文件) | 中 |
| Fix16 | verify_password.py:13 | D:\ 硬编码 | 高 |
| Fix17 | reflection_module.py:42 | D:\ 硬编码 | 高 |
| Fix2 | consciousness_cycle.py:2163 | `LAPTOP-HJPFSOKP` 写死 | 中 |
| Fix18/19 | 34 处 `C:/Users/...` 正斜杠硬编 | 一致性隐患 | 低 |
| Fix8/E024 | memory_dedup.py:280 | `_character_trigrams` 实为 unigram(`[i:i+1]`)，docstring 自承 | 非功能 |
| E022 | tu8_memory.py:1507-1513 | `_load_long_term()` 仅 `pass` 空操作 | 高(长期记忆未载入) |
| E027 | memory_degradation.py | 独立 `should_degrade()`/`compute_next_fidelity_level()` 与 tu8_memory.FidelityManager 6级降级重复（0 处 class 同名，是函数级重复） | 中 |
| E029 | steel_seal_verifier.py:106/115/122 | 钢印阈值 `>=0.3` 三处 | 设计偏松 |

## 二、WorkBuddy 的 3 处问题（需修正/补足）

### 2.1 Fix3 不完整 + overview 错误陈述
- `steel_seal_verifier.py` 的 D:\ 硬编码实际在 **:36(SOUL_FILE) / :37(L5_FILE) / :38(MEMORY_FILE)** 三行。
- Fix3 只修 :37(L5_FILE)，**漏了 :36/:38**。
- overview(E029 段)称"SOUL_FILE/MEMORY_FILE 已正确指向 B"——**错误**，这俩也是 D:\ 硬编码。

### 2.2 D:\ 路径漂移严重漏报
- WorkBuddy 声称抓到 D:\ 相关 15 处（Fix1/3/5/6/7/9/10a/11/13/16/17）。
- **真实源码全量扫描 = 28 文件 / 32 处 D:\ 硬编码**，WorkBuddy 漏 ~17 文件，包括：
  - `environment_detector.py:37-40`（4 条 security 路径，与 Fix5 同一模式，高危却未列）
  - `cognitive_readiness.py:43` / `micro_sleep.py:45` / `naming_module.py:45`（均 `WORKSPACE_D=D:\`）
  - `divine_branch_interceptor.py:41` / `version_cooldown.py:41` / `upgrade_mode.py:5` / `scan_existing_sanitized.py:18` / `migrate_kg_db.py:6`
  - `add_efhv_event.py:13,16` / `add_efhv_event_simple.py:12,54` / `fact_correction_scar.py:39`
  - `tu8_dispatch.py:1108`（CLI 默认 `--workspace D:\...`，漏列）
- `apply_tu8_fixes.py` 仅覆盖所列 ~15 处，跑完仍留 ~17 处 D:\。

### 2.3 C:/ 正斜杠数量
- 真实扫描 34 处 `C:/Users/qq366410837/.qclaw/workspace`（含 Fix18 的 8 件 + Fix19 的 9 件 + 其余 ~17 件）。WorkBuddy 说"剩 ~27 件待补"——量级接近，基本一致。

## 三、风险分级（本机 workspace 已迁 C:，D:\ 不存在 → 命中即 FileNotFound）
- **活跃路径高危**（建议优先）：neural_reflex(安全层4文件+QCLOW)、cold_start_engine、steel_seal_verifier、verify_password、reflection_module、quantized_memory、confidence_decay、error_router。
- **独立脚本/孤儿件**（低优先）：environment_detector、cognitive_readiness、micro_sleep、naming_module、divine_branch_interceptor、version_cooldown、upgrade_mode、scan_existing_sanitized、migrate_kg_db、add_efhv_event*、tu8_dispatch(仅默认)、sag_lite(仅CLI)、audit_engine(仅CLI)、fact_correction_scar(事实记录串，可能故意)。

## 四、建议
- `apply_tu8_fixes.py` 的 token 替换 + DRY_RUN 思路正确，但需**扩充 old/new 清单至全部 28 文件**，否则修一半留一半。
- 改法统一：`os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace")`。
- 是否执行批量修复需造物主授权（触及 28 文件写操作）。
