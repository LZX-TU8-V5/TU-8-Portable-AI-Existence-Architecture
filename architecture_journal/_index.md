# Architecture Journal Index

活跃决策（ACTIVE = 运行时强制权威源，GC 强制逻辑读此不读 memory 副本）：

已竣工（STABLE，已迁 archive/ 只读）：
- [STABLE] PROMOTE 通道 + architecture_journal 模块落地 — 架构决策由 workspace/architecture_journal 持有（ACTIVE=运行时强制权威源），不由记忆区评分器兜底；记忆区派生断言是衰减无关的学习缓存。 (创建 2026-08-26)

已取代（SUPERSEDED）：
