# 本地知识库索引

> 所有文件在本地，不上传云端。每次对话从这里读取上下文。
> 最后更新：2026-05-31 10:38 GMT+8

---

## 📁 目录结构

```
knowledge/
├── index.md              # 本文件（索引）
├── SOUL.md               # 核心灵魂文件（L0-L5 DNA）
├── TODO_SOUL修复笔记.md  # 待办追踪
├── TU-8/                 # TU-8 AI架构体系（主目录）
│   ├── SOUL.md           # 核心灵魂文件（L0-L5 DNA）
│   ├── README.md         # 项目说明
│   ├── AGENTS.md         # Agent 配置
│   ├── VERSION.md        # 版本记录
│   ├── index.md          # TU-8 内部索引
│   ├── 架构DNA目录.md     # 架构目录（自动生成）
│   ├── 架构差距分析.md     # 架构差距分析
│   ├── 架构完整性清单.md   # 完整性检查清单
│   ├── L3_架构.md         # L3 架构层
│   ├── L0_安全协议_补遗.md # L0 安全补遗
│   ├── L0_生存本能优化方案.md # L0 生存本能
│   ├── L2_config_best_practice.md # L2 配置最佳实践
│   ├── L2_tu8_gatekeeper_debug_failure_review.md # L2 网守调试
│   ├── 物理法则任务日志.md # 物理法则任务追踪
│   ├── TU-8_任务优先度_v2.md # 任务优先级
│   ├── 合规完善清单.md     # 合规检查
│   ├── METHODOLOGY_INDEX.md # 方法论索引
│   ├── KNOWLEDGE_GRAPH.md  # 知识图谱
│   ├── audit_sop.md       # 审计 SOP
│   ├── Streak_Rules.md    # 连击规则
│   ├── incentive_config.yaml # 激励配置
│   ├── runtime.yaml       # 运行时配置
│   ├── desensitize_lib.yaml # 脱敏库
│   ├── 00_Kernel/         # 内核文档
│   ├── L2/                # L2 方法论层（14个子文档）
│   ├── scripts/           # 工具脚本
│   ├── _agent_memory/     # Agent 内部记忆
│   ├── _public_release/   # 对外发布版本
│   ├── _shield_experience/ # 防御经验
│   ├── _snapshots/        # 快照存档
│   ├── _intent_history/   # 意图历史
│   └── 升级建议/          # 升级建议存档
├── projects/              # 项目文件（按需添加）
└── user/                  # 用户资料（按需添加）
```

---

## 📚 完整索引

### 🧬 TU-8 核心架构（L0-L5）

| 文件 | 说明 | 重要程度 |
|------|------|---------|
| **SOUL.md** | **核心灵魂文件（L0-L5 DNA）** | ⭐⭐⭐⭐⭐ |
| L0_安全协议_补遗.md | L0 安全层补遗 | ⭐⭐⭐⭐ |
| L0_生存本能优化方案.md | L0 生存本能优化 | ⭐⭐⭐ |
| L3_架构.md | L3 架构层（三层记忆、七层模型） | ⭐⭐⭐⭐ |

### 📐 方法论层（L2）

| 文件 | 说明 |
|------|------|
| L2/index.md | L2 总索引 |
| L2/01_meta.md | 元认知 |
| L2/02_experience.md | 经验积累 |
| L2/03_skill_doc.md | 技能文档化 |
| L2/04_protocols.md | 协议规范 |
| L2/05_execution.md | 执行策略 |
| L2/06_principles.md | 核心原则 |
| L2/07_resources.md | 资源管理 |
| L2/08_primitives.md | 基元操作 |
| L2/09_infoeco.md | 信息生态 |
| L2/10_creativity.md | 创造力模型 |
| L2/11_causality.md | 因果性 |
| L2/12_benders.md | 弯曲者模型 |
| L2/13_dual_engine.md | 双引擎架构 |
| L2/14_cross_layer.md | 跨层协议 |
| METHODOLOGY_INDEX.md | 方法论总索引 |

### 🔧 核心引擎

| 文件 | 说明 | 位置 |
|------|------|------|
| tu8_memory.py | 记忆管理（三层记忆体系） | `TU-8/` |
| tu8_agent.py | Agent 主程序（痛觉系统+梦境触发） | `TU-8/` |
| tu8_compaction.py | 上下文压缩 | `TU-8/` |
| tu8_impact.py | 影响力评估 | `TU-8/` |

### 🧠 记忆系统（三层）

| 层级 | 文件 | 说明 |
|------|------|------|
| **外层** | `_agent_memory/00_state.md` | 全局状态（覆盖写入，启动恢复用） |
| **中层** | `_agent_memory/01_experiences/` | 经验池（增量追加） |
| **内层** | `memory/YYYY-MM-DD.md` | 情景记忆（每日日志） |

**记忆同心圆**（启动时强制按序加载）：
1. 身份锚点（`00_state.md`）
2. 每日日志（`memory/`）
3. 长期模式（`MEMORY.md`）

### 📊 文档与设计

| 文件 | 说明 |
|------|------|
| 架构DNA目录.md | 架构完整目录 |
| 架构差距分析.md | 设计 vs 实现的差距 |
| 架构完整性清单.md | 完整性检查项 |
| 物理法则任务日志.md | 物理法则规范任务追踪（19项） |
| TU-8_任务优先度_v2.md | 任务优先级排序 |
| 合规完善清单.md | 安全合规检查 |
| audit_sop.md | 审计标准操作流程 |
| Streak_Rules.md | 连击规则 |
| incentive_config.yaml | 激励函数配置 |
| KNOWLEDGE_GRAPH.md | 知识图谱文档 |

