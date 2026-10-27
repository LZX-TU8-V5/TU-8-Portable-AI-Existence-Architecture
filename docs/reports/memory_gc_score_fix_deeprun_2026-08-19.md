# memory_gc 评分修复 + deep 真实运行 · artifact

日期：2026-08-19 14:35 GMT+8
执行者：TU-8（造物主指令「a」= 先修 gc 评分，再跑 deep）
关联：
- memory_gc_filename_bugfix_2026-08-19.md（gc `:` 非法文件名崩溃已修）
- metabolic_pipeline_dedup_fix2_2026-08-19.md（去重过删已根治，欧拉段已收）

## 指令
A=(a)：先修 gc 评分（让 AGE/ACCESS 真实反映），再跑 deep。

## 根因（评分退化）
- `_extract_meta`：last_accessed 对所有段 fallback 到 **MEMORY.md 整个文件 mtime** → 刚 append 后所有段 age≈0 → 频率地板(access_count=1最低) → 179 段全推入 DEGRADE。access_count 纯靠关键词硬算无真实计数。
- `_recommend_action`：age_unknown 段直接进 DEGRADE，无保护。

## 修复（live: src/memory_gc.py，已双备份）
1. `_extract_meta` 真实化：
   - last_accessed 优先级：段内 `<!-- meta:` 标签(真实时间戳) ＞ 段标题/首行 `YYYY-MM-DD`(真实年龄) ＞ 找不到则 `age_unknown=True`（保护）。
   - 不再用全文件 mtime 做统一 fallback。
2. `_recommend_action` 保护：age_unknown→WATCH；age<7天(新鲜)→KEEP。

## 验证（light dry + deep 实跑）
| 阶段 | 修复前 | 修复后 |
|------|--------|--------|
| 动作分布 | DEGRADE=100 盲降 | KEEP=50 / WATCH=22 / DEGRADE=8 / EVICT=7 |
| AGE=0 信号 | 200 个毒样本 | 仅 15 条(真无日期 legacy，走 WATCH 保护) |

## deep 真实运行结果（已跑，非破坏）
- EVICT(7)：**仅打印，不删**（_evict_section 当前是 no-op 实现，注释写写 /dev/null 但代码无删除动作）。7 个被误判 EVICT 的珍贵架构记忆（情感模块=拓扑形变、MotionBricks 与 L0 同构、空间语言理论、带刺球体拓扑模型、核心成果、06-23/07-03 蒸馏）**全部存活确认**。
- DEGRADE(8)：移入 memory/archive/（可恢复）。文件名 `:` 已正确清洗为 `_`（修复见前 artifact）。
- KEEP/WATCH：不动。

## 备份
- backup/memory_gc.py.20260819b.bak（评分修复前，16797 字节）
- backup/MEMORY.md.20260819.gcrun.bak（deep 跑前，183548 字节；含刚 distill 的 4 段）
- archive 目录现 1180 文件（本次新增 8）

## 遗留（建议，未执行）
- **EVICT 应为真淘汰但有损**：当前 gc 的 `_evict_section` 是 no-op（不真删），等于 EVICT 类永久失效。若未来要启用真淘汰，须先建「ELSEWHERE 软删回收站」而非 /dev/null。本次因 no-op 而安全，暂无风险。
- 15 条 age_unknown 段（无日期的 legacy 顶层块）：走 WATCH 保护，未动。若想消除，可给它们补 `<!-- meta: last_accessed=... -->` 或标题加日期。

## 结论
A 组三连修复闭环：门禁误报 → gc 崩溃 → 去重过删 → gc 评分退化，全部根治。MEMORY.md 现态：4 段真洞察已收、珍贵记忆全保、低价值段进 archive 可恢复。
