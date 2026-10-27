# 任务归档：behavior_upgrader 双向拦截协议

**归档时间**：2026-07-22
**状态**：✅ 完成（18/18 自测通过）

---

## 背景

用户指出 HEARTBEAT.md 中的"汇报协议"为硬性规则，但 TU-8 历史上从未自动执行。用户希望：
1. 系统自动拦截"只报问题不带建议"的行为
2. 不阻塞对话流程
3. 状态化积累，可代谢

---

## 核心设计

**双向阀门**：
- A→B（意图归意图）：`record_intent()` 捕获意图，写文件，不跑脚本，不输出
- B→A（状态归状态）：`read_and_translate()` 读取状态，LLM 翻译成人话

**链路**：
1. alignment_verify() 拦截到"复盘"关键词
2. `detect_intent()` 提取关键词 → `record_intent()` 记录意图
3. 返回 `llm_append = "[检测到复盘意图，请说「复盘报告」查看结果]"
4. LLM 在回复末尾追加提示
5. 用户说"复盘报告" → `read_and_translate()` 翻译状态，输出规则表
6. 定时任务每周代谢（结果写文件，永远不直接输出）

**待升级检测**：alignment_verify 检测到"复盘"但无"建议" → 触发行为升级

---

## Bug 修复

| Bug | 根因 | 修复 |
|-----|------|------|
| 第二次说"复盘"仍提示 | `already_pending` 检查在写文件之后 | 移到写文件之前，提前返回 |
| read_and_translate has_pending=False | `has_pending` 在清空后算（永远是 False） | 清空前先捕获 |
| pending 在第二次调用后丢失 | `has_pending` 计算后状态文件被覆写为 pending=None | 已在 already_pending 分支跳过写入 |

---

## 文件清单

| 文件 | 变化 |
|------|------|
| `src/behavior_upgrader.py` | 重写双向拦截主逻辑 |
| `BEHAVIOR_RULES.md` | 新建，汇报协议永久存储 |
| `src/alignment_verify.py` | 集成 detect_intent+record_intent |
| `HEARTBEAT.md` | 汇报协议段落替换为引用 |

---

## 集成验证

```
Test1: content含"复盘" → llm_append正常设置 ✓
Test2: content无"复盘" → 无操作 ✓
Test3: 第二次"复盘" → 不重复提示 ✓
自测：18/18 通过 ✓
```

---

## 剩余问题

无。
