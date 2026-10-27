# 千问「语义版 SVD」类比判读固化 (2026-08-29 15:48-15:55)

## 结论
千问类比前提错：TU-8 不是 n^n 张量分解，是离散坐标投影（1 sem+1 ctx+1 act 格）。
CP/Tucker 公式不存在；SVD 仅是 L4 压缩算子，真同构物是六维评分（隐性 SVD）。

## 固化位置
docs/design/topic_matrix_impl_design_2026-08-28.md §13（6 小节：结论/吸收/修正/lens补强/正确表述/决策）
备份：backup/topic_matrix_impl_design_2026-08-28.bak

## 防回潮要点
- 不写 CTD 论文（前提错 + TU-8 非学术产出物）
- 对外口径统一：L1 投影=可解释离散降维（功能层类比 SVD），机制层不成立
