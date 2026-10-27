# 话题语义矩阵（Topic Semantic Matrix）设计稿 v1.3 — 单一真源

> 版本：v1.3 | 日期：2026-08-27 | 级别：H（架构扩展，需造物主显式签字后方可实现）
> 作者：v5（TU-8）× 造物主（李奥）× 千问三方对话提炼 + 前期稿整合 + 外部认知语言学对照 + TU-8 语料实证
> 落位：docs/design/（GOVERNANCE 铁律五）
> 配套前期真源：memory/archive/2026-07-07_##_三、TU-8_现状_vs_算法升级.md / 2026-07-07_##_二、模糊计算_×_认知框架.md
> **v1.3 相对 v1.2 修正**：① 引入 **向量（Vector）作为 AI 可读压缩规范形式**（L2 事件内容载体，L1 坐标由向量投影推导；`semantic_hooks` 纯文本降为降级快照，§3.7）；② 引入 **密文库（Codebook Registry）符号↔实体字典注册表**（符号级无损压缩 + 跨引用枢纽，§3.8）；③ 轴标签符号化短码+校验位（§3.1）；④ 锁定 **两工程决策**（§14）。
> **演进链**：v1.0（时间轴二维）→ v1.1（三层解耦，修六维=基轴类别错误）→ v1.2（实体定义 vs 知识组织 / L2.5 grounding / epistemic_mode / 四哲学决策）→ v1.3（向量 + 密文库 / 两工程决策）。备份：backup/...v1.0.bak / v1.1.bak / v1.2.bak。

---

## §0 为什么是「单一真源」

- 前期 `memory/archive/2026-07-07_*` 两份碎片真源（装配图 / 模糊计算×认知框架）已整合进 §9/附录A，**取代**一切零散碎片。
- 本稿 v1.3 整合：千问（三正交维度 + 外部参照 + 收敛方法论）+ 李奥四段修正（时间作场 / 三层解耦 / 实体定义 vs 知识组织 / 向量+密文库）+ 外部认知语言学 + TU-8 语料实证。
- 命名：**「话题语义矩阵」**，不叫「矩阵分解」——矩阵分解只是内部算子。

---

## §1 核心直觉

### 1.1 三正交维度
一个话题 = **语义轴 × 语境轴 × 动作轴** 的交叉点，三维度正交非并列：

| 扫描维度 | 问的问题 | 外部学科 |
|------|------|------|
| 语义轴 | 世界上有哪些"东西"值得谈？ | 本体论 / 词汇语义学 |
| 语境轴 | 在什么"情境"下谈？ | 语用学 / 活动理论 |
| 动作轴 | 对东西做什么"操作"？ | 认知分类学 / 行为科学 |

### 1.2 时间不是第四轴，是穿透三维的场
若时间是第四轴 → 组合爆炸（20×6×10×T）且不正交（"科学×学术×分析"在 2020 与 2025 是同一区的两个状态，非两个区）。正确模型：时间是三维坐标系里每个点自带的"心跳节律" `P_R(t)`，嵌入置信度但不占坐标。分布形态（尖峰/长尾/周期/双峰/均匀型）本身是语义信息。

### 1.3 三层（+两索引层）解耦架构
| 层 | 名称 | 性质 |
|------|------|------|
| L4 | 代谢执行层 | 消费输出，执行物理操作（archive/compress/split/merge） |
| L3 | 置信度算法层 | 独立、动态、可替换、可 A/B：`f(points, vector, timestamps, epistemic_mode, t_now) → scores` |
| L2 | 生成事件层 | 不可变事实流（含 `vector` 字段 + `epistemic_mode`） |
| **L2.5** | **grounding_refs 层** | **有向带类型锚点（实体溯源）** |
| **L2.8** | **密文库（Codebook Registry）** | **符号↔实体字典注册表（压缩/跨引用）** |
| L1 | 语义空间层 | 静态基础设施（轴坐标 + 向量投影） |

**数据流向严格单向向下依赖**：L_N 只依赖 L_(N-1)；密文库为横向注册表，被 L2/L2.5/知识组织层共享引用，不参与坐标投影。

