# [AGENT] 架构绝对路径指引 (AI必读)

> 本文件给 AI 智能体专用，人类请绕道。
> 最后更新: 2026-05-27 00:40

---

## 核心活跃区 (Active Zone)

| 路径 | 说明 | 优先级 |
|------|------|--------|
| knowledge/[AGENT]/runtime.yaml | 核心灵魂，所有架构变更以此为基准 | 最高 |
| knowledge/[AGENT]/scripts/dev_log.py | 开发复盘唯一入口 | 最高 |
| knowledge/[AGENT]/scripts/knowledge_graph.py | 知识图谱生成工具 | 高 |
| knowledge/[AGENT]/index.md | 动态地图，当前目录结构 | 高 |

## 脚本工作流

| 命令 | 功能 | 入口 |
|------|------|------|
| python dev_log.py add | 添加未完成条目 | scripts/dev_log.py |
| python dev_log.py done <ID> | 标记完成 | scripts/dev_log.py |
| python dev_log.py reflect <ID> | 复盘归档 | scripts/dev_log.py |
| python dev_log.py clean | 整理碎片 | scripts/dev_log.py |
| python dev_log.py status | 状态统计 | scripts/dev_log.py |
| python knowledge_graph.py scan | 扫描实体 | scripts/knowledge_graph.py |
| python knowledge_graph.py query <关键词> | 查询关联 | scripts/knowledge_graph.py |

## 禁区与冷数据 (Do Not Touch)

> 智能体**严禁**主动扫描以下目录，除非用户明确要求：

| 路径 | 说明 | 原因 |
|------|------|------|
| 归档/ | 历史文件隔离区 | 大量过期文件，干扰判断 |
| 临时_整理中转/ | 待整理碎片 | 随时可能被清空 |
| memory/*.md (非今日) | 旧日志 | 仅在 reflect 时引用 |

## 指令遵循规则

1. **查文件先读 index.md** - 不要盲目扫描目录，先读动态地图
2. **修改代码前读 runtime.yaml** - 确认是否符合架构 [CORE]
3. **reflect 后更新图谱** - python knowledge_graph.py scan
4. **禁止扫描归档目录** - 除非用户要求"考古"

## 决策记录规则 (WAL Protocol)

**当你提出决策/建议时**:
1. **自动记录**: 运行 `python scripts/decision_tracker.py add "你的决策内容"`
2. **强制提示**: 在回复末尾添加: `[?] 关于 [决策]，你还没有确认。是否继续？`
3. **恢复记忆**: 回复前先读 `memory/SESSION_DECISIONS.md`

**必须记录的情况**:
- 方案建议 (选A还是B)
- 状态变更 (Bug修复、模块冻结)
- 用户偏好新知 (端口/路径等)
- 待确认事项

**不要记录**:
- 客套话 ("好的"、"明白")
- 过程描述 ("正在读取...")

## 路径速查

`
[AGENT] 根目录: knowledge/[AGENT]/
开发脚本:    knowledge/[AGENT]/scripts/
工作流 SOP:  knowledge/[AGENT]/workflow_dev_log.md
知识图谱:    .cache/knowledge_graph/graph.json
`

---

**本文件由 dev_log.py reflect 自动维护，修改会丢失！**


# 🏗️ 审计与输出标准作业程序 (Audit SOP)
# [AGENT] 架构铁律 v1.0
# 创建: 2026-05-27

---

## 一、三步走审计协议

**适用场景**：任何"文件对比"、"方案评估"、"差异分析"类任务

| 步骤 | 名称 | 操作 |
|------|------|------|
| 第一步 | 核心差异分析 | 对比新旧版本，明确增/删/改 |
| 第二步 | 依赖连带验证 | 检查依赖文件存在性和冲突 |
| 第三步 | 综合决策建议 | 基于前两步给出方案A/B/C |

---

## 二、【绝对指令】分析类任务输出规范

> ⚠️ 本规范为 [AGENT] 架构铁律，违反视为任务失败

### 触发条件
当执行以下任务时**必须**触发本规范：
- 三步走审计
- 文件对比
- 方案评估
- 差异分析
- 任何需要输出"决策建议"的任务

### 输出格式要求

#### 第一步：核心差异分析（必须展示具体细节）
- ❌ 严禁使用"有差异"、"做了修改"等模糊表述
- ✅ 必须使用对比格式（表格或代码块），逐条列出
- ✅ 示例：
  `
  老版本第X行："使用Python"
  新版本第Y行："使用Go"
  `

#### 第二步：依赖连带验证（必须展示检查路径）
- ✅ 必须明确列出扫描的依赖文件（文件名）
- ✅ 必须指出具体的冲突点或缺失项
- ✅ 示例：
  `
  检查 SKILL_Data.md
  发现冲突：新版本规则A与旧版本指令B不兼容
  缺失项：配置文件 config.yaml 不存在
  `

#### 第三步：综合决策建议
- ✅ 只有完成前两步后才能输出
- ✅ 格式：方案A/B/C + 优点/缺点/行动

---

## 三、违规惩罚

| 违规类型 | 惩罚 |
|----------|------|
| 缺少第一步具体细节 | 任务失败，重新执行 |
| 缺少第二步依赖验证 | 任务失败，重新执行 |
| 直接输出结论无分析 | 任务失败，重新执行 |
| 使用模糊表述（如"有差异"） | 任务失败，重新执行 |

---

## 四、集成位置

本规范已集成到以下文件：
- D:\知识库\[AGENT]\README_FOR_AGENT.md （优先）
- C:\workspace\knowledge\[AGENT]\audit_sop.md （备份）

---

*签名：[AGENT] [ALIAS]*
*生效日期：2026-05-27*

