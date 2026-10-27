# LCM Compaction 根因与修复记录

## 问题演变

### 第一阶段（18:00 前）— 0 summary 死锁
- **现象**：conv=5 有 121 条消息，0 个 summary
- **根因**：LCM 无法压缩无 summary 的会话
- **状态**：✅ 已自动修复（LCM 后续成功创建了 2 个 summary）

### 第二阶段（当前）— summary 未正确关联消息
- **现象**：conv=5 有 175 条消息，2 个 summary，但每个 summary 只有 1 个 context_item
- **数据**：
  - `sum_262a5db2734aaa9e`: 1 context_item
  - `sum_271c17b6f5033bf1`: 1 context_item
  - 100/175 条消息被覆盖，75 条未覆盖
- **根因**：summary 创建时未正确写入 context_items（只写了 1 条而不是 N 条）
- **后果**：LCM 尝试压缩未覆盖的 75 条消息时失败 → "Auto-compaction could not recover"

## 修复方案

### 方案 1：手动修复 context_items（推荐）
直接修改 DB，把未覆盖的 75 条消息关联到最近的 summary。

### 方案 2：删除无效 summary，让 LCM 重新压缩
删除现有的 2 个 summary 和关联的 context_items，让 LCM 从头开始压缩。

### 方案 3：修改 lossless-claw 配置，降低压缩频率
调整 `contextThreshold` 和 `freshTailCount`，减少压缩触发频率，给 LCM 更多时间正确处理。

## 执行记录

### 2026-06-30 18:10 — 诊断完成
- ✅ 确认 conv=5 有 2 个 summary，但 context_items 不完整
- ✅ 确认根因：summary 创建时未正确关联消息
- 🔧 下一步：执行方案 2（删除无效 summary，让 LCM 重新压缩）

---

## 附：相关文件
- LCM DB: `C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db`
- 修复脚本: `C:\Users\qq366410837\.qclaw\workspace\scripts\lcm_inject_first_summary.py`