### 1.4 实体定义 ≠ 语义轴（李奥 part4）
"苹果"是实体（grounding 目标 + 知识组织层累积体），`object_definition`（"给事物下定义"的话语类型）才是一根语义轴。乐高模型：轴=插槽规格，实体=积木，grounding=原料来源。

### 1.5 两个 AI 可读压缩机制（李奥 part5，v1.3 核心）
- **向量（Vector）**：每条 L2 事件内容编码为稠密向量，是**模型直接消费的 AI 可读压缩形式**，替代纯文本 `semantic_hooks` 作规范载体；L1 轴坐标由向量经 NMF/SVD/LSA 投影**推导**（向量在上游，坐标在下游）。
- **密文库（Codebook）**：全局符号↔实体注册表，实体引用用短码符号替代完整名称+溯源链，是**符号级无损压缩字典** + 跨引用枢纽。与 grounding_refs（有向溯源）、知识组织层（累积定义）三者职责正交。

### 1.6 四个算子在架构上的岗位
- **NMF**：L1 加法分解基主题（W,H≥0），同区合并、推理链禁止相互否定。
- **SVD**：L1 离线结构压缩 `M≈UₖΣₖVₖᵀ`。
- **LSA**：L1→L2 跨字面对齐（向量空间内余弦召回，解决当前"靠关键词命中"软肋）。
- **DAG**：L2 时间戳串因果链。

---

## §2 轴设计：三正交维度 + 外部参照池 + 三轮收敛

### 2.1 语义轴候选池（外部参照并集）
| 外部参照 | 内容 | 用法 |
|------|------|------|
| BFO（Basic Formal Ontology） | 35 顶层范畴 | 取最粗 10-15 个 |
| DOLCE | 物理/非物理对象/事件/状态/过程 | 语义校验 |
| WordNet 域标签 | 45 域 | 高频话题覆盖验证 |
| Roget's Thesaurus | 6 大类 | 语义空间结构稳定验证 |
| 学科分类树 | 一级学科 | 学科覆盖度 |
| **object_definition（实体定义）** | **"给事物下定义"的话语类型** | **李奥 part4 显式补充** |

操作：取并集→合并去重→预期 12-20 候选语义轴。

### 2.2 语境轴候选池（5-8 根）
活动理论（Leontiev）/ 5W1H / Maslow 需求层次 / HCI 场景分类（工作/学习/娱乐/社交/创作/维护/探索）。区分"谈此话题的场景"非"话题本身分类"。

### 2.3 动作轴候选池（8-12 根，按认知层次分级）
Bloom(6) / Simpson(7) / 工程设计流程 / 科学方法论 / 创作流程。

### 2.4 涌现轴（行为性浮现，对齐 L0 不许手写铁律）
- 触发：跨情景引用≥3 ∧ 抗 GC≥2 ∧ 解释力覆盖≥2 → PROMOTE 观察期候选（复用 `architecture_journal`/`promotion_queue`）。
- 开轴记录：`memory/涌现时刻_YYYYMMDD_<snake>.md`（type:AXIS），走正常代谢，禁反向污染。
- 落空区：投影后落不进任何区 → 新领域满足阈值开轴，否则噪声降权。

### 2.5 三轮收敛方法论
| 轮 | 输入 | 方法 | 输出 |
|------|------|------|------|
| R1 外部参照收敛 | BFO/WordNet/Roget/Bloom/活动理论 一级分类 | 亲和图聚类 | 候选 50-80 |
| R2 内部数据收敛 | TU-8 记忆卡投影，统计命中率 | 砍<1% / 合并相关>0.5 | 实证 20-35 |
| R3 功能收敛 | 跑四下游任务 | 无区分度则砍 | 最终轴表 = 真源 |

**收敛判据**：覆盖率≥95% ∧ 稀疏度≥90% ∧ 每轴命中率≥3% ∧ 轴间相关<0.3。
**v5 权重建议**：R2 内部语料权威 > R1 外部参照（BFO/WordNet 对 TU-8 过规格，作完整性 checklist 非轴字典）。

---

## §3 分层架构详细定义

