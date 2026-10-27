# B+C1 落地 artifact (H级, 2026-08-28)

## 签字
- 造物主 10:42 GMT+8 签 H 级，按路线3（B+C1 并入一批落）

## 备份
- backup/metabolic_pipeline.20260828_bc1.bak (12942B)
- backup/memory_gc.20260828_bc1.bak (21807B)

## 落地内容
1. 新建 src/promote_channel.py (6728B): evaluate_promotion(ref_events, gc_survival_log, linkage_map) 签名冻结 + 观察期状态机(CANDIDATE→SOLIDIFIED/DOWNGRADE) + gc_decisions 原子自述(no-op 安全)
2. 改 src/metabolic_pipeline.py: distill 提取段补 topic_tag/citation_id/ref_events/survival_score/coverage_domains/linkage_map 六字段(向后兼容178段) + _enrich_telemetry/_project_topic/_coverage_domains/_build_linkage 四方法
3. 改 src/memory_gc.py: 加 _load_scores() 供 S 信号派生(容错空 dict)

## 冒烟
- 三模块 import OK
- evaluate_promotion R3S2C2→CANDIDATE / 空→DOWNGRADE(不破坏)
- distill dry_run 正常，enriched 段全 8 字段
- file_lint 0 error / 3 warn(冷归档历史快照旧引用，非新增)

## 千问 critique 吸收
- B 稿 §7 已补内生信号演进路线(张力→PROMOTE 耦合: curiosity→R / pain_int_raw→S / epistemic_mode→C)
- 本次落码是工程过渡，非自涌现张力终态；质变目标转路线图不悬停

## 遗留
- topic_tag 当前返 [](禁写死)，待 topic_semantic_matrix v1.3 L1 投影就位后接管(§7.3)
- citation_id 版本化(允许多快照)待 PROMOTE 主体稳定后补(§7.4)
