# 文件治理 Phase A 落地报告（2026-08-27 17:06）

> 造物主 17:04 选 A：修正 GOVERNANCE + 落位纪律入 AGENTS.md 铁律 + P0 总备份。
> 本阶段为"分析+规范+安全锚点"，**未位移任何业务文件**（仅新增/修正 2 个规范文档 + 1 个备份目录）。

## 一、五边界分析结论（决定合并策略）
| 边界 | 结论 | 动作 |
|------|------|------|
| ① 小说/ | **保留中文名原位** | GOVERNANCE §1 改 `小说/` 非 `novel/` |
| ② 知识库三目录 | **不硬合并**（knowledge199/knowledge_base152/知识库7 是不同层，仅 4 同名且 3 为旧备份） | 保留三目录；低优先清 1 个真重复 |
| ③ backup 快照 | **不泛滥不清零**（实际 15 个 .bak + 4 套模块自动快照是系统预期行为） | 并入 `backup/auto_/`，作回滚锚点 |
| ④ .node.md | **13 个被引用者留根**（Gateway 启动加载项）；10 个未引用者移 `docs/architecture/` | 禁止移动被引用者 |
| ⑤ 用户/ | **保留原位**（运行时状态 JSON，与 USER.md 散文互补，改名断路径） | GOVERNANCE 原"合并"判断撤销 |

## 二、纠正：backup "1204" 是统计口径错误
原 survey 用 `rglob("*")` 把 `backup/` 嵌套子目录全数了 → 误报 1204。实际 `backup/` 仅 **15 个 .bak**（手动规范命名）。其他 4 套（backups/.arch_backups/.arch_recycle_bin/_snapshots）是 arch_fsm/consciousness_cycle 等改前自动留底，属预期，非泛滥。

## 三、GOVERNANCE.md 修正
- §1 目录结构图：改为修正版（小说保留、知识库三目录并存、用户/保留、backup/auto_ 子目录、.node.md 13 留根）
- §4 边界：5 条全部由"待定"改为"已分析→结论"
- P0 段标注已完成

## 四、AGENTS.md 新增铁律五「文件落位纪律」（P0 级）
6 条强约束：新 md 进 docs//memory/、新 py 进 src/tools、状态 JSON 进 _agent_memory/用户/、备份单通道、待办单真源 TODO_MASTER、不得移动启动加载项。违反=P0 失误。
→ **这是防再乱的根本机制**，后续新文件自动归位。

## 五、P0 总备份（安全锚点）
- 路径：`_GOV_ARCHIVE_20260827_170629/`
- 内容：workspace 全量（排除 .git/__pycache__/.pytest_cache/.cache 瞬态 + 清理 .pyc）= **4566 有效文件**
- 一致性校验：OK（源缺 1=运行期脚本自身，多 2=锚点/备份脚本，均预期）
- 回滚锚点：`_GOV_ARCHIVE_20260827_170629/_ROLLBACK_ANCHOR.txt`

## 六、下一步（待造物主确认进 P1）
P1 = 根目录非破坏分流（身份层留根，其余按 docs/{design,reports,tasks,emergence,architecture}/ 移动）+ 10 个未引用 .node.md 移 docs/architecture/ + SOUL 旧版（SOUL.v2.1/SOUL_v2）移 docs/architecture/。
所有移动走 trash 可恢复，每步可回滚。

## 七、技术坑记录
- 备份校验脚本自指 bug：源排除 `_GOV_ARCHIVE_*` 但 dst 递归含自身 → 假"缺 4568"。修正为双向排除自身目录后一致。
- `knowledge/TU-8/` 下藏整棵 `__pycache__`+`_agent_memory/` 嵌套子树（584 垃圾文件），备份时已清理 .pyc。
