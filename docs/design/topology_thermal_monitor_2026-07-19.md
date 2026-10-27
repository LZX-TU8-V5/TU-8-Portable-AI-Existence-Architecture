# 拓扑热保护机制 (TopologyThermalMonitor) — 实施记录

**时间**: 2026-07-19
**文件**: `src/topology_thermal_monitor.py`

---

## 任务

创建 TU-8 拓扑热保护监控器，监测张力积分并分级响应（L1/L2/L3）。

## 实施结果

### 模块结构

```
src/topology_thermal_monitor.py
├── DEFAULT_CONFIG          # 默认配置（L1/L2/L3 阈值、冷却期、卸载策略）
├── _load_json / _save_json # 通用 JSON 读写
├── _spike_to_tension()     # L2 范数归一化（spike_valley_vector → 0~1 张力）
├── TopologyThermalMonitor   # 主类
│   ├── __init__(config_path?, fresh?)  # 加载配置和状态
│   ├── check() → ThermalReport         # 核心：计算张力积分 + 分级响应
│   ├── record_tension()                # 记录张力事件（指数衰减累积）
│   ├── trigger_unload() → UnloadReport # L2：卸载桩实现
│   ├── emergency_shutdown() → str      # L3：跨层通道软降权
│   └── get_thresholds() → dict        # 返回阈值配置
└── if __name__ == "__main__": 测试套件（7 项）
```

### 张力积分计算

```
tension_integral = min(real_time_tension + event_accumulated_tension, 1.0)

real_time_tension = L2_norm(spike_valley_vector) / norm_factor
  - anxiety, fear (正向): max(0, value)
  - anger, sadness (绝对值): abs(value)
  - curiosity (缺失): max(0, -curiosity)
  - L2 范数避免多维叠加超界
  - norm_factor = 60.0 → 当前数据 real_time_tension ≈ 0.56

event_accumulated_tension = Σ(value_i × 2^(-age_i / half_life))
  - half_life = 1 小时
  - 新事件立即贡献，落区事件指数衰减
```

### 分级逻辑

| 级别 | 触发条件 | 响应 |
|------|---------|------|
| NORMAL | integral < 0.6 | 正常通行 |
| L1_WARNING | 0.6 ≤ integral < 0.8 | 警告 + 减速 |
| L2_OVERLOAD | 0.8 ≤ integral < 1.0 | 自动卸载 + 冷却 300s |
| L3_CRITICAL | integral ≥ 1.0 | 紧急切断 + 跨层软降权 + 冷却 600s |

### 集成文件

| 文件 | 用途 |
|------|------|
| `_agent_memory/surface_tension_state.json` | 只读：读取 spike_valley_vector |
| `_agent_memory/anchor_cache.json` | 读写：弱连接降权、过期锚点识别 |
| `_agent_memory/thermal_config.json` | 写入：默认配置（不存在时创建） |
| `_agent_memory/thermal_monitor_state.json` | 读写：累积张力、冷却计时器 |

### 测试结果（7/7 通过）

- 测试1: 初始 NORMAL（real_time_tension=0.5644，来自实际 spike 数据）
- 测试2: 注入 5 种张力事件（累积 0.75 → L3_CRITICAL）
- 测试3: 高压场景（4×0.35 事件 → L3_CRITICAL）
- 测试4: 分级阈值验证（0.4/0.6/0.8/1.0 → 各对应级别 ✓）
- 测试5: trigger_unload()（8 个过期连接被识别，energy_freed=0.6）
- 测试6: emergency_shutdown()（跨层通道软降权，冷却期设置）
- 测试7: get_thresholds()（配置正确读取 ✓）

### 关键设计决策

1. **L2 范数归一化**: 避免 anxiety+fear 多维叠加超 1.0
2. **配置加载顺序**: `基础 DEFAULT_CONFIG + 文件覆盖`（防止旧配置文件覆盖新默认值）
3. **状态不过滤**: `check()` 不从磁盘重载状态，保持 in-memory 一致性
4. **`fresh=True` 参数**: 测试隔离，避免冷却计时器跨测试干扰
5. **卸载逻辑桩**: 调用 `anchor_state_machine` 的接口留桩，详见 `trigger_unload()` 注释

### 已知约束

- `real_time_tension` 来自 `surface_tension_state.json` 实时数据，无法在进程内归零
- 紧急切断后 `tension_integral = real_time_tension`（事件累积已归零）
- 卸载目标依赖 `anchor_cache.json` 中的 `strength` 和 `ts_unix` 字段