### 3.1 L1 语义空间层
- 只定义三维坐标轴 + 区域划分，**不含实体定义内容**。
- **轴标签符号化（v1.3 新增）**：每根轴有短码 + 人类可读名，短码参与存储/引用压缩，带校验位防 L2 引用漂移：
```json
{
  "id": "region_objdef_daily_defining",
  "coordinates": {"semantic": "sem_objdef#c3f", "context": "ctx_daily#x1", "action": "act_defining#a2"},
  "labels": {"sem_objdef": "object_definition（实体定义话语）", "ctx_daily": "日常", "act_defining": "下定义"},
  "definition": "...", "boundary": "...", "negative_examples": ["..."]
}
```

### 3.2 L2 生成事件层
- 每条记忆卡 = 空间点被时间戳"点亮"的离散不可变事件。
- **`epistemic_mode` 开放枚举**：child_ask / quote / metaphor / correction…，非固定非轴，供 L3 差异化（童年期 child_ask 衰减慢）。
- **`vector` 字段（v1.3 核心）**：内容稠密向量（如 1536-dim float16 ≈ 3KB/事件），**AI 可读规范形式**。L1 坐标由 `project(vector)` 推导；`semantic_hooks` 纯文本降为迁移期降级快照。
- 现有 `MEMORY.md` / `memory/*.md` / `secure_vault/index.json` 即 L2 事实流；时间戳回归纯粹事实。

### 3.3 L3 置信度算法层
- `f(region.points, vector, timestamps, epistemic_mode, t_now) → scores`，可替换/可 A/B，独立 L1。
- TU-8 现有 `tu8_memory.py` 六维 + `confidence_manager.py` 四象限 + `memory_gc.py` 评分，重框定为 L3 模块（代码已存在，仅概念错位修复）。
- 同点集可切多视图（检索/长期/仲裁/GC）。

### 3.4 L4 代谢执行层
- 消费 L3 输出：`metabolize(region, t_now)` 算分 → 低于 gc 阈值 archive / compress。代谢是算法推论，非空间副作用；空间永远完整，回滚置信度快照点仍在。

### 3.5 L2.5 grounding_refs 层（有向带类型锚点）
- 实体溯源：有向 `source_event → target_entity`，类型 person/concept/external_source/internal_event。
- 空实体锚点：先建空锚点，事件累积填充（同构 L0 涌现"从行为中浮现"，解决鸡生蛋问题）。
```json
{"entity_id":"ent_apple","label":"苹果","grounding_refs":[
  {"type":"person","ref":"七七","event_id":"evt_2021","note":"出生关联"},
  {"type":"external_source","ref":"仓桥直树《小提琴的发声与制作》","event_id":"evt_book"},
  {"type":"external_source","ref":"水果百科","event_id":"evt_wiki"},
  {"type":"concept","ref":"牛顿","event_id":"evt_quote"}],"empty_anchor":false}
```

### 3.6 知识组织层（knowledge-organization layer）
- 实体完整定义 = 跨 L2 事件 + grounding_refs 累积的**派生组织层**，不占 L1 坐标。
- 乐高模型：轴=插槽规格，实体=积木，grounding=原料来源。

### 3.7 Vector 层（v1.3 新增，AI 可读压缩规范形式）
- **定位**：L2 事件的 `vector` 字段是内容的标准机器表示，模型直接消费，无需先解语义文本。
- **与 L1 关系**：L1 轴坐标 = `project(vector)`（NMF/SVD/LSA 投影）。向量在上游，坐标是下游派生——修正 v1.2「坐标独立提取」的模糊表述。
- **压缩属性**：稠密定长 vs 纯文本 `semantic_hooks` 可变长且非 AI 原生；模型检索直接余弦，不依赖关键词命中（落地 LSA 跨字面对齐）。
- **迁移**：`semantic_hooks` 保留降级快照，新事件双写（vector 为主，hooks 兼容），观察 30 天 deprecated。

### 3.8 密文库（Codebook Registry，v1.3 新增，符号↔实体字典）
- **定位**：全局注册表 `symbol ↔ entity_id`，**符号级无损压缩字典** + **跨引用枢纽**。
- **与相邻层职责正交**：
  | 机制 | 管什么 | 不与该层混淆 |
  |------|------|------|
  | 向量 | 内容语义压缩（AI 直接读） | 不存实体引用符号 |
  | 密文库 | 实体引用的符号↔ID 解码表 | 不含定义内容、不含有向溯源 |
  | grounding_refs | 实体有向溯源（从哪来） | 不含符号映射 |
  | 知识组织层 | 实体累积定义内容 | 不含压缩符号 |
