# 索引同步与复盘联动协议

> 版本：v1.0 | 创建：2026-05-30
> 解决问题：索引不联动导致"掉线"、查找困难

---

## 🔴 问题诊断

| 现象 | 根因 |
|------|------|
| 找不到刚创建的文件 | 索引没有实时更新 |
| 两个索引不一致 | `memory/索引.md` 和 `knowledge/index.md` 各自维护 |
| 外协建议无法索引 | docs/ 目录未纳入索引 |
| 复盘时遗漏文件 | 没有触发式索引更新机制 |

---

## 🟢 解决方案

### 1. 统一索引架构

```
索引总入口（唯一真值）
│
├── memory/索引.md          # 记忆文件索引（日志、外协、事件）
│   └── 覆盖范围：memory/*.md, memory/.dreams/, memory/short/
│
├── knowledge/index.md      # 知识库索引（DNA、架构、脚本）
│   └── 覆盖范围：knowledge/TU-8/, 知识库/, docs/
│
└── _agent_memory/00_state.md  # 状态锚点（最新线索）
```

### 2. 复盘触发条件

| 触发事件 | 执行动作 |
|---------|---------|
| 创建新文件 | 立即更新对应索引 |
| 会话结束前 | 全量索引扫描 |
| 发现索引不一致时 | 强制同步 |
| 用户要求复盘时 | 执行复盘协议 |

### 3. 索引更新脚本

```python
# scripts/index_updater.py

INDEX_PATHS = {
    "memory": "D:/qq366410837/.qclaw/workspace/memory/索引.md",
    "knowledge": "D:/qq366410837/.qclaw/workspace/knowledge/index.md",
}

def update_index(index_type: str, action: str, file_path: str, metadata: dict):
    """
    更新索引条目
    
    Args:
        index_type: memory | knowledge
        action: add | update | remove
        file_path: 文件相对路径
        metadata: {title, tags, status, importance}
    """
    index_file = INDEX_PATHS[index_type]
    
    if action == "add":
        entry = format_entry(file_path, metadata)
        append_to_index(index_file, entry)
    elif action == "remove":
        remove_from_index(index_file, file_path)
    elif action == "update":
        update_entry(index_file, file_path, metadata)

def format_entry(file_path: str, metadata: dict) -> str:
    """格式化索引条目"""
    status_icon = {"active": "✅", "archived": "📦", "孵化": "🟡"}.get(metadata.get("status", "active"), "✅")
    return f"| `{file_path}` | {status_icon} | {metadata.get('tags', '')} | {metadata.get('note', '')} |"
```

---

## 🟡 复盘协议（会话结束前执行）

### Step 1: 扫描新文件
```bash
# 检查 memory/ 目录
ls D:\qq366410837\.qclaw\workspace\memory\*.md

# 检查 docs/ 目录  
ls D:\qq366410837\.qclaw\workspace\docs\*.md

# 检查 知识库/ 目录
ls D:\qq366410837\.qclaw\workspace\知识库\*.md
```

### Step 2: 对比索引
- 读取现有索引条目
- 与实际文件对比
- 找出缺失/多余/过时的条目

### Step 3: 更新索引
- 添加新文件条目
- 移除已删除文件条目
- 更新文件状态（如：🟡孵化 → ✅沉淀）

### Step 4: 更新状态锚点
```markdown
# _agent_memory/00_state.md

## 最近索引更新
- 2026-05-30 10:05 添加 docs/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_FULL_SPECTRUM.md
- 2026-05-30 10:06 更新 知识库/索引.md（新增docs目录）
```

---

## 🟣 本次手动更新（2026-05-30）

现在立即执行索引同步：

### memory/索引.md 需要添加：
- `docs/` 目录条目（新建）
- 2026-05-29 和 2026-05-30 的日志文件（如果有）

### knowledge/index.md 需要添加：
- `docs/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_FULL_SPECTRUM.md`
- `docs/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_GAP_ANALYSIS.md`
- `docs/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/EXTERNAL_ADVICE_SPACETIME_MEMORY.md`
- `docs/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/SPACETIME_SENSE_HUMAN_VS_AI.md`
- `docs/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/STARTUP_PIPELINE_DESIGN.md`

---

## 🔗 连线池

| 连线ID | 涉及模块 | 关系 |
|--------|---------|------|
| link-001 | memory索引 ↔ knowledge索引 | 交叉引用 |
| link-002 | 复盘协议 → 索引更新 | 触发关系 |
| link-003 | 索引更新 → 状态锚点 | 同步关系 |

---

*协议创建：金木蟾 | 2026-05-30*
