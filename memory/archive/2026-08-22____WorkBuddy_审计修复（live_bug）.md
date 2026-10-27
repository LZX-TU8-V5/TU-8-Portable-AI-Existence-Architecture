## WorkBuddy 审计修复（live bug）

来源：`D:\工作文件\桌面\workbuddy\2026-08-01-14-43-57\tu8_live_bug_audit_2026-08-15.md`

### 🔴 真 bug：weismann_fork.py 正则语法错误
- **文件**：`src/weismann_fork.py:76`
- **根因**：`rf"{re.escape(_DECONTAMINATE_HOST)|"` 缺少闭合 `}`，整段正则括号配平错
- **引入**：2026-08-13 主机名动态化改造
- **修复**：补 `}` → `rf"{re.escape(_DECONTAMINATE_HOST)}|"`
- **状态**：✅ 编译通过

### 🟡 死引用清理
- `src/load_monitor.py:41`：`spikes` 键指向已删除的 `spike_valley_detector_state.json` → 已删除该行
- `src/spiral_topology_audit.py:45`：同上 → 重定向至 `unresolved_spikes.jsonl`（真实文件）
- 状态：✅ 编译通过

---

### 用户关键洞察（来自千问对话_长期记忆vs上下文_2026-08-15.md）
- 40K目标是天花板不是终点
- GC触发条件比触发时机难：先有最简规则（60天无引用→归档）
- 存量不迁移，增量走结构化
- 五维度基线测试应提至P1
- **写入纪律三问**（防反弹）：
  1. 这条信息7天后还有用吗？
  2. 能用一句话说清吗？
  3. 已有条目里有没有可以覆盖而不是追加的？