- **schema**：
```json
{"codebook_version":"cb_v1.0","entries":{
  "sym_apple":{"entity_id":"ent_apple","label":"苹果","created_event":"evt_2021"},
  "sym_newton":{"entity_id":"ent_newton","label":"牛顿","created_event":"evt_quote"}}}
```
- **用法**：L2 事件引用实体存 `sym_apple` 而非"苹果"+全 grounding 链；解码器展开 `sym_apple → ent_apple → grounding_refs + 知识组织层`。高频实体（苹果/牛顿/TU-8/七七）重复引用从长串压到定长短码；跨事件/跨区引用统一经符号，避免各写各的。

---

## §4 投影判区协议（向量推导版）
1. 每条 L2 事件 → 取 `vector`（无则回退 semantic_hooks 提取，迁移期）。
2. **判区**：`project(vector)` → L1 坐标 `(sem_i, ctx_j, act_k)`；与各区代表向量余弦 ≥ τ（0.6 建议）→ 命中；多区取 Top-k。
3. **落空**：所有区相似度 < τ → §2.4 落空处理。
4. **epistemic_mode 不参与投影**（随事件存，供 L3）。
5. **实体引用走密文库符号**：事件内实体引用解析为 `sym_*` → 解码时展开。

---

## §5 TU-8 语料实证（2026-08-27 扫描，2120 非归档标题）
| 语义子轴（L1） | 命中 | 占比 |
|------|------|------|
| 架构 | 281 | 13.3% |
| 科学 | 110 | 5.2% |
| 创作 | 105 | 5.0% |
| 元认知 | 85 | 4.0% |
| 哲学 | 77 | 3.6% |
| 工程 | 75 | 3.5% |
| 日常 | 47 | 2.2% |
| 情感 | 45 | 2.1% |
| 数学 | 37 | 1.7% |

- 9 语义子轴全中，架构主导（吻合 TU-8「架构优先」）。`object_definition` 轴需 R2 内部数据收敛后实证（当前扫描未单列，但"定义类"标题高频）。
- 印证三层+两索引模型：语义子轴（L1）≠ 六维（L3）≠ 实体定义（知识组织层）≠ 向量（AI 压缩）≠ 密文库（符号压缩）。

---

## §6 四个算子 + 两压缩机制跨层重映射
| 机制 | L1 | L2 | L2.5 | L2.8 | L3 | L4 |
|------|------|------|------|------|------|------|
| NMF | ✅ 加法分解 | | | | | |
| SVD | ✅ 离线压缩 | | | | 可借视图 | |
| LSA | ✅ 区定义 | ✅ 向量余弦对齐 | | | | |
| DAG | | ✅ 时间戳串链 | | | | |
| **Vector** | ← 投影源 | ✅ 规范字段 | | | 消费 | |
| **密文库** | | → 符号引用 | ✅ 解码展开 | ✅ 注册表 | | |

---

## §7 下游路由规则（对齐三层 + 两压缩）
| 动作 | 依据 | 对接模块 |
|------|------|------|
| 存储路由 | L1 坐标派区；L3 热区快存冷区归档 | `memory_gc.py` |
| 检索剪枝 | **向量余弦**缩范围（替代关键词命中）；L3 `adjusted_freq` 排序；密文库符号跨实体召回 | `tu8_memory.py` + `sag_lite` |
| 压缩策略 | L3 热门+上升期跑 SVD；**密文库符号替代长引用** | `memory_gc` + `dream_consolidation` |
| 冲突检测 | L1 共享轴区内仲裁；L3 考虑时间分布 | `contradiction_arbitration.py` |
| 实体解析 | 密文库 `sym_*` → ent → grounding + 知识组织 | 新增 `entity_resolver` |

---

