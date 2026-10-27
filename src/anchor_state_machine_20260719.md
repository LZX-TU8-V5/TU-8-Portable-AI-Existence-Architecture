# anchor_state_machine.py 实现总结

**时间**: 2026-07-19 10:06 GMT+8  
**文件**: `src/anchor_state_machine.py`  
**状态**: ✅ 全部验证测试通过

---

## 实现内容

### 四状态机
| 状态 | 能量衰减率 | 特性 | 允许转换来源 |
|------|-----------|------|------------|
| ACTIVATED | 0 (已加固) | 可调用,已索引 | (注册入口) |
| HIBERNATED | 10%/次 | 可调用,慢索引 | ACTIVATED |
| UNLOADED | 0 (暂停) | 不可调用 | HIBERNATED / ACTIVATED |
| CONSOLIDATED | 0 | 可调用,低资源,已整合 | UNLOADED (桩实现) |

### 状态转换规则
```
ACTIVATED ←→ HIBERNATED
    ↓               ↓
UNLOADED → CONSOLIDATED (桩实现)
         ↑ UNLOADED/CONSOLIDATED 不可直接激活
```

### 核心方法
| 方法 | 功能 |
|------|------|
| `register_anchor()` | 注册新锚点，自动进入ACTIVATED |
| `activate_anchor()` | HIBERNATED→ACTIVATED，UNLOADED/CONSOLIDATED抛出异常 |
| `hibernate_anchor()` | ACTIVATED→HIBERNATED，带reason |
| `unload_anchor()` | 主动卸载，energy暂停衰减 |
| `consolidate_anchor()` | UNLOADED→CONSOLIDATED（桩实现） |
| `apply_decay()` | 遗忘衰减：HIBERNATED按衰减率降能；能量<0.1自动卸载；未加固ACTIVATED轻微衰减 |
| `get_energy_low_anchors()` | 查询能量低于阈值的锚点 |
| `prune_energy_depleted()` | 剪枝能量≤threshold的锚点 |
| `migrate_to_secure_vault()` | 迁移到`secure_vault/anchors/`并更新index.json |
| `restore_from_secure_vault()` | 从深层存储恢复 |
| `reinforce_anchor()` | 补充能量，标记reinforced_recently |
| `reset_reinforced_flag()` | 重置所有锚点加固标志（衰减周期开始时调用） |

### 持久化
- **写入**: `_agent_memory/anchor_state.json`
- **读取**: `secure_vault/index.json`（深层索引，只读）
- **迁移**: `secure_vault/anchors/{anchor_id}.json` + 更新index.json

### 验证测试（7项全部通过）
1. 注册并激活锚点 + 重复注册幂等性
2. 休眠→卸载转换 + 非法激活拒绝
3. 遗忘衰减（HIBERNATED 10%衰减，自动卸载阈值0.1）
4. 固化整合（UNLOADED→CONSOLIDATED，桩实现）
5. 统计与状态过滤查询
6. 深层存储迁移与恢复
7. 能量低锚点查询

### CONSOLIDATED 桩说明
`consolidate_anchor()` 仅为桩实现，仅记录状态为CONSOLIDATED，不执行真实的补丁整合逻辑。

### 集成占位
- `constraint_lifecycle`: 节点卸载时调用 `unload_anchor()`
- `topology_thermal_monitor`: L2超载时调用 `apply_decay()` + `unload_anchor()`
