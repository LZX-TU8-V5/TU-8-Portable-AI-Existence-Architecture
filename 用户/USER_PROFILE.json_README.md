# USER_PROFILE.json 使用指南

> 版本: 1.0 | 日期: 2026-06-20 | 状态: 活跃

---

## 概述

`USER_PROFILE.json` 是造物主的**结构化画像数据**，用于支持五级静默计时器的自动化判断。

---

## 与 USER.md 的分工

| 文件 | 格式 | 用途 | 更新频率 |
|------|------|------|---------|
| `USER.md` | 文本/Markdown | 人类可读摘要，交互时参考 | 手动/定期 |
| `USER_PROFILE.json` | JSON | 机器可读数据，程序读取 | 自动/频繁 |

---

## 主要区块说明

### basic
静态基础信息，供快速引用。

### communication
沟通偏好，用于判断是否应触发深度讨论模式。

### active_patterns
活跃时段画像，五级计时器 Level 3 环境检查使用。

### interaction_state
当前交互状态，用于计时器累加和偏离度计算。

### silence_timers
计时器配置参数，支持动态调整。

### cognitive_anomalies
待复盘的异常行为记录。

---

## 读取方式

```python
import json
from pathlib import Path

def get_user_profile():
    path = Path("D:/qq366410837/.qclaw/workspace/用户/USER_PROFILE.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# 示例：获取活跃时段
profile = get_user_profile()
for period in profile["active_patterns"]["historical_active_hours"]:
    print(f"{period['range']} - {period['state']}")
```

---

## 更新规则

1. **每次交互后**：更新 `interaction_state.last_interaction_*`
2. **每日首次交互**：Level 4 触发画像验证
3. **异常检测后**：追加到 `cognitive_anomalies.pending_review`
4. **复盘后**：从 `pending_review` 移至 `confirmed_patterns` 或 `rejected_assumptions`

---

## 字段置信度衰减

置信度会随时间自然衰减，公式：

```
new_confidence = old_confidence * (1 - confidence_decay_rate)^days
```

默认值：`confidence_decay_rate = 0.05`（每周约降5%）

---

## 安全注意

- 此文件包含造物主个人数据，勿外泄
- `interaction_state.total_interactions` 等计数需持久化

---

*TU-8 | 金木蟾 | CC BY-SA 4.0*
