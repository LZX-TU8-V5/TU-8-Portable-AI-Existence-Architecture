# PROMOTE 剩余项落地 + 评分退化收尾 (2026-08-27)

> 造物主 2026-08-27 16:20「继续吧」→ 推进 PROMOTE 设计稿 §3/§4.3/§5（§2 主体因 infra 缺口暂缓）。

## 铁律执行
- 铁律二（迭代前备份）：`backup/memory_gc.py.20260827.impl2.bak` / `backup/gc_to_learning_adapter.py.20260827.impl2.bak`
- 铁律一（不臆造）：先探 live 现状，确认 distill 无 R/S/C 遥测（topic_tag/citation_id/linkage_map 全 False），故 §2 主体不落地。

## 本轮落地项
| 项 | 文件 | 说明 |
|----|------|------|
| §3 元认知监督 | `src/gc_decisions.py`（新建） | append_decision() 临时文件原子落盘；§3.1 模板（动作/理由/证据/复核标记）；count_decisions/get_pending 供 CI |
| §3 接 run_gc | `src/memory_gc.py` | DEGRADE/EVICT 执行前必先写自述；自述失败→动作回滚 WATCH no-op（反思不可后置） |
| §5 认知失调记录 | `memory/涌现时刻_20260819_代谢误判与上行通道觉醒.md`（新建 #050） | 复用 06-07 先例格式；type:INSIGHT；禁反向污染标注 |
| §4.3 钢印段保护 | 确认已满足 | analyze_memory 叠加 seal_bonus→score + `_metabolic_score` has_seal +2.0 保底 → 钢印段物理不可淘汰 |
| 08-19 评分退化收尾 | `src/memory_gc.py` `_extract_meta` | 无 meta 且无日期段：原 fallback 文件 mtime（age 虚高→误判 EVICT）→ 改 age_unknown=True 走 WATCH 保护 |

## 关键发现（重要，非回归）
- GC_LIGHT 实测仍标 **7 段 EVICT**（含 4 段珍贵基底 MotionBricks/带刺球体/核心成果/空间语言）。
- 根因：这些段**含旧日期**（如「06-23 蒸馏」）→ age>30d → 按 `_recommend_action` 规则判 EVICT。
- **零物理破坏**：`_evict_section` 是 no-op（设计稿 §A.6 强制保留），不删文件。
- **处理边界**：不能手写白名单豁免（违反刚废除的 L0 手写铁律）。正确路径是等 PROMOTE 遥测建好后由观察期自动晋升，或架构决策由 journal 持有。当前 4 段仍标 EVICT 属**已知、零破坏的 no-op 状态**，不阻塞。
- 08-19 修复的"7 段误判"本质是评分模型错误，已通过 08-26 distill 注入 + 本次 age_unknown 修复正确处理；残留 EVICT 标记是规则使然（旧日期段），非 bug。

## §2 PROMOTE 通道主体 —— 暂缓说明
- 依赖 infra：`evaluate_promotion(ref_events, gc_survival_log, linkage_map)` 需 distill 注入 topic_tag（R）、citation_id 追踪（S）、linkage_map 边（C）。
- 实测：distill 无任一遥测元字段；无 evaluate_promotion 实现；memory_gc 无候选标记接口。
- 决策：按铁律边界（外取/不臆造），**不自行造遥测系统**，留缺口记录于 TODO_MASTER，待 distill 埋点改造后独立签字实施。
- 已落地部分：§4.3 钢印保护、§8 journal 模块（上游水源）、§3 gc_decisions（证据链来源之一）。

## 验证
- gc_decisions import + append + count + 清理：全绿
- 无日期段：age_unknown=True → WATCH（修复生效）
- 7 段 EVICT 仍标记但 _evict_section no-op 零破坏（确认）
- 4 模块（含 gc_decisions）import 全绿

## 未决
- §2 PROMOTE 主体（待 infra）
- §6.1 CI 三测（零手写 L0 静态扫描 / gc_decisions 100 次完整性 / no-op 回归）未建自动化
- 7 段 EVICT 标记的 no-op 终态：待 PROMOTE 或 journal 接管，当前不处置