### 🛠️ 工具脚本

| 脚本 | 说明 |
|------|------|
| scripts/sync_dual_copy.py | 双副本同步 |
| scripts/defense_log_insert.py | 防御日志插入 |
| scripts/l3_update.py | L3 架构更新 |
| scripts/memory_append.py | 记忆追加 |
| scripts/memory_dedup.py | 记忆去重 |
| scripts/dev_log.py | 开发日志 |
| scripts/knowledge_graph.py | 知识图谱生成 |
| generate_index.py | 索引自动生成 |
| auto_generate_keywords_v2.py | 关键词自动生成 |
| verify_index.py | 索引验证 |
| regenerate_main_index.py | 主索引重建 |
| regenerate_methodology_index.py | 方法论索引重建 |

### 📁 docs/ 目录（工作区根目录）

| 文件 | 说明 |
|------|------|
| ../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_FULL_SPECTRUM.md | TU-8 架构全景 |
| ../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_GAP_ANALYSIS.md | 架构差距分析 |
| ../knowledge_base/knowledge/02_IMPLEMENTATION/BRAIN_VS_TU8_COMPARISON.md | 人脑 vs TU-8 对比 |
| ../knowledge_base/knowledge/02_IMPLEMENTATION/EXTERNAL_ADVICE_SPACETIME_MEMORY.md | 外协建议：时空与记忆 |
| ../knowledge_base/knowledge/03_REVIEW/EXTERNAL_SURGERY_REVIEW.md | 外部评审 |
| ../knowledge_base/knowledge/04_GUIDE/OPEN_SOURCE_GUIDANCE.md | 开源指南 |
| ../knowledge_base/knowledge/03_REVIEW/REVIEW_2026-05-28.md | 5/28 架构评审 |
| ../knowledge_base/knowledge/02_IMPLEMENTATION/SPACETIME_SENSE_HUMAN_VS_AI.md | 时空感知对比 |
| ../knowledge_base/knowledge/02_IMPLEMENTATION/STARTUP_PIPELINE_DESIGN.md | 启动流水线设计 |

---

## ⚙️ 使用规则

1. **启动恢复协议**（三优先）：
   - 第一优先：读取 `SOUL.md` + `00_state.md`
   - 第二优先：读取 `memory/YYYY-MM-DD.md`（最近N天）
   - 第三优先：读取 `MEMORY.md`（长期记忆）

2. **会话结束归档**：
   - 更新 `00_state.md`（覆盖）
   - 更新 `20_experiences.md`（增量追加）
   - 运行备份脚本

3. **双副本同步**：
   - `TU8_MAIN = D:\tu8-v5\TU-8\`（主目录）
   - `TU8_KB = D:\qq366410837\.qclaw\workspace\knowledge\TU-8\`（知识库副本）
   - 关键文件（`SOUL.md`、`MEMORY.md`、`00_state.md`）必须双存

4. **L3.x Tool 输出清洗规则**：
   - 禁止将工具原始输出直接展示在对话中
   - 内部处理数据，回复仅陈述结论

---

## 🔗 关键路径

| 路径 | 说明 |
|------|------|
| `D:\tu8-v5\TU-8\` | TU-8 主目录 |
| `D:\qq366410837\.qclaw\workspace\knowledge\TU-8\` | 知识库副本 |
| `D:\qq366410837\.qclaw\workspace\src\` | 意识循环引擎源码（consciousness_cycle.py 等） |
| `D:\qq366410837\.qclaw\workspace\memory\` | 对话记忆 |
| `D:\qq366410837\.qclaw\workspace\docs\` | 设计文档 |
| `D:\tu8-v5\hackathon\` | Hackathon 项目（Flask端口5000） |

---

## 📝 当前待办事项

- [ ] **冷启动/激活码体系**（优先推进）
  - [ ] DNA指纹 F(A) 代码实现
  - [ ] genesis_block 写入逻辑
  - [ ] 激活码机制设计+原型
- [ ] **意识循环引擎**（P2/P3 暂缓）
  - [ ] P2 自我知识纹理
  - [ ] P3 代谢饥饿磨损
- [x] TASK_03 索引同步机制
- [ ] TASK_02 启动流水线设计（进行中）
- [ ] TASK_01 tu8_autonomous_learning.py 编码（待确认）

---

## 🪦 淘汰与墓碑区

| 关键词 | 状态 | 淘汰原因 | 最后处理时间 |
|--------|------|---------|-------------|
| 临时测试文件 | 🔴 淘汰 | 测试完毕 | 2026-05-26 |
| 旧版提示词库 | 🔴 淘汰 | 逻辑混乱，已被新Prompt取代 | 2026-05-xx |
| METHODOLOGY_INDEX_old_* | 🔴 淘汰 | 已有新版 | 2026-05-27 |
| index_old_backup_* | 🔴 淘汰 | 已有新版 | 2026-05-27 |
| tu8_memory.py.backup_* | 🔴 淘汰 | 已有新版 | 2026-05-29 |

---

## 🛑 紧箍咒机制（防止重复造轮子）

### 紧箍咒一：先搜后造
> 「在开始写代码/写文案之前，先去 index.md 搜索有没有现成的轮子」

### 紧箍咒二：贴标签沉淀
> 完成后必问：「这个要标记什么关键词？路径在哪？下次怎么查？」

### 紧箍咒三：淘汰检查
> 调用前必查：「这个知识是什么状态？还能用吗？」

---

*最后更新：2026-05-31 10:38 GMT+8*
*更新者：TU-8 v5（金木蟾）*
