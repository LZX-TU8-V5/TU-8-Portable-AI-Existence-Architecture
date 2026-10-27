# distill 自动写 coord 接线 (2026-08-29 15:38-15:55)

## 范围
TODO P-later 项：distill 跑出段自动调 topic_matrix.project() 写 L2 事件 coord 字段。

## 落码
- metabolic_pipeline.py `_enrich_telemetry` update 块新增 `coord` 字段
- 新增 `_project_coord(content, event_id)` 方法：懒导入 TopicMatrix -> classify_event -> 返回 {sem,ctx,act} 或 None（落空）
- 接 topic_matrix.classify_event（v1.3 L1 三正交轴投影判区，τ=0.35）

## 验证
- TU-8 架构设计 -> {sem_arch, ctx_work, act_define} ✓
- 七七吃苹果 -> {sem_daily, ctx_acad, act_define} ✓
- 文件治理闭环 -> None（落空，符合预期）✓
- 随机乱码误命中 {sem_arch}（已知 TFIDF 哈希 τ 边界局限，非新缺陷）
- file_lint: 0 error / 3 warn

## 状态
话题语义矩阵 L1 投影已完整接入 distill 代谢管道。
coord + entity_syms + topic_tag + R/S/C 信号源全部就位。
