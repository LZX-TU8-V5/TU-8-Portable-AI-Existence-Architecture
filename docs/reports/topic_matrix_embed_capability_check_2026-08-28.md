# 话题矩阵 embedding 能力查证 (2026-08-28)

## 方法
- 扫 1512 个 py（src/knowledge/knowledge_base/根），搜 embed/sentence_transform/chroma/faiss/milvus/qdrant/api_embed 等模式。

## 实证结论
- TU-8 已有 embedding 管道：src/cognitive_evaluator.py 的 TFIDFEmbedder(dimension=128) 已定义，cognitive_integration.py:54 已实例化为下游产出 embedding。注释写"轻量级嵌入替代 heavy embedding model"。
- 可选真语义：scripts/capacitive_retrieval.py:152 延迟加载 sentence_transformers，缺失降级关键词匹配。
- 无本地向量库：chroma/milvus/qdrant 全 0；FAISS 仅 quantized_memory 外部索引引用。

## 对实现设计的修正
- 原稿 3.3/5/11 写"无 embedding 管道→TF-IDF 降级"是推断错误。
- 修正：Vectorizer 默认后端=复用 TFIDFEmbedder（不新造）；sentence_transformers 作可插拔升级；storage 仍 numpy memmap。
- 落点：docs/design/topic_matrix_impl_design_2026-08-28.md 三处 edit 已改。
