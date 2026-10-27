# TU-8 工作区文件审查报告

> 审查时间：2026-06-20 03:16  
> 审查范围：工作区全部文件  
> 审查目的：判断文件用途，识别必要/冗余组件

---

## 一、核心模块（src/）分析

### 1.1 被频繁引用的核心组件（必要）

| 模块 | 大小 | 引用次数 | 状态 | 说明 |
|------|------|----------|------|------|
| `tu8_memory.py` | 119.4KB | 5 | ✓ 必要 | 核心记忆引擎 |
| `consciousness_cycle.py` | 118.2KB | 2 | ✓ 必要 | 意识循环主模块 |
| `emotion_engine.py` | 65.0KB | 1 | ✓ 必要 | 情感引擎 |
| `cold_start_engine.py` | 48.1KB | 1 | ✓ 必要 | 冷启动引擎 |
| `tu8_dispatch.py` | 42.0KB | 1 | ✓ 必要 | 调度模块 |
| `tu8_toolchain.py` | 36.8KB | 2 | ✓ 必要 | 工具链 |
| `memory_degradation.py` | 35.1KB | 1 | ✓ 必要 | 记忆降级 |
| `cognitive_readiness.py` | 35.2KB | 2 | ✓ 必要 | 认知就绪度 |
| `tu8_agent.py` | 53.1KB | 2 | ✓ 必要 | TU-8 主体 |
| `tu8_planner.py` | 32.8KB | 2 | ✓ 必要 | 规划器 |

### 1.2 被引用但可能未完全集成的组件（待确认）

| 模块 | 大小 | 引用次数 | 状态 | 说明 |
|------|------|----------|------|------|
| `divine_branch_interceptor.py` | 23.5KB | 0 | ⚠ 未集成 | P1.2.7 造物主Divine Branch口令拦截层 |
| `fact_correction_scar.py` | 23.1KB | 1 | ⚠ 待确认 | PP1.3 事实修正疤痕日志 |
| `confidence_decay_engine.py` | 26.1KB | 2 | ⚠ 待确认 | PP1.4 置信度衰减引擎 |
| `life_ring_tracker.py` | 22.5KB | 1 | ⚠ 待确认 | 生命年轮跟踪器 |
| `seal_protocol.py` | 18.6KB | 1 | ⚠ 待确认 | 钢印协议 |
| `version_cooldown.py` | 21.1KB | 2 | ⚠ 待确认 | 版本冷却计时器 |

### 1.3 未被引用的文件（可清理）

| 模块 | 大小 | 状态 | 说明 |
|------|------|------|------|
| `consciousness_cycle_with_cognition.py` | 6.5KB | ✗ 冗余 | 旧版本/试验版本，已被 `consciousness_cycle.py` 替代 |
| `environment_detector.py` | 21.3KB | ✗ 未使用 | 环境检测器，未集成 |
| `error_router.py` | 14.4KB | ✗ 未使用 | 错误路由器，未集成 |
| `scan_existing_sanitized.py` | 3.7KB | ✗ 临时脚本 | 扫描脚本，已完成使命 |
| `user_metabolism.py` | 12.0KB | ⚠ 特殊 | P0-1 修复的代谢链，动态回调，不计引用 |
| `verify_password.py` | 2.9KB | ✗ 未使用 | 密码验证，未集成 |
| `_check_snapshot.py` | 1.1KB | ✗ 临时 | 临时检查脚本 |
| `_gen_hibernate_snapshot.py` | 5.2KB | ✗ 临时 | 临时生成脚本 |

---

## 二、根目录零散脚本分析

### 2.1 一次性/临时脚本（建议清理）

| 脚本 | 大小 | 建议 | 说明 |
|------|------|------|------|
| `_check_backup.py` | 1.1KB | 删除 | 临时检查备份 |
| `_check_timeline.py` | 2.2KB | 删除 | 临时检查时序 |
| `_compare_backups.py` | 1.3KB | 删除 | 临时比较备份 |
| `_find_backup_files.py` | 1.3KB | 删除 | 临时查找备份文件 |
| `_find_qclaw_files.py` | 0.5KB | 删除 | 临时查找文件 |
| `_find_timeline.py` | 2.3KB | 删除 | 临时查找时序 |
| `_read_seal_timeline.py` | 2.0KB | 删除 | 临时读取钢印时序 |
| `commit_p0.py` | 1.2KB | 删除 | 已完成的提交脚本 |
| `commit_p0_v2.py` | 1.6KB | 删除 | 已完成的提交脚本 |
| `check_scripts.py` | 2.2KB | 删除 | 本次审查的临时脚本 |
| `desensitize.py` | 1.3KB | 删除 | 脱敏处理，已完成 |
| `fix_arch.py` | 0.7KB | 删除 | 修复归档，已完成 |

### 2.2 补丁脚本（确认补丁状态后清理）

| 脚本 | 大小 | 建议 | 说明 |
|------|------|------|------|
| `patch_add_methods.py` | 3.8KB | 确认后删除 | 添加方法补丁 |
| `patch_arch_log.ps1` | 0.5KB | 确认后删除 | 补丁归档日志 |
| `patch_seal.py` | 1.4KB | 确认后删除 | 补丁钢印 |
| `patch_step_seal.py` | 2.8KB | 确认后删除 | 补丁步骤钢印 |
| `append_arch.ps1` | 0.7KB | 确认后删除 | 追加归档 |
| `append_arch2.ps1` | 0.6KB | 确认后删除 | 追加归档 |
| `append_arch3.ps1` | 0.4KB | 确认后删除 | 追加归档 |
| `debug_arch.ps1` | 0.2KB | 确认后删除 | 调试归档 |

