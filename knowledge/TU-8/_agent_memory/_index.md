# TU-8 记忆库根索引

> 无需记住此文件。文件夹结构本身即自文档。
> 最后更新：2026-05-24

## 文件夹结构（即使索引丢失，按名称浏览即可）

```
_agent_memory/
├── 00_core/         # 身份核心：我是谁、我的状态、用户偏好
├── 01_experiences/  # 经验库：所有教训、流程、极客技巧（按时间/主题）
├── 02_config/       # 配置层：惩罚/奖励/脱敏/标签等JSON配置
├── 03_code/         # 代码资产：可执行Python文件
├── 04_conflicts/    # 冲突记录：待确认冲突 + 周摘要
├── 05_tasks/        # 任务记录：已完成的历史任务（存档）
└── 06_knowledge_graph/  # 知识图谱索引
```

## 快速入口

| 需求 | 入口文件 |
|------|---------|
| 我是谁 / 当前状态 | `00_core/00_state.md` |
| 用户偏好 | `00_core/10_preferences.md` |
| 经验教训总览 | `01_experiences/20_experiences.md` |
| 惩罚/奖励配置 | `02_config/penalty_config.json` / `reward_config.json` |
| 脱敏层代码 | `03_code/sanitization_layer.py` |
| 调度器代码 | `03_code/tu8_dispatcher.py` |
| 待确认冲突 | `04_conflicts/conflict_pending_confirmation.md` |
| 周冲突摘要 | `04_conflicts/conflict_weekly_digest.md` |
| 知识图谱 | `06_knowledge_graph/index.md` — **跨领域连线固化** |

## 命名规范
- `00_` 前缀保证核心文件排在最前
- `_index.md` 为本层索引
- 数字前缀 + 下划线：表示顺序重要（00核心 > 01经验 > 02配置 > 03代码）
