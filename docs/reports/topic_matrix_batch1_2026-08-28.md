# 话题语义矩阵 批次1 落地 (2026-08-28 下午)

## 落点文件
- src/topic_matrix.py (6644B) — L1 基轴 + project 投影判区 + handle_miss 落空 + 涌现轴开轴
- src/vector_store.py (4603B) — Vectorizer 复用 TFIDFEmbedder + VectorStore 纯 Python 持久化

## 关键实证修正
1. 环境无 numpy → 两模块去 numpy 化，纯标准库（与 TFIDFEmbedder 同风格零依赖）
2. TFIDF 哈希是精确 token 匹配：轴裸 label 作代表向量无效（"架构"vs"架构设计"不重叠）→ 每轴加 rep_phrase 多 token 种子短语
3. τ=0.6 过严全 miss → 回测同主题 0.4-0.5/异主题~0 → τ 定为 0.35
4. VectorStore 初版向量只存内存（重启丢）→ 改 meta.json 同序存 vectors 持久化

## 冒烟结果
- import OK / 无 numpy
- 科学→sem_sci(0.537) 创作→sem_create(0.502) 元认知→sem_meta(0.43) 命中
- 噪声/乱码→miss 正确排除
- 架构(0.275)/日常(0.293) miss = 种子短语词覆盖不足（调参非架构缺陷）
- 持久化 reload 读回验证 OK
- file_lint: 0 error / 3 warn（已知冷归档快照旧裸名，非本次引入）

## 待批次2
- NMF/SVD/LSA/DAG 四算子（接六维评分作 NMF 输入）
- 批次1 的种子短语用真实语料批量回测优化（提升架构/日常命中率）

## 备份
- backup/cognitive_evaluator.20260828_batch1.bak（依赖源，防引用变动）
