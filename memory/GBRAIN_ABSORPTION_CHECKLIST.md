# GBrain 架构优点吸收清单

> 来源：GBrain（Garry Tan 开源项目）
> 研究时间：2026-06-28（首次）、2026-07-01（补充）
> 文档来源：GitHub raw CLAUDE.md + CSDN 深度解析

---

## 一、GBrain 是什么

**定义**：持续运行的 AI 智能体记忆操作系统，解决"每次对话从零开始"的健忘问题。

**定位**：
- RAG 胜在规模（百万文档级）
- LLM Wiki 胜在深度编译（百页级）
- **GBrain 胜在持续自动化运行（万页级）**

**核心理念**：知识应该被编译一次并保持最新，而不是在每次查询时重新推导。

---

## 二、核心架构优点

### 优点 1：双模存储（人类可读 + 机器优化）

| 层级 | 存储形式 | 目的 |
|------|---------|------|
| Brain Repo | Git 管理的 Markdown 文件 | 人类可读可编辑，版本可控 |
| GBrain Retrieval | SQLite（brain.db） | 机器优化查询，FTS5 + 向量 + 结构化 |

**吸收价值**：TU-8 当前只有 MEMORY.md + memory/*.md（人类可读），缺少机器优化的查询层。

---

### 优点 2：双列知识模型（已编译事实 + 时间线）

每个页面结构：
- **分隔线上方**：已编译事实（当前最佳理解，新证据出现时整体重写）
- **分隔线下方**：时间线（只追加，永不修改）

**吸收价值**：解决了"知识更新 vs 历史保留"的矛盾。

TU-8 当前只有时间线（memory/日期文件），缺少"已编译事实"层。

---

### 优点 3：自链接知识图谱（Self-Wiring Knowledge Graph）

| 功能 | 说明 |
|------|------|
| 实体提取 | 每次页面写入时零 LLM 调用提取实体引用 |
| 类型化链接 | attended、works_at、invested_in、founded、advises |
| 自动协调 | 编辑时移除内容中不再存在的链接 |
| 反向链接 | backlink-boosted ranking |

**基准数据**：
- Recall@5：83% → 95%（+11.5%）
- Precision@5：39% → 45%（+5.4%）
- works_at 精确率：21% → 94%（+73%）

**吸收价值**：TU-8 当前只有钢印链（因果关系），缺少实体关系图谱。

---

### 优点 4：混合搜索（关键词 + 向量 + RRF 融合）

```
查询 → 多查询扩展（Claude Haiku 改写）
     → 向量搜索（HNSW 余弦相似度）
     → 关键词搜索（tsvector）
     → RRF 融合排名
     → 四层去重
```

**吸收价值**：TU-8 当前只有 LCM（lossless-claw）的语义检索，缺少关键词搜索和融合排名。

---

### 优点 5：梦境循环（Dream Cycle）自动维护

21 个 cron 作业，智能体在"睡眠"时运行：

| 类型 | 功能 |
|------|------|
| 丰富化 | 分层丰富化（Tier 1/2/3），创建/更新人物/公司页面 |
| 查询 | 三层搜索 + 合成 + 引用 |
| 维护 | 陈旧页面、孤立页面、死链、引用审计、反向链接、标签一致性 |
| 引用修复 | 扫描缺失/畸形引用，修复格式 |

**吸收价值**：TU-8 有 Heartbeat（心跳巡检），但缺少"夜间梦境"的深度整合能力。

---

### 优点 6：两轴数据组织（Brain + Source）

| 轴 | 含义 | 路由方式 |
|------|------|---------|
| **Brain** | 哪个数据库 | `--brain`、`GBRAIN_BRAIN_ID`、`.gbrain-mount` |
| **Source** | 数据库内的哪个仓库 | `--source`、`GBRAIN_SOURCE`、`.gbrain-source` |

**吸收价值**：TU-8 当前只有单一 workspace，缺少多 brain / 多 source 的路由能力。

---

### 优点 7：信任边界设计（Trust Boundary）

```typescript
OperationContext.remote:
  - false → 本地 CLI 调用者（可信）
  - true → Agent-facing 调用者（不可信）
```

安全敏感操作（如 `file_upload`）在 `remote=true` 时收紧文件系统限制。

**吸收价值**：TU-8 有 L0 安全栅，但缺少细粒度的"操作级信任边界"。

---

### 优点 8：跨切面不变量（Cross-Cutting Invariants）

| 不变量 | 规则 |
|--------|------|
| Trust is fail-closed | 不严格 `false` 就视为不可信 |
| Source isolation | 每个读操作都路由到 sourceScopeOpts(ctx) |
| JSONB: never stringify | 不直接 JSON.stringify 到 ::jsonb |
| Engine parity | postgres-engine 和 pglite-engine 同步更新 |
| Contract-first | operations.ts 是唯一来源，CLI + MCP 从它生成 |

**吸收价值**：TU-8 有 SOUL.md（宪法），但缺少代码级的跨切面约束。

---

## 三、与 TU-8 的对比

| 维度 | TU-8 当前 | GBrain |
|------|----------|--------|
| 存储层 | MEMORY.md + memory/*.md（人类可读） | Markdown + SQLite 双模 |
| 知识模型 | 时间线（日记式） | 已编译事实 + 时间线（双列） |
| 关系图谱 | 钢印链（因果关系） | 实体关系图谱（多种类型化链接） |
| 检索能力 | LCM 语义检索 | 关键词 + 向量 + RRF 融合 |
| 维护机制 | Heartbeat（心跳巡检） | Dream Cycle（梦境循环） |
| 数据组织 | 单一 workspace | Brain + Source 两轴路由 |
| 信任边界 | L0 安全栅（粗粒度） | OperationContext.remote（操作级） |
| 跨切面约束 | SOUL.md（文档级） | 代码级跨切面不变量 |

---

## 四、吸收优先级

### 🔴 P0-High（立即吸收）

| 编号 | 吸收点 | 理由 |
|------|--------|------|
| A1 | 双列知识模型（已编译事实 + 时间线） | 解决知识更新与历史保留矛盾 |
| A2 | 梦境循环（Dream Cycle）自动维护 | 提升知识库自我维护能力 |

### 🟡 P1-Medium（近期吸收）

| 编号 | 吸收点 | 理由 |
|------|--------|------|
| B1 | 自链接知识图谱（实体关系） | 支持关系型查询 |
| B2 | 混合搜索（关键词 + 向量 + RRF） | 提升检索精度 |
| B3 | 两轴数据组织（Brain + Source） | 支持多知识库路由 |

### 🟢 P2-Low（长期吸收）

| 编号 | 吸收点 | 理由 |
|------|--------|------|
| C1 | 信任边界设计（操作级） | 细粒度安全控制 |
| C2 | 跨切面不变量（代码级） | 架构约束固化到代码 |

---

## 五、具体吸收方案

### A1：双列知识模型

**目标**：在 MEMORY.md 中实现"已编译事实 + 时间线"结构。

**实现路径**：
1. 定义 MEMORY.md 结构规范（分隔线 + 上方/下方）
2. 修改记忆写入逻辑（写入时区分"事实区"和"时间线区"）
3. 实现事实更新逻辑（新证据出现时整体重写上方区域）

### A2：梦境循环自动维护

**目标**：在 Dream Check cron 中增加深度整合能力。

**实现路径**：
1. 扩展 `dream_check_cron.py` 的功能
2. 增加"丰富化"步骤（实体识别 + 关系提取）
3. 增加"引用修复"步骤（扫描死链 + 修复格式）
4. 增加"矛盾检测"步骤（跨页面一致性检查）

---

## 六、风险与限制

### GBrain 的局限

1. **项目较新**（2026-04 发布），长期稳定性待验证
2. **企业级功能不足**（多用户协作、细粒度访问控制）
3. **生态不成熟**（与 LangChain/LlamaIndex 相比）

### 吸收风险

1. **过度工程化**：GBrain 是产品级系统，TU-8 是架构实验，盲目吸收会导致复杂性爆炸
2. **失去简洁性**：TU-8 的核心优势是极简，吸收时需权衡

---

## 七、参考文献

- GBrain GitHub: https://github.com/garrytan/gbrain
- GBrain CLAUDE.md: https://raw.githubusercontent.com/garrytan/gbrain/master/CLAUDE.md
- CSDN 深度解析: https://blog.csdn.net/m0_64363449/article/details/160444492
- Karpathy LLM Wiki: https://github.com/karpathy/llmwiki

---

## 八、最终定论（2026-07-01 16:26）

**GBrain = 记忆链的外部专业子库**

- **受调度链控制**：GBrain 的检索、丰富化、维护由调度链触发
- **受钢印链校验**：GBrain 的知识写入需经钢印链验证（保真度、source 验证）

**定位**：GBrain 不是 TU-8 的替代品，是记忆链的**外部专业子库**——类似大脑的"海马体→皮层"投射关系。

---

*⅋ 吸收清单 #001*
*生成于 2026-07-01 16:25*
