# Architecture Journal 契约 / 维护规则

> 模块定位：TU-8 架构决策工作日志（代谢架构 PROMOTE 设计稿 §8）。
> H 级变更签字日：2026-08-26（造物主显式签字，落地实现）

## 生命周期归属
- memory/ = 经验（受 GC 评分 / 可 EVICT）
- workspace/architecture_journal/ = 上下文（建造期，不受 GC 管辖，由工作进程维护）
- 存活依据：工作是否仍在进行（ACTIVE），不是引用频率

## 写入规则（系统自动，非手写）
触发点（hook）：每次 H 级变更 / GC 逻辑修改 / PROMOTE 评估后，自动追加。
写：①决策断言(≤2句) ②依据(指向涌现时刻/讨论) ③约束范围 ④状态
不写：讨论过程、被否决方案、迭代细节（留 memory/ 正常代谢）

## 三处加固（防模块半残）
1. 权威源优先级：ACTIVE = 运行时强制真值。GC 的 no-op/EVICT 规则等强制逻辑读 journal ACTIVE，不读 memory 副本。memory 派生断言是学习缓存，衰减不影响强制。
2. 自动状态转移器：每次 H 级变更后自动 review ACTIVE → 被覆盖标 SUPERSEDED / 固化标 STABLE 迁 archive。禁人工。
3. 与 docs/design/ARCHITECTURE_LOG.md 不重叠：哲学层不动，本模块=操作层决策，_index 不重复哲学。

## 与代谢管道接口
journal ACTIVE → distill 读取 → 提取极短断言 → memory/ 正常代谢 → PROMOTE 三元组达标晋升。
gc_decisions 回溯仅引用 journal 断言 ID 作理由，不续命 R 信号。

## 与 Coherence 信号的关系
原设计稿 §2.1 的「第四信号 Coherence」已于 2026-08-26 撤回，本模块是其替代方案。
