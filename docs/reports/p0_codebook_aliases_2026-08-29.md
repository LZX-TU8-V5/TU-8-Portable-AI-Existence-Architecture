# P0 #3 Codebook 别名归并 + 自动轴分布（2026-08-29）

## 目标
认知契约 §0.1「允许记忆融合」+ §0.5「显式纠偏穿透」代码落地：同义异构（我妈/母亲/老太太）归并同一 sym，axis_weights 运行时反推非手填。

## 改动（src/codebook.py）
- `register(label, event_id, aliases=None)`：新增 aliases 字段
- `merge_alias(sym, alias)`：同义表述并入已有 sym（吸收独立 sym 的 weights/aliases）；§0.5 显式纠偏穿透接口
- `update_axis_weights(sym, coord, weight)`：distill 写段 coord 后反推 sym 轴分布（§1.8 涌现非手写）
- `_merge_weights`：平滑合并（加权平均）
- `resolve_by_alias(text)`：模糊检索（alias/label→sym）

## 验证
- aliases 归并：母亲 sym 含 ['我妈','老太太','我妈独立'] ✅
- 自动 axis_weights：sem_daily/ctx_personal/act_recall 从 3 次段 coord 反推涌现 ✅
- resolve_by_alias：'老太太'/'母亲' 均命中 sym_母亲 ✅
- file_lint 0 error

## 认知契约落地
"允许记忆融合"代码化：同义异构自然归并，不分裂；axis_weights 从行为浮现非配置（呼应 L0 不手写铁律）。

## 备份
- backup/codebook.20260829_p03.bak
