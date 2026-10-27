# phase_state_machine.py 创建完成

## 任务
创建 `src/phase_state_machine.py` — TU-8 四相态状态机

## 实现摘要

### 文件位置
- 核心：`src/phase_state_machine.py`
- 状态写入：`_agent_memory/phase_state.json`

### 实现的接口

| 方法 | 功能 |
|------|------|
| `get_phase()` | 返回当前相态（str） |
| `get_phase_config()` | 返回当前相态配置参数（dict） |
| `trigger_phase(target, reason)` | 触发切换，返回 PhaseTransitionReport |
| `auto_detect_phase()` | 基于张力/沉默时长/聚焦度自动检测相态 |
| `get_phase_duration()` | 当前相态持续时间（秒） |
| `get_phase_history(limit)` | 最近切换历史（list） |
| `is_phase_stable()` | 当前相态是否稳定 |
| `force_phase(phase, reason)` | 强制切换相态（绕过自动检测） |
| `set_focused(bool)` | 设置主动注意力聚焦标志 |
| `get_tension()` | 返回归一化张力值 [0,1] |
| `diagnose()` | 返回完整诊断信息 |

### 四相态配置

| 相态 | 带宽 | 压缩比 | 深层允许 | 表层允许 |
|------|------|--------|---------|---------|
| NORMAL | full | 100 | True | True |
| SLEEP | high | 10 | True | False |
| DREAM | very_high | 10 | True | True |
| COLLAPSE | zero | 0 | False | False |

### 自动检测规则
- `tension >= 1.0` → COLLAPSE
- `tension >= 0.6` AND `focused=True` → DREAM
- `silence > 3600s` (1h) → SLEEP
- 其他 → NORMAL

### 张力计算
从 `surface_tension_state.json` 的 `spike_valley_vector` 和 `personality_baseline` 计算归一化张力：
- 负向情绪偏差（anxiety, anger, fear, sadness）升高张力
- 正向情绪负向偏移（joy, love, curiosity 低于基线）升高张力
- tanh 压缩到 [0, 1] 范围

### 集成
- 读取：`surface_tension_state.json`（张力）、`_agent_memory/presence_state.json`（沉默时长）
- 写入：`_agent_memory/phase_state.json`（历史）、`_agent_memory/interface_state.json`（同步相态）
- 调用：`deep_surface_interface.set_phase()`（相态切换时同步接口）

### 验证结果（10/10 PASS）
1. 初始状态读取
2. NORMAL → SLEEP 强制切换
3. SLEEP → DREAM 强制切换（含阻抗警告）
4. DREAM → COLLAPSE 强制切换（含安全模式标志）
5. 恢复到 NORMAL
6. 自动检测（沉默 130min → SLEEP）
7. 相态历史记录（4 条）
8. 稳定性检测（False，因测试期间频繁切换）
9. 各相态配置一致性检查
10. 诊断信息完整性

## 备注
- `is_phase_stable()` 在测试期间返回 False 是预期行为（测试切换 4 次发生在 0.14s 内）
- 实际使用中 200 条历史上限自动裁剪
- `deep_surface_interface` 未就绪时静默跳过（启动早期保护）