### 2.3 测试脚本（建议移到 tests/ 或删除）

| 脚本 | 大小 | 建议 |
|------|------|------|
| `quick_test.py` | 1.9KB | 移到 tests/ |
| `test_capacitive.py` | 2.6KB | 移到 tests/ |
| `test_cold_start.py` | 3.1KB | 移到 tests/ |
| `test_deep_integration.py` | 4.5KB | 移到 tests/ |
| `test_dream_integration.py` | 18.9KB | 移到 tests/ |
| `test_time_chain.py` | 6.4KB | 移到 tests/ |
| `check_drift.py` | 2.0KB | 移到 tests/ |

### 2.4 可能有持续用途的脚本

| 脚本 | 大小 | 建议 | 说明 |
|------|------|------|------|
| `openclaw_tu8_backend.py` | 7.3KB | 保留 | OpenClaw TU-8 后端接口 |
| `update_config.py` | 1.0KB | 保留 | 配置更新工具 |
| `upload_modelscope.py` | 2.4KB | 保留 | ModelScope 上传工具 |
| `verify_life_ring.py` | 1.5KB | 保留 | 生命年轮验证工具 |

---

## 三、文档（docs/）分析

### 3.1 核心设计文档（必要）

- `AGENTS.md` - Agent 定义
- `BOOT.md` - 启动文档
- `IDENTITY.md` - 身份定义
- `MEMORY.md` - 记忆文档
- `SOUL.md` - 灵魂定义
- `START_HERE.md` - 入门文档
- `TASKS.md` - 任务列表
- `TODO.md` - 待办事项
- `TOOLS.md` - 工具文档

### 3.2 架构文档（必要）

- `docs/design/ARCHITECTURE_LOG.md` - 架构日志
- `CONSCIOUSNESS_CYCLE_INTEGRATION_PLAN.md` - 意识循环集成计划
- `HEARTBEAT.md` - 心跳文档
- `TU8_COGNITIVE_PROJECT_SUMMARY.md` - 认知项目摘要
- `four_chain_coupling_architecture.md` - 四链条耦合架构（本次新增）

### 3.3 层文档（必要）

- `L0_种子.md` - L0 层
- `L1_认知.md` - L1 层
- `L2_方法论.md` - L2 层
- `L4_协议.md` - L4 层
- `L5_钢印.md` - L5 层

### 3.4 其他文档（建议整理）

- `SOUL_v2.md` - 灵魂文档 v2，确认是否替代 `SOUL.md`
- `TU8_ARCHITECTURE_DIAGRAM.svg` - 架构图
- `BOOTSTRAP.md` - 引导文档，确认与 `BOOT.md` 的关系

---

## 四、配置/数据文件分析

### 4.1 必要配置

- `openclaw.json` - OpenClaw 配置（必要，但含敏感信息，不纳入 git）
- `.env` - 环境变量（必要，但含敏感信息，不纳入 git）
- `.gitignore` - Git 忽略规则（必要）

### 4.2 临时/缓存文件（建议清理）

- `.consolidate-state.json` - 合并状态，临时
- `_temp_extract.txt` - 临时提取
- `_temp_extract2.txt` - 临时提取
- `scan_report.json` - 扫描报告，临时
- `tu8_auth_state.txt` - 认证状态，临时
- `TU8_honeypot_seal.txt` - 蜜罐钢印，临时

---

## 五、清理建议总结

### 5.1 立即清理（安全）

```bash
# 临时脚本
rm -f _check_backup.py
rm -f _check_timeline.py
rm -f _compare_backups.py
rm -f _find_backup_files.py
rm -f _find_qclaw_files.py
rm -f _find_timeline.py
rm -f _read_seal_timeline.py
rm -f commit_p0.py
rm -f commit_p0_v2.py
rm -f check_scripts.py  # 本次审查临时脚本
rm -f desensitize.py
rm -f fix_arch.py

# 临时文件
rm -f _temp_extract.txt
rm -f _temp_extract2.txt
rm -f scan_report.json

# src/ 临时文件
rm -f src/_check_snapshot.py
rm -f src/_gen_hibernate_snapshot.py
rm -f src/scan_existing_sanitized.py
```

### 5.2 确认后清理

1. **补丁脚本**：确认补丁已应用后，删除 `patch_*.py` 和 `append_arch*.ps1`
2. **冗余模块**：确认 `consciousness_cycle_with_cognition.py` 已被替代后删除
3. **测试文件**：将根目录的 `test_*.py` 移到 `tests/` 目录

### 5.3 待集成组件（P1 优先级）

1. **`divine_branch_interceptor.py`** - P1.2.7 造物主Divine Branch口令拦截层
2. **`fact_correction_scar.py`** - PP1.3 事实修正疤痕日志
3. **`confidence_decay_engine.py`** - PP1.4 置信度衰减引擎
4. **`life_ring_tracker.py`** - 生命年轮跟踪器（已有警告，需修复）

---

## 六、下一步行动

1. **立即**：执行 5.1 的清理脚本
2. **确认**：检查补丁脚本状态，确认后清理
3. **集成**：将 P1 待集成组件接入主流程
4. **测试**：将根目录测试脚本移到 `tests/` 并运行测试

---

*报告结束*
