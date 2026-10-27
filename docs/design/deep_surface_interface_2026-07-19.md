# deep_surface_interface.py — 产物记录

## 任务摘要
创建 `src/deep_surface_interface.py`，实现 TU-8 深层（拓扑计算层）与表层（渲染/语言层）之间的显式通信协议。

## 核心功能

### DeepSurfaceInterface 类
| 方法 | 功能 |
|------|------|
| `deep_to_surface(deep_output, context)` | 深层→表层：压缩+校验+渲染 |
| `surface_to_deep(surface_input)` | 表层→深层：解压+解析+注入 |
| `get_phase()` / `set_phase(phase, reason)` | 相态管理 |
| `get_bandwidth_status()` | 带宽状态查询 |
| `check_integrity(deep_data)` | 拓扑完整性校验 |
| `detect_surface_pollution(text)` | 表层语义污染检测 |
| `diagnose()` | 诊断信息 |

### 相态配置
| 相态 | 压缩比 | 允许原始输出 | 最大Token | 封阻输出 |
|------|--------|-------------|-----------|---------|
| NORMAL | 100:1 | 否 | 200 | 否 |
| SLEEP | 10:1 | 是 | 2000 | 否 |
| DREAM | 10:1 | 是 | 2000 | 否（含阻抗警告）|
| REVISION | 1:1 | 是 | 5000 | 否 |
| COLLAPSE | 0 | 否 | 0 | 是 |

### 校验机制
- **拓扑完整性**：`check_integrity()` 检查必需字段、张力范围、拓扑空值
- **保真度阈值**：fidelity < 0.3 → 拒绝传输
- **污染检测**：`detect_surface_pollution()` 检测清醒语义标签（如"麻绳""杀手"等）
- **崩溃态封阻**：COLLAPSE 相态禁止一切输出

### 集成
- 读取：`_agent_memory/surface_tension_state.json`
- 写入：`_agent_memory/interface_state.json`、`_agent_memory/interface_config.json`
- 调用：`topology_thermal_monitor.on_interface_event`（占位，未实现时静默跳过）

## 自测结果（8 项全部通过）
1. [PASS] 正常态 deep_to_surface（100:1 压缩，62:1 实际）
2. [PASS] 睡眠态 deep_to_surface（10:1 压缩）
3. [PASS] 续梦态跨相态传输（阻抗警告验证）
4. [PASS] surface_to_deep 污染检测（"麻绳""杀手"标签）
5. [PASS] 相态切换（REVISION 带宽配置）
6. [PASS] 崩溃态拒绝输出（BLOCKED 警告）
7. [PASS] 保真度不足拒绝传输（fidelity < 0.3）
8. [PASS] 带宽状态查询

## 文件位置
- 核心模块：`src/deep_surface_interface.py`
- 状态文件：`_agent_memory/interface_state.json`
- 配置文件：`_agent_memory/interface_config.json`
