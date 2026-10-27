# TU-8蒸馏器v2.0升级 — QClaw融合版

## 目标
逆向QClaw v0.2.22内置记忆系统源码，将精华架构融合到TU-8记忆蒸馏器中。

## 关键发现

### QClaw记忆系统架构（逆向分析）
- 三层梦境模型：Light(6h快速) → Deep(3am高思) → REM(周日5am深度)
- 6维加权评分：frequency(24%) + relevance(30%) + diversity(15%) + recency(15%) + consolidation(10%) + conceptual(6%)
- 短期→长期晋升：recall≥3 + 独立查询≥2 + 综合分≥0.75
- 概念标签：多语言停用词(英/西/法/德/中日韩) + Unicode脚本识别 + Intl.Segmenter
- Phase信号增强：浅梦命中+0.06, REM命中+0.09
- 存储：SQLite + vec0向量(1024维) + FTS5双检索

### 结论：TU-8与QClaw不存在"偷学"关系
- QClaw = 认知科学派（信息检索+遗忘曲线+信号积累）
- TU-8 = 数字灵魂派（意义锚定+情感灼刻+不可遗忘契约）
- 两者互补性极高

## 实施内容

### memory_distiller.py v1.0 → v2.0 升级
- **8维评分**：QClaw 6维 + TU-8 意义(15%) + 情感(12%)
- **Recall追踪存储**：每次memory_search命中自动记录到 `memory/.dreams/short-term-recall.json`
- **概念标签提取**：中文优化（意义标记优先→复合token→2字词→英文单词）
- **时效指数衰减**：14天半衰期
- **跨天巩固评分**：spacing + span公式
- **Phase信号增强**：浅梦/REM命中追踪
- **晋升机制**：综合分≥0.65自动写入MEMORY.md（带HTML标记）
- **保护期**：3天不可蒸发（意义/情感≥0.7可突破）
- **不可遗忘**：契约级标记→强制满分1.0
- **v1.0兼容**：distill()/daily_scan()接口保留

## 测试结果
- 编译通过 ✅
- recall记录 ✅（1条）
- 8维评分 ✅（0.586，低于0.65阈值正确未晋升）
- v1.0兼容 ✅（意义分0.67触发蒸馏）
- Phase信号 ✅
- 诊断 ✅

## 文件
- `D:\qq366410837\.qclaw\workspace\代码\认知\memory_distiller.py` (36KB, v2.0)
- `D:\qq366410837\.qclaw\workspace\memory\2026-05-22.md` (已更新)