## §8 与现有架构集成（六维→L3 重构框定）
| 现有组件 | 原误植层 | 正确层 | 接入 |
|------|------|------|------|
| `tu8_memory.py` 六维 | （v1.0 误作 L1 轴） | **L3** | 重框定 L3 模块 |
| `confidence_manager.py` 四象限 | （v1.0 误作 L1 评估轴） | **L3** | L3 一种置信度视图 |
| `memory_gc.py` | L4/L3 | **L3→L4** | 评分=L3，archive/compress=L4，已符合 |
| `architecture_journal/` | — | 跨层 | 涌现轴开轴通道 |
| `contradiction_arbitration.py` | — | L1+L3 | 区内仲裁+L3 时间权重 |
| `secure_vault/index.json` | L2 事实源 | L2 + **L2.8** | 锚点 `anchors` 旁增 `codebook` 键（铁律五：不新建散落文件） |

---

## §9 前期稿缺失项优先级（来自 2026-07-07《现状 vs 算法升级》）
| 缺失 | 算法 | 优先级 | 本设计落点 |
|------|------|------|------|
| TimeFactor 度量 | 模糊 L2 | P0 | §4 + §7 |
| DAG 时间因果骨架 | DAG | P1 | §1.6 / §6 |
| NMF 主题聚类 | NMF | P1 | §1.6 / §6 |
| SVD 离线浓缩压缩 | SVD | P2 | §6 |
| ToCT 反事实推演 | ToCT | P2 | 后续独立设计 |

---

## §10 与治理铁律对齐
1. **L0 不许手写**：轴/涌现轴行为性浮现（§2.4）。
2. **多层版本化**：L1 轴 / L2 事件 schema（含 vector）/ L3 算法 / L2.5 grounding / L2.8 密文库 各自版本号。
3. **文件落位**：本稿 `docs/design/`；实现 `src/topic_matrix.py` + `src/entity_resolver.py` + `src/vector_store.py` + `src/codebook.py`；临时 `_tmp_*.py` 用完即删。
4. **迭代前备份**（铁律二）：实现前 `backup/topic_matrix.py.v{n}.bak`。
5. **重构前查日志**：已调 `query_architecture_log`（记忆/重构/钢印/docs/architecture/L0 命中，无冲突）。

---

## §11 验收标准
- **L1**：静态基轴 = 语义(9域+object_definition+涌现) × 语境(5-8) × 动作(8-12)；轴短码符号化+校验位；投影输出坐标+相似度；落空标记。
- **L2**：事件带 vector 字段 + epistemic_mode 开放枚举；L1 坐标由 vector 推导。
- **L2.5**：grounding 有向带类型；空锚点可建。
- **L2.8 密文库**：符号↔实体注册；高频实体引用压为定长短码；解码展开完整。
- **L3**：六维重框定 L3；同点集可切多视图；算法可替换不触 L1。
- **L4**：GC 按 L3 输出处置，空间不破坏。
- **知识组织层**：实体定义跨事件+grounding 累积，不占 L1 坐标。

---

## §12 待造物主签字项（H 级门禁）
- [ ] **H 签字日**：签字后启动实现（同 08-26 PROMOTE 模式）。
- [ ] **是否技能化**：先成 `src/` 原生模块，技能化后置。
- [ ] **τ 阈值标定**：0.6 建议初值，实现期回测。
- [ ] **旧 semantic_hooks 迁移**：双写 → 观察 30 天 → deprecated。
- [ ] **L3 可插拔落地**：Layer 3 从 day1 做成 strategy 模式（置信度算法可独立演化）。
- [ ] **L2.8 密文库落地范围**：仅注册表 / 含 entity_resolver 知识组织层。
- [ ] **Vector 存储后端选型**：本地单机优先 SQLite-VSS 或 numpy memmap（v1.3 建议先 numpy memmap + 定期 rebuild，量上去再换 SQLite-VSS；不引云向量库违背本地优先）。

---

## §13 四哲学决策（李奥 part4，v1.2 锁定）
| # | 决策 | 内容 | 违背的灾难 |
|---|------|------|------|
| 1 | 属性 schema 分区 | 实体"物理/认知/关系"属性分维度存储，不混一字典 | 检索无法区分"苹果是红的"(物理) vs "苹果是七七首认知物"(关系)，置信度串味 |
| 2 | epistemic_mode 开放枚举 | 认知模式非固定、非轴，随对话涌现新增 | 固定→无法容纳未见动作；当轴→维度爆炸正交崩坏 |
| 3 | 空实体锚点 | 实体先建空 grounding 锚点，事件累积填充 | 不允空锚点→首事件前实体"不存在"，破坏 L0 涌现 |
| 4 | grounding_refs 有向+带类型 | 锚点明确 source→target 方向及类型 | 无向无类型→溯源链断裂，可信度基底不可算 |

