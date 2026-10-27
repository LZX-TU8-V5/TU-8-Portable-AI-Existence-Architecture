# P0 #4 τ 绑定后端 + 软区间落地（2026-08-29）

## 目标
实现认知契约 §0.2：τ 从硬编码魔法数改为 Backend 属性，支持软区间（precise/fuzzy/inhibit），切换向量后端时自动跟随。

## 改动
- `src/topic_matrix.py`：
  - 新增 `VectorizerBackend` 抽象 + `TFIDFBackend`(tau_fuzzy=0.35/precise=0.6) + `EmbeddingBackend`(tau_fuzzy=0.65/precise=0.8)
  - 删除模块常量 `TAU=0.35`（硬编码消除）
  - `TopicMatrix.__init__` 改 `backend` 驱动，`self.tau` 从 backend 取（兼容旧签名）
  - `RegionHit` 加 `zone` 字段；`project` 用 `backend.zone()` 软区间（sim≤0 才 miss，否则 fuzzy/inhibit 降权召回）
  - `classify_event` 返回 `zone` 供下游降权
- `src/memory_reader.py`：E3 接 zone——sem 硬匹配=1.0，fuzzy=0.6，inhibit=0.3（§0.2 软区间降权）

## 验证
- 后端 τ 属性隔离（TFIDF vs Embedding 不同阈值）✅
- zone 三档正确（0.9→precise / 0.4→fuzzy / 0.2→inhibit / 0→none）✅
- 实跑案例：
  - 「架构设计」sim=0.364 fuzzy（旧版 miss→现模糊召回）
  - 「七七吃苹果」sim=0.516 fuzzy（旧版 miss→现召回 sem_daily）
  - 「随机乱码」sim=0.314 inhibit（旧版丢弃→现抑制不丢）
- file_lint 0 error / 3 warn（已知冷归档旧裸名）

## 认知契约落地
"拒绝假精确，宁返回大致相关"已代码化：τ 硬阈值→软区间，模糊/抑制区保留低权召回而非空白失败。

## 备份
- `backup/topic_matrix.20260829_p04.bak`
