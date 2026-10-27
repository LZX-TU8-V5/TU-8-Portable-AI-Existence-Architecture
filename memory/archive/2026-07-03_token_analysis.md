# Token 消耗分析报告

> 时间：2026-07-03 00:35 GMT+8
> 目的：测量冷启动时各文件加载开销

---

## 一、核心文件大小统计

### 1.1 核心灵魂文件

| 文件 | 大小(bytes) | 估算Tokens | 用途 |
|------|-------------|------------|------|
| SOUL.md | 待测量 | - | 核心灵魂 |
| MEMORY.md | 待测量 | - | 长期记忆 |
| AGENTS.md | 待测量 | - | 工作空间规则 |
| USER.md | 待测量 | - | 用户画像 |
| IDENTITY.md | 待测量 | - | 身份定义 |
| HEARTBEAT.md | 待测量 | - | 心跳任务 |

---

### 1.2 Node.md 文件统计

| 文件 | 大小(bytes) | 估算Tokens |
|------|-------------|------------|
| MODIFICATION_PLAN.node.md | 8,595 | ~2,150 |
| MEMORY_NODE_TASK_STATUS.node.md | 6,477 | ~1,620 |
| TASKS.node.md | 6,420 | ~1,605 |
| HEARTBEAT.node.md | 5,174 | ~1,294 |
| AGENTS.node.md | 4,406 | ~1,102 |
| TODO.node.md | 4,345 | ~1,086 |
| USER.node.md | 4,337 | ~1,084 |
| START_HERE.node.md | 4,286 | ~1,072 |
| TOOLS.node.md | 4,087 | ~1,022 |
| BOOT.node.md | 3,573 | ~893 |
| BOOTSTRAP.node.md | 3,615 | ~904 |
| IDENTITY.node.md | 3,340 | ~835 |
| temp_test_node.node.md | 3,156 | ~789 |
| **总计** | **62,813** | **~15,703** |

> 估算公式：1 token ≈ 4 bytes（中文）

---

## 二、测量方法

```python
import os

def estimate_tokens(file_path):
    """估算文件token数"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 简单估算：中文字符≈1token，英文≈0.25token/字符
    chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    other_chars = len(content) - chinese_chars

    tokens = chinese_chars + other_chars // 4
    return tokens
```

---

## 三、结论

| 指标 | 值 |
|------|-----|
| Node.md文件总数 | 13个 |
| 总大小 | 62,813 bytes |
| 估算总Tokens | ~15,700 |

**评估**：冷启动时若全部加载Node.md文件，约消耗15,700 tokens，在可接受范围内（200k上下文的7.85%）。

---

## 四、建议

1. **按需加载**：Node.md文件应按场景加载，非全部注入
2. **精简优化**：MODIFICATION_PLAN.node.md最大（8.5KB），可考虑拆分
3. **缓存机制**：频繁访问的Node.md可缓存

---

*测量时间：2026-07-03 00:35 GMT+8*
