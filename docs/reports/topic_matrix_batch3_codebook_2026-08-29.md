# 话题语义矩阵 批次3 密文库落码 (2026-08-29 15:26-15:55)

## 范围（§12 决策）
仅注册表（不含 entity_resolver 知识组织层）。

## 落码
- 新建 src/codebook.py (3311B)：Codebook 类，挂 secure_vault/index.json["codebook"] 键
  - register(label, event_id) -> sym_*（幂等，同名 label 复用）
  - resolve(sym) / resolve_label(sym) -> 实体记录/明文
  - 短码 = sym_{slug(label)[:12]}_{md5(label)[:4]}
- metabolic_pipeline.py：distill 接线 _compress_entities(content) -> entity_syms
  - 已知高频繁体词典 _KNOWN_ENTITIES（苹果/TU-8/七七/李奥/钢印/千问/牛顿/PROMOTE）
  - 演进：未来由 topic_semantic_matrix v1.3 L2.5 grounding_refs 行为性浮现，不写死

## 验证
- codebook 注册返回 sym_*，幂等 True
- distill entity_syms 正确提取 5 实体压码
- index.json["codebook"] 键写入（5 条）
- 幂等稳定（再跑不新增）
- file_lint: 0 error / 3 warn（已知冷归档旧裸名，与本次无关）

## 备份
- backup/topic_matrix.py.20260829_batch3.bak
- backup/metabolic_pipeline.py.20260829_batch3.bak
- backup/vector_store.py.20260829_batch3.bak

## 状态
批次1+2+3 全落地，话题语义矩阵算法核心完整。
