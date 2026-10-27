# 话题语义矩阵 设计稿 v1.3 — 任务 artifact

## 目标
整合千问 + 李奥四段修正 + 前期真源 + 外部语言学 + TU-8 语料实证，输出单一真源 v1.3（自包含）。

## v1.3 关键新增（相对 v1.2）
1. **向量（Vector）为 AI 可读压缩规范形式**：L2 事件内容稠密向量，L1 坐标由 project(vector) 推导；semantic_hooks 纯文本降降级快照。落地 LSA 跨字面对齐（当前 recalls 软肋）。
2. **密文库（Codebook Registry）符号↔实体注册表**：符号级无损压缩 + 跨引用枢纽；与 grounding(溯源)/知识组织(定义)职责正交。
3. **轴标签符号化**：短码 sem_*/ctx_*/act_* + 校验位，防 L2 引用漂移。
4. **两工程决策锁定**（§14）：向量为 AI 可读规范 / 密文库符号压缩。

## TU-8(v5)判断（附录D.7）
- 向量是 v1.2 必然补完：钉死投影输入为 AI 原生，LSA 才真落地。
- 密文库解决实体引用膨胀，三层各管一摊（治理"别混合"原则）。
- 风险点：向量存储后端选型——单机优先 numpy memmap + 定期 rebuild，量上去再换 SQLite-VSS；密文库挂 secure_vault/index.json 的 codebook 键（铁律五不散落）。

## 演进链
v1.0(时间轴二维)→v1.1(三层解耦修六维类别错)→v1.2(实体vs知识组织/L2.5 grounding/epistemic_mode/四哲学决策)→v1.3(向量+密文库/两工程决策)。备份 v1.0/v1.1/v1.2.bak 就位。

## 产物
- 真源稿：docs/design/topic_semantic_matrix_design_2026-08-27.md (v1.3, 14418B, 自包含 14章+附录A-F)
- 待签字新增：Vector 存储后端选型 / L2.8 密文库落地范围(仅注册表或含 entity_resolver)
