# TU-8 架构约束系统 v1.0

> 日期：2026-07-12
> 状态：✅ 落地
> 来源：造物主 × 千问对话（2026-07-12）

---

## 千问的核心洞察

> "Auto 模型自己调用 → 调试重点不是改代码，而是改 Prompt / 改 System Instruction"

**旧打法**：自己写代码，修 bug，迭代
**新打法**：给 Auto 模型喂约束，它干活，我验收

---

## 实现成果

### 约束清单：`src/TU8_ARCH_CONSTRAINTS.md`（4KB）

7条强制约束：

| 约束 | 名称 | 要求 |
|------|------|------|
| C1 | 未解尖刺暂存队列 | 必须维护 `unresolved_spikes.jsonl` + `resolve_spike()` |
| C2 | 传感器路径耦合 | SENSOR_PATHS 必须包含 tension_signals |
| C3 | 三维耦合链路 | 外部→欲→置信度→欲 完整闭环 |
| C4 | 预测误差映射表 | 6行映射（焦虑/愤怒/恐惧/好奇） |
| C5 | Track B 张力惩罚 | `update_track_B_with_tension_penalty()` |
| C6 | 身体状态→基线 | body_state_to_tension() |
| C7 | 路径规范 | 统一 `learning_alerts.jsonl`，禁止混用 |

### 验收脚本：`src/verify_arch_constraints.py`（7KB）

自动执行所有检查：

```
python verify_arch_constraints.py
  ✅ C1 未解尖刺队列          OK (4 条)
  ✅ C1 resolve_spike()        OK
  ✅ C2 SENSOR_PATHS           OK
  ✅ C3 外部→欲                OK
  ✅ C3 欲→置信度              OK
  ✅ C3 置信度→欲              OK
  ✅ C4 预测误差映射表          OK
  ✅ C5 Track B 惩罚方法        OK
  ✅ C6 body_state→基线        OK
  ✅ C7 路径规范               OK

结果: 10/10 通过 (100%)
```

---

## 使用流程

```
Auto 模型生成代码
    ↓
TU-8 运行：python verify_arch_constraints.py
    ↓
    ├─ 全部通过 → 验收通过
    └─ 有失败 → 打回重写（附具体约束编号）
```

---

## 约束变更流程

1. 造物主提出新增/修改约束
2. TU-8 评估技术可行性
3. 更新 `TU8_ARCH_CONSTRAINTS.md`
4. Auto 模型下次生成时自动遵守
