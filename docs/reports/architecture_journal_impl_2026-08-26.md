# architecture_journal 模块实现闭环 (2026-08-26)

> 造物主 2026-08-26 11:34 显式签字「那就开始写代码吧」→ 落地 PROMOTE 设计稿 §8。

## 落地范围（签字覆盖）
按造物主选 (a) 直觉方案：撤回 Coherence 信号，建 `workspace/architecture_journal` 模块 + 三处加固。
实测代码现状比设计稿乐观——§4.2/§4.1 部分项已满足，无需改。

## 铁律执行
- 铁律二（迭代前备份）：`backup/memory_gc.py.20260826.impl.bak` / `metabolic_pipeline.py.20260826.impl.bak` / `seal_to_gc_adapter.py.20260826.impl.bak` + `backup/MEMORY.md.20260826.journal_inject.bak`
- 铁律一（不臆造）：先探 live 接口，发现 `compute_seal_bonus` 已非 stub、`_evict_section` 已是 no-op、`_learning_protected.json` 已空壳——§4 清理项现状满足，免改。

## 新增/修改文件
| 文件 | 动作 | 说明 |
|------|------|------|
| `src/architecture_journal.py` | 新建 | ArchitectureJournal 类：log_decision / load_active_constraints / get_active_assertions / review_transitions（自动状态转移）/ deprecate_learning_protected / _regenerate_index |
| `architecture_journal/CONTRACT.md` | 新建 | 模块契约/维护规则/三处加固/与 Coherence 关系 |
| `architecture_journal/2026-08-26_PROMOTE通道与journal模块落地.md` | 新建 | 种子 ACTIVE 决策（断言进 distill 上游） |
| `architecture_journal_archive/` | 新建 | 竣工只读归档区（空） |
| `src/metabolic_pipeline.py` | 改 | distill 增 `_journal_active_sections()` 上游水源；段变量初值修正 |
| `src/memory_gc.py` | 改 | analyze_memory 接 journal ACTIVE 强制 KEEP（加固1）；run_gc 启动自动 review_transitions + deprecate（加固2） |

## 三处加固落地映射
1. **权威源优先级**：`memory_gc.analyze_memory` 在 protected 判定后读 `aj.load_active_constraints()`，命中即强制 KEEP（GC 读 journal 不读 memory 副本）。
2. **自动状态转移器**：`memory_gc.run_gc` 每次启动调 `aj.review_transitions(dry_run=mode==LIGHT)`，ACTIVE→SUPERSEDED/STABLE 自动翻状态，STABLE 迁 archive。
3. **与 ARCHITECTURE_LOG 不重叠**：CONTRACT.md 明确 journal=操作层、ARCHITECTURE_LOG=哲学层，_index 不重复哲学。

## 验证（全部通过）
- 模块 import OK；ACTIVE 约束集含种子决策 1 项（CONTRACT 已排除）；review_transitions dry_run 空转移（无误判）。
- `_learning_protected.json` 标记 `DEPRECATED: "2026-08-26"`。
- distill 干跑提取 1 段（journal 上游）；真实跑注入 MEMORY.md（备份 145133 字节可回滚），GC 验证 80 段全量、49 KEEP、7 段珍贵基底零破坏（EVICT 仍 no-op）。
- GC analyze_memory 耦合 journal 不崩。

## 未落地（需后续独立签字，属 v0.1→v0.2 仍待建）
- §2 PROMOTE 通道规格（evaluate_promotion 三元组 / 观察期状态机 / 独立上行评估器）
- §3 元认知监督（gc_decisions.md 原子写入 / 完整性测试）
- §5 认知失调记录（涌现时刻_20260819 正常代谢）

## 遗留观察
- `review_transitions` 的 scope 重叠判定为单 token 相交（≥1），粒度粗；当前仅 1 条 ACTIVE 决策，暂不暴露问题，待多决策时复核。
- 种子决策已进 MEMORY.md 走正常 PROMOTE 管道，未来若行为性信号（R/S/C）达标则晋升 L0；当前无 evaluate_promotion 实现，晋升通道待建。
