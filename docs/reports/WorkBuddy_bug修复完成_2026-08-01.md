# WorkBuddy bug 清单修复完成（2026-08-01）

授权：用户「备份再处理」。策略：先备份 `backup/*.v1.py`，再做**纯字符串替换**（不改动结构、不注入 import 除 fact_correction_scar 外、零语法风险）。

## 修复统计
- **29 个文件**已修复并备份（`backup/<name>.v1.py`，tu8_toolchain 为 `.v1`/续号）。
- 全部 `py_compile` 通过。

## 替换类型与命中
| 类型 | 内容 | 命中文件 |
|---|---|---|
| A. D:\→C: 基准路径 | `D:\qq366410837\.qclaw\workspace` → `C:\Users\qq366410837\.qclaw\workspace` | 25 文件（含 steel_seal :36/:38 补全 Fix3、neural_reflex 安全层4路径、cold_start WORKSPACE_D、environment_detector 4路径等） |
| B. A副本引用 | `D:\tu8-v5\TU-8` → `C:...\.qclaw\workspace` | steel_seal:37 + tu8_agent:1166(Fix4) |
| C. .openclaw 笔误 | `.openclaw\workspace` → `.qclaw\workspace` | cold_start:76 + naming_module + tu8_toolchain:846(正斜杠变体，WorkBuddy 漏列) |
| D. QCLOW 变量名 | `QCLOW_WORKSPACE` → `QCLAW_WORKSPACE` | neural_reflex:545 |
| E. QWCLAW 变量名 | `QWCLAW_WORKSPACE` → `QCLAW_WORKSPACE` | cross_phase_channel/deep_surface_interface/dream_topology_engine/phase_state_machine (4文件) |
| F. 双反斜杠变体 | `D:\\qq366410837\\.qclaw\\workspace` → `C:\\...` | tu8_dispatch:1108(源码双反斜杠，批量漏匹配，单独补) |
| G. fact 赋值 | :39 包 `os.environ.get("QCLAW_WORKSPACE", ...)` + 补 `import os` | fact_correction_scar.py |

## 未处理（需用户拍板）
- **主机名写死 `LAPTOP-HJPFSOKP`**（Fix2 consciousness_cycle:2163 / Fix10c cold_start:93）：消除误降级 vs 锁机语义分叉，未自动改。
- **fact_correction_scar.py:529/569/570**：事实记录串（用户曾称 workspace 在 D:），属历史记录非路径赋值，有意保留。

## 相对 WorkBuddy 原始清单的补充修正
1. Fix3 不完整 → 本次补全 steel_seal :36/:38（原 overview 误称"已正确指向 B"）。
2. D:\ 原清单列 ~11 处，实际 28 文件/32 处 → 本次全修。
3. 额外发现并修复 tu8_toolchain:846 的 `.openclaw` 笔误（WorkBuddy 漏列）。

## 验证
- 残留扫描：`.openclaw`=0、`QCLOW/QWCLAW`=0、活跃路径 `D:\qq366410837` 与 `D:\tu8-v5`=0（仅 fact_correction_scar 历史记录串保留）。
- 29 文件 py_compile 全过。

## 备注
- 多数采用 D:\→C: 硬编（与既有 34 处 `C:/Users/...` 一致性，低风险）。若需可移植（env var 统一），可后续对活跃路径文件加 `os.environ.get("QCLAW_WORKSPACE", ...)` 包装，但非必需。
- 临时修复脚本已清理（`_fix_dpath.py` / `_fix_dpath2.py`）。