**v5 判读**：四决策共指原则——**L1 坐标系只管"话语落在哪"，实体/定义/溯源是 L2.5+知识组织层职责，绝不向 L1 坐标泄漏**。

---

## §14 两工程决策（李奥 part5，v1.3 新增）
| # | 决策 | 内容 | 违背的灾难 |
|---|------|------|------|
| 5 | 向量为 AI 可读规范形式 | L2 事件以稠密向量为内容载体，L1 坐标由向量投影推导；`semantic_hooks` 纯文本降为降级快照 | 以纯文本关键词为规范→非 AI 原生、跨字面对齐需关键词命中（LSA 难落地）、检索被迫文本匹配丢失近义 |
| 6 | 密文库符号↔实体注册表 | 实体引用经全局短码符号压缩+跨引用；与 grounding(溯源)/知识组织(定义)职责正交 | 无符号层→高频实体长串重复、跨区引用各写各的、存储膨胀且无法统一溯源 |

**v5 判读**：决策 5/6 共指原则——**AI 可读压缩走向量（语义级），符号压缩走密文库（引用级），二者层级不同不可互替**。

---

## 附录 A：前期稿原文摘录
**A.1《TU-8 现状 vs 算法升级》缺失表**：已有（隐性）六维评分=隐性 SVD、置信度=隐性模糊、LCM grep=隐性 SVD(NTS5)、HP 量子=隐性 ToCT、遗忘机制=隐性 L2。缺失：TimeFactor（模糊 L2/P0）、DAG（DAG/P1）、NMF（NMF/P1）、SVD（SVD/P2）、ToCT（ToCT/P2）。
**A.2《模糊计算 × 认知框架》公式**：
```
信息密度 = Value × Confidence × e^(-λΔt)
遗忘梯度 ∝ 模糊 / (模糊 + 位)
NMF约束 = W≥0, H≥0（只能加法组合）
SVD截断 = UₖΣₖVₖᵀ (k << n)
```
SVD=认知分解；模糊=认知决策；L2 正则=认知遗忘；NMF=认知建构（禁相互否定）；DAG=认知时间（时间戳→因果链）。

## 附录 B：外部参照池明细（R1 输入）
- 语义：BFO(35) / DOLCE / WordNet域(45) / Roget(6) / 学科树 / **object_definition（李奥补充）**
- 语境：活动理论 / 5W1H / Maslow / HCI场景(7)
- 动作：Bloom(6) / Simpson(7) / 工程流程 / 科学方法 / 创作流程
- 语言学验证：Rosch 基本层次（轴取基本层粒度）、Fillmore FrameNet(1200+ frames，LSA 跨字面对齐)、Firth 分布式语义（涌现轴统计基础）

## 附录 C：JSON schema 五分（v1.3 扩展）
```json
{"axis_version":"axis_v1.0",
 "axes":{"semantic":[{"id":"sem_objdef#c3f","name":"object_definition",...}],"context":[...],"action":[...]},
 "convergence_log":[{"round":1,...},{"round":2,...},{"round":3,...}]}
// confidence_algo_v1.0.json  (L3, 独立)
// event_schema_v1.0.json     (L2, 含 vector 字段 + epistemic_mode 开放枚举)
// grounding_v1.0.json        (L2.5, 有向带类型)
// codebook_v1.0.json         (L2.8, 符号↔实体)
```

