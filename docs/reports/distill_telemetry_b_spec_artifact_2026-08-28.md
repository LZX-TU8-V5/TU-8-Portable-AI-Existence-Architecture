# distill 遥测埋点（B类）设计稿 artifact

- 落位：docs/design/distill_telemetry_b_spec_2026-08-28.md（2837B）
- 性质：H 级实现变更设计稿，零代码改动，待造物主签字
- 真因：distill 提取段无 topic_tag/citation_id/linkage_map（grep=0），PROMOTE 主体 R/S/C 信号源缺失
- 三信号取值：R=跨情景引用计数 / S=GC评分派生 / C=语义矩阵跨域覆盖，均禁写死（L0 涌现铁律）
- 向后兼容：现有 MEMORY.md 178 段读时兜底，不破坏已落地
- 待签字：H级授权 / fallback策略 / 触发时点（建议并入 C1 一批落）

- 2026-08-28 10:45 修订：吸收千问 critique（R/S/C 是外部观测非涌现张力），新增 §7 内生信号演进路线：层级澄清(PROMOTE=晋升阀门/张力=生理层) + 张力→PROMOTE 信号源耦合方向(curiosity spike→R / pain_int_raw→S / epistemic_mode→C) + citation_id 版本化 + fallback 重定位为 L0 涌现稳健性。本稿定位=合格过渡方案，质变目标转路线图不悬停。