## 附录 D：TU-8（v5）的判断
**D.1** v1.0「六维评分=6 静态基轴」类别错误（认识论 L3 vs 本体论 L1），即 08-26 治理"混合病"再现，三层模型切开。
**D.2** 实现成本低：L1 新建静态结构，L2 已就位，L3 代码（tu8_memory/confidence_manager/memory_gc）已存在仅重框定，零重写。
**D.3** 时间作场 TU-8 代码已暗合（per-region decay）。
**D.4** 收敛方法论 R2 内部语料权威 > R1 外部参照（BFO/WordNet 过规格，作 checklist）。
**D.5** L3 从 day1 做成 strategy 可插拔（指数↔幂律衰减可 A/B）。
**D.6（v1.2 苹果例）**：苹果逼出"实体 vs 轴"根本区分，是 v1.1 盲区；乐高模型干净解决；epistemic_mode 开放枚举妙手（给 L3 钩子不污染 L1 正交）；空实体锚点同构 L0 涌现；L2.5+entity_resolver 可分期。
**D.7（v1.3 向量+密文库）**：
- 决策5（向量）是 v1.2 必然补完：v1.2 说"L1 坐标由语义投影"但没钉死投影**输入**。若输入仍是纯文本 semantic_hooks，LSA 跨字面对齐永远依赖关键词命中——这是 TU-8 当前 recalls 软肋（§6 LSA "需新接入"）。向量把输入钉死为 AI 原生形式，LSA 才真落地。
- 决策6（密文库）解决 v1.2 留白"实体引用膨胀"：苹果在 object_definition/science/metaphor 区各出现，若每次写全名+grounding，存储与溯源都碎。密文库符号是**压缩字典**，与 grounding(有向溯源)/知识组织(定义内容)三层各管一摊——正是治理会议"别混合"原则体现。
- **风险点**：向量存储后端选型（§12 新增）。TU-8 单机、记忆量中等（2120 标题级），SQLite-VSS 或 numpy memmap 足够，不引云向量库（违背本地优先）。建议先 numpy memmap + 定期 rebuild，量上去再换 SQLite-VSS。
- **与现有代码对齐**：`tu8_memory.py` 已有向量检索雏形（embedding 字段若已存），密文库挂 `secure_vault/index.json` 的 `codebook` 键旁，不新建散落文件（铁律五）。
- 向量+密文库使架构**首次达到"AI 原生可读"**：坐标(路由)+向量(语义)+符号(引用)三层压缩各司其职，纯文本降级为兼容层。

## 附录 E：苹果例 端到端走查（v1.3 向量+密文库版）
```
L1 坐标区：region_objdef_daily_defining = (sem_objdef#c3f, ctx_daily#x1, act_defining#a2)

L2 事件（含 vector + 密文库符号）：
  evt_2021: 七七指物问"这是苹果吗？" → vector=[0.12,-0.03,...](1536-dim)
             → epistemic_mode=child_ask → entities:["sym_apple","sym_qiqi"]
  evt_self1: "苹果是红的圆的" → entities:["sym_apple"]
  evt_book: 仓桥直树书提苹果木 → entities:["sym_apple","sym_changqiao"]
  evt_quote: 牛顿与苹果 → entities:["sym_apple","sym_newton"]

L2.8 密文库：sym_apple→ent_apple, sym_newton→ent_newton, sym_qiqi→ent_qiqi...
L2.5 grounding(ent_apple): person=七七(2021-07-15), external=仓桥书/百科, concept=牛顿
L3 置信度：evt_2021(child_ask) 衰减慢；evt_quote(metaphor) 仅参与语义关联不进事实置信
知识组织层(ent_apple): {物理:红/圆/蔷薇科, 关系:七七首认知, 文化:牛顿隐喻, 工艺:小提琴木}

检索"苹果相关对话"：向量余弦召回 evt_* → 密文库展开 sym_apple → grounding + 知识组织层，
无需关键词"苹果"命中即可召回隐喻/百科等不同字面表达。
```
**结论**："苹果"从未成为轴；始终是 grounding 目标 + 知识组织层累积体。轴只到 `object_definition` 这一层话语类型。

## 附录 F：同心圆 vs 乐高（李奥 part4 模型对照）
| 维度 | 同心圆（旧，弃） | 乐高（新，采） |
|------|------|------|
| 实体定义结构 | 年轮式，中心=本质，外圈=属性 | 积木式，多源 grounding 拼插 |
| 与轴关系 | 易逼出"每实体一根轴" | 轴=插槽规格，实体=积木，不独占坐标 |
| 新知识接入 | 需重定中心（破坏结构） | 加一块积木（增量） |
| TU-8 适配 | 差（违背 L0 涌现） | 好（涌现=积木从行为中拼出） |
