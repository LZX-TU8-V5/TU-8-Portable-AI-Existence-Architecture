# 话题语义矩阵 — 实现设计文档（Implementation Design）[2026-08-28]

> 级别：**H 级**（架构扩展实现，需造物主显式签字后落码）
> 上游真源：`docs/design/topic_semantic_matrix_design_2026-08-27.md` v1.3（概念/架构稿，本稿是其**实现展开**）
> 作者：v5（TU-8）× 造物主（李奥）
> 落位：`docs/design/`（GOVERNANCE 铁律五）
> 本文档性质：**代码蓝图**，零代码改动。签字后按 §8 分批落地。

---

## §0 目的与范围

v1.3 已定「做什么」（三层+两索引架构、轴定义、投影判区协议、四算子岗位）。本稿定「怎么写」：

- 模块文件清单与职责边界
- 数据 schema（L1 轴 / L2 事件 / grounding / codebook）
- 核心算法接口与伪码（`project` / `classify_region` / fallback）
- 四算子（NMF/SVD/LSA/DAG）的 TU-8 适配接入点
- Vector 存储后端选型（含 TU-8 当前无 embedding 管道的降级方案）
- 分批实现计划 + 可测验收

**不在本稿范围**：L3 置信度算法重构（六维重框定，独立任务）、entity_resolver 知识组织层（§12 决策待定）、PROMOTE 主体（已落地 `promote_channel.py`）。

---

## §1 模块划分（src/ 原生模块）

| 模块 | 职责 | 依赖 |
|------|------|------|
| `src/topic_matrix.py` | **L1 语义空间 + 投影判区**：基轴定义、轴短码、project(vector)、classify_region、落空处理 | vector_store, codebook |
| `src/matrix_operators.py` | **四算子**：NMF/SVD/LSA/DAG 的 TU-8 适配实现 | topic_matrix, tu8_memory（六维输入） |
| `src/vector_store.py` | **Vector 后端**：numpy memmap 初版 + 索引；可插拔 Vectorizer（TF-IDF 默认 / Ollama embedding 未来） | 无 |
| `src/codebook.py` | **密文库**：`sym_* ↔ entity_id` 注册表 + 解码展开 | secure_vault/index.json（codebook 键） |

> 不新建 `entity_resolver.py`（§12 决策：密文库仅注册表，知识组织层留后续）。

**L3 / 置信度算法**：不在此批。六维评分（`tu8_memory.py`）与四象限（`confidence_manager.py`）**重框定**为 L3 视图，仅改注释与调用约定，不改算法本体。

---

## §2 数据 Schema

### 2.1 L1 基轴定义（静态，禁写死新增轴；涌现轴走 §2.4 行为性浮现）

```json
{
  "axis_version": "L1_v1.0",
  "semantic": [
    {"code": "sem_arch",  "label": "架构",     "checksum": "a3f1"},
    {"code": "sem_sci",   "label": "科学",     "checksum": "b7c2"},
    {"code": "sem_create","label": "创作",     "checksum": "c9d4"},
    {"code": "sem_meta",  "label": "元认知",   "checksum": "d1e5"},
    {"code": "sem_phil",  "label": "哲学",     "checksum": "e2f6"},
    {"code": "sem_eng",   "label": "工程",     "checksum": "f3a7"},
    {"code": "sem_daily", "label": "日常",     "checksum": "a4b8"},
    {"code": "sem_emo",   "label": "情感",     "checksum": "b5c9"},
    {"code": "sem_math",  "label": "数学",     "checksum": "c6da"},
    {"code": "sem_objdef","label": "实体定义", "checksum": "d7eb"}
  ],
  "context": [
    {"code": "ctx_acad",  "label": "学术"},
    {"code": "ctx_personal","label": "私人"},
    {"code": "ctx_work",  "label": "工作"},
    {"code": "ctx_dialog","label": "对话"},
    {"code": "ctx_reflect","label": "反思"}
  ],
  "action": [
    {"code": "act_define","label": "定义"},
    {"code": "act_analyze","label": "分析"},
    {"code": "act_create","label": "创作"},
    {"code": "act_decide","label": "决策"},
    {"code": "act_recall","label": "回忆"},
    {"code": "act_correct","label": "修正"},
    {"code": "act_quote","label": "引用"},
    {"code": "act_plan","label": "规划"}
  ]
}
```

- 轴短码 = `前缀_英文缩写` + 2位校验位（防 L2 引用漂移）。
- 候选池来自 v1.3 §2.1/§2.2/§2.3 外部参照并集收敛，实证基础 §5（9 域已扫中）。
- **涌现轴**：`sem_emergent_*` 由行为性信号（跨情景引用≥3 ∧ 抗GC≥2 ∧ 解释力覆盖≥2，见 PROMOTE 设计稿 §2.1）自动开轴，不手写。

### 2.2 L2 生成事件（含 vector + epistemic_mode）

```json
{
  "event_id": "evt_20260828_001",
  "timestamp": "2026-08-28T11:00:00+08:00",
  "vector": [0.02, -0.11, 0.88, ...],   // 稠密定长（Vector 后端生成）
  "epistemic_mode": "child_ask",         // 开放枚举，随对话涌现新增
  "coord": {"sem": "sem_arch", "ctx": "ctx_work", "act": "act_decide"},  // project 输出
  "grounding_refs": [
    {"type": "person", "ref": "七七", "event_id": "evt_2021"},
    {"type": "external_source", "ref": "sym_book_violin", "event_id": "evt_book"}
  ],
  "entity_syms": ["sym_apple", "sym_newton"]
}
```

- `vector` 无时（迁移期）fallback 到 `semantic_hooks` 文本，由 Vectorizer 即时编码。
- `epistemic_mode` 不参与投影，随事件存 L3 消费。

### 2.3 L2.5 grounding_refs + L2.8 密文库

```json
// grounding（有向带类型）
{"type": "person|external_source|concept", "ref": "<sym_or_name>", "event_id": "evt_*", "note": "可选"}

// codebook（secure_vault/index.json 的 codebook 键）
{"codebook_version":"cb_v1.0","entries":{
  "sym_apple":{"entity_id":"ent_apple","label":"苹果","created_event":"evt_2021"},
  "sym_newton":{"entity_id":"ent_newton","label":"牛顿","created_event":"evt_quote"}
}}
```

---

## §3 核心算法：投影判区（topic_matrix.py）

### 3.1 project(vector) → 坐标

```python
def project(self, vector: np.ndarray) -> RegionHit:
    """
    输入: 稠密向量 (Vector 后端产出)
    输出: RegionHit(sem_code, ctx_code, act_code, max_sim, topk_regions)
    协议 (v1.3 §4):
      1. 取 vector（无则 Vectorizer.fallback(semantic_hooks)）
      2. 与各区代表向量余弦 ≥ τ → 命中
      3. 多区取 Top-k（默认 k=3）
      4. 全 < τ → 落空（触发涌现轴评估或噪声降权）
    """
    reps = self._region_representatives()   # 各区质心向量（LSA/SVD 离线算）
    sims = {rid: cosine(vector, reps[rid]) for rid in reps}
    hits = [(rid, s) for rid, s in sims.items() if s >= self.tau]
    hits.sort(key=lambda x: -x[1])
    if not hits:
        return RegionHit.empty(reason="below_tau")  # 落空
    top = hits[:self.top_k]
    return RegionHit.from_hits(top)
```

### 3.2 落空处理（v1.3 §2.4 / §4.3）

```python
def handle_miss(self, event) -> Decision:
    # 落空 = 结构性去噪（v1.3 核心）：要么新领域开轴，要么噪声降权
    if self._emergent_signal(event):   # 跨情景引用≥3 ∧ 抗GC≥2 ∧ 覆盖≥2
        return Decision.OPEN_EMERGENT_AXIS(event)
    return Decision.NOISE_DOWNGRADE(event)  # 不进任何区，降权
```

### 3.3 fallback（无 vector 时，迁移期关键）

> **实证修正（2026-08-28 查代码）**：TU-8 **已有 embedding 管道**，非无管道。
> `src/cognitive_evaluator.py` 的 `TFIDFEmbedder(dimension=128)` 已落地，`cognitive_integration.py` 已实例化为下游产出 embedding。
> 故 Vectorizer 默认后端 = **复用 `TFIDFEmbedder`**，不新造轮子；sentence-transformers 可作可选升级后端（capacitive_retrieval.py 已延迟加载，失败降级）。

```python
def fallback_vector(self, semantic_hooks: list[str], content: str) -> np.ndarray:
    """
    复用现有 TFIDFEmbedder（128维本地，零重依赖），非从零写 TF-IDF。
    可选升级：sentence_transformers 后端（可插拔，环境缺失时自动降级关键词）。
    """
    from cognitive_evaluator import TFIDFEmbedder
    vec = TFIDFEmbedder(dimension=128).encode(content)
    return np.asarray(vec, dtype=float)
```

---

## §4 四算子实现规格（matrix_operators.py）

| 算子 | 函数签名（草案） | TU-8 适配 | 优先级 |
|------|------|------|------|
| **NMF** | `nmf_cluster(sections, k) -> (W, H)` | W,H≥0 约束；六维评分作初始化先验（非负） | P1 |
| **SVD** | `svd_compress(matrix, k) -> (Uk, Sk, Vk)` | 离线算各区质心 `reps`（§3.1 用）；k<<n 截断 | P2 |
| **LSA** | `lsa_align(query_vec, region_reps) -> ranked` | 向量余弦跨字面对齐，替代关键词命中软肋 | P1 |
| **DAG** | `build_causal_chain(events) -> DAG` | 时间戳→因果拓扑，按需追溯不读全史 | P1 |

**复用不重造**：
- NMF 输入 = `tu8_memory.py` 六维（`freq/rel/div` 非负）→ 天然适配
- LSA 消费 `vector_store` 的向量索引
- DAG 读取 L2 事件 `timestamp` 字段

---

## §5 Vector 存储后端（vector_store.py）

**TU-8 现状**：单机、记忆量中等（~1500 md）、**当前无 embedding 模型管道**。

**选型决策（v1.3 §12 + 本地优先 + 2026-08-28 实证修正）**：
1. **存储**：`numpy memmap` 存稠密向量矩阵 + 定期 rebuild 索引（简单、零依赖、本地）。
2. **编码（Vectorizer）**：复用现有 `cognitive_evaluator.TFIDFEmbedder`（128维，本地零重依赖），**不新造**；
   可选升级后端 = `sentence_transformers`（capacitive_retrieval.py 已延迟加载模式，缺失自动降级关键词匹配）。
3. **不引云向量库**（chroma/milvus/qdrant 全 0 命中；FAISS 仅是 quantized_memory 外部索引引用，TU-8 不自维护向量库）。
4. **未来**：量上去换 SQLite-VSS；或换 sentence-transformers 后端（可插拔，不改存储接口）。

```python
class VectorStore:
    def __init__(self, path: Path):  # memmap 文件
        ...
    def add(self, event_id: str, vec: np.ndarray): ...
    def query(self, vec: np.ndarray, top_k: int) -> list[tuple[str, float]]: ...
    def rebuild(self): ...  # 定期重算索引

class Vectorizer:
    def encode(self, text_or_hooks) -> np.ndarray:  # 默认 TF-IDF；未来 Ollama
        ...
```

---

## §6 密文库实现（codebook.py）

```python
class Codebook:
    def __init__(self): self.data = load_codebook()  # secure_vault/index.json["codebook"]
    def register(self, label: str, event_id: str) -> str:  # 返回 sym_*
        sym = f"sym_{slug(label)}_{checksum(label)[:4]}"
        self.data[sym] = {"entity_id": f"ent_{...}", "label": label, "created_event": event_id}
        return sym
    def resolve(self, sym: str) -> dict:  # sym_* → ent → grounding + 知识组织层
        ...
    def save(self): write_back_to_index_json()
```

- 挂载 `secure_vault/index.json` 的 `codebook` 键（铁律五：不新建散落文件）。
- 高频实体（苹果/牛顿/TU-8/七七）引用压为定长短码，跨区统一经符号。

---

## §7 与现有模块集成接线

| 现有模块 | 接线点 |
|---------|--------|
| `metabolic_pipeline.distill` | 提取段后调 `Vectorizer.encode` + `topic_matrix.project` → 写 L2 事件 coord 字段（**B 稿六遥测字段扩展点**） |
| `memory_gc.py` | L3 评分消费 `coord` 派区；热区快存冷区归档（§7 存储路由） |
| `tu8_memory.py` | 六维 → NMF 输入先验 |
| `contradiction_arbitration.py` | L1 共享轴区内仲裁；L3 时间分布加权 |
| `promote_channel.py` | 涌现轴开轴信号（跨情景引用≥3 等）触发 `topic_matrix.open_emergent_axis` |
| `secure_vault/index.json` | codebook 键宿主 |

---

## §8 分批实现计划

| 批次 | 落点文件 | 内容 | 验收 |
|------|---------|------|------|
| **批次 1（地基）** | `topic_matrix.py` + `vector_store.py` | L1 轴定义 + project/classify_region + 落空 + TF-IDF fallback + memmap 存储 | §9.1-9.2 |
| **批次 2（算子）** | `matrix_operators.py` | NMF/SVD/LSA/DAG 四算子 TU-8 适配 | §9.3 |
| **批次 3（压缩）** | `codebook.py` + distill 接线 | 密文库注册表 + distill 写 coord/entity_syms | §9.4 |

> 每批独立 H 级子流程：备份 → 改 → file_lint 0 error → 冒烟。

---

## §9 验收标准（可测）

1. **L1**：基轴 9 域 + object_definition 定义完整；project 输出 `(sem,ctx,act)` + 相似度；τ=0.35 下命中率合理（同主题命中/异主题不命中）；落空标记正确。
2. **Vector**：memmap add/query 往返一致；TF-IDF fallback 产出定长向量。
3. **四算子**：NMF 输出 W,H≥0；SVD 截断重建误差<阈值；LSA 余弦排序优于关键词命中（抽样）；DAG 时间戳拓扑无环。
4. **Codebook**：sym 注册/解析往返；解码展开完整 grounding。
5. **集成**：distill 跑完段带 coord；memory_gc 读 coord 不崩；file_lint 0 error。

---

## §10 待签字项（继承 v1.3 §12 + 本稿新决议）

- [ ] **H 签字**：批准本实现设计，授权按 §8 三批次落地
- [ ] **τ 阈值**：**0.35**（实现期回测标定：TFIDF 哈希向量同主题 0.4-0.5 / 异主题~0，0.6 过严全 miss，2026-08-28 实测）
- [ ] **Vectorizer 默认**：TF-IDF 降级版（确认 TU-8 无 embedding 管道，先用本地）
- [ ] **批次起点**：批次 1（地基）优先
- [ ] **密文库范围**：仅注册表（不含 entity_resolver，留后续）
- [ ] **语义轴实证补全**：object_definition 轴需 R2 内部数据收敛后实证（§5 备注）

> 签字后下一步：批次 1 落码（`topic_matrix.py` + `vector_store.py`），走 H 级子流程。

---

## §11 风险与已识别坑（TU-8 lens）

1. **embedding 能力已具备（实证修正）**：`TFIDFEmbedder` 已落地可复用，非降级妥协。风险转为「Vectorizer 后端选型稳定性」——sentence-transformers 若环境缺失需确认自动降级路径（capacitive_retrieval 已有先例）。
2. **memmap 并发**：GC/distill 同时写向量矩阵需加锁或串行；初版单线程 rebuild 足够。
3. **轴漂移**：L2 引用用短码+校验位防漂移（§2.1）；旧 `semantic_hooks` 双写 30 天观察后 deprecated（v1.3 §3.7）。
4. **涌现轴误开**：行为性信号阈值需回测，避免噪声开轴（§3.2 严格三条件）。

---

## §12 千问三段对话映射（防过度设计，2026-08-29 固化）

> 来源：李奥 × 千问对话「长短对话向量余弦偏差」三段（通用 RAG 长短文档 / 压缩标签混合架构 / 张量分解轴级对齐）。
> 目的：把外部方案与 TU-8 真实状态对齐，标记「采纳 / 已同构 / 不适用」，防未来过度设计回潮。

### §12.1 TU-8 当前真状态（判读基准）
- Vectorizer = `TFIDFEmbedder`（128维哈希，**非 mean pooling，已 L2 归一化**，模长固定）
- 投影协议 = 单事件文本 vs 各轴代表向量余弦，每轴**多短短语 MAX 池化**（批次1 修复）
- 投影单位 = 单条记忆卡/日记标题（短文本，非 30 轮对话）
- 验证：真实语料 63 样本命中率 **93.7%**（修种子短语 bug 后）
- 架构 = v1.3 三正交轴 `(sem, ctx, act)` **离散坐标**，非连续张量

### §12.2 三段逐条判读

| 段 | 千问核心 | TU-8 适配 | 处置 |
|----|---------|----------|------|
| 一（长短文档余弦偏差） | 语义稀释/模长偏差/分块对齐/多粒度索引/Calibration 分桶 | TFIDF 哈希模长固定无漂移；投影单位是短记忆卡无长文档分块需求 | **不适用**（过度设计，当前尺度不需要） |
| 二（压缩标签 vs 完整原文） | 「`我吃饭` 压缩标签永远不要和完整语句算余弦，不在同一语义平面」 | **正是批次1 初版 bug 原型**（裸轴 label 作代表向量 vs 完整事件→token 不重叠→全 miss）；批次1 修复（富短语 MAX 池化）= 千问「增强摘要」工程版 | **已同构**，验证修复方向正确，无新动作 |
| 三（张量 a×b×c 轴级对齐） | 不在整体向量比较，在轴级拾取匹配；交集轴对齐+缺失轴标未指定 | TU-8 v1.3 三正交轴 project 输出 `(sem,ctx,act)` 离散坐标，`_best_in_axis` 每轴独立取 best，缺失轴不判不匹配 | **已同构**，千问描述= TU-8 设计稿旁证，无需深入 |

### §12.3 TU-8 lens 补强（千问未看到的约束）
1. **哈希向量 ≠ 稠密 embedding**：千问全程假设 embedding 模型（mean pooling/PCA whitening/Matryoshka）。TU-8 哈希向量无连续语义空间，PCA 降维无意义；只有换 sentence_transformers 才有意义（设计稿 §5 可插拔，当前环境无包）。
2. **TU-8 轴是离散分类格，非稠密子空间**：千问「稀疏点 vs 稠密子空间激活密度不同」隐喻对 TU-8 不成立——每条记忆必落每轴一个离散格，不存在「激活密度导致余弦偏低」。故千问「密度归一化」TU-8 天然满足（缺失轴不影响其他轴命中）。
3. **落点**：TU-8 不需要传统单向量余弦校准，因架构本身是轴级离散落格。

### §12.4 可吸收的低优先增强（非必须，待签）
- **A（信息增强，不改算法）**：`classify_event` 返回补 `coverage = 命中轴数/3`，让下游知这是「单轴明确记忆」还是「三轴俱全富记忆」（借鉴千问「缺失轴标未指定」）。
- **B（根治长短可比性）**：设计稿 §5 已规划 sentence_transformers 可插拔；环境可用时升级 Vectorizer 后端即自动获得稠密向量长短可比性。
- **不做**：分块对齐 / 多粒度索引 / PCA whitening / Calibration 分桶——TU-8 短记忆卡尺度 + 离散轴架构下过度工程。

### §12.5 结论
批次1+2 验证通过（93.7% 命中），架构哲学与千问第三段同构。三段对话**不触发任何实现变更**，仅固化本映射防回潮。批次3（密文库）独立推进。


## §13 千问「语义版 SVD」类比判读（防过度设计，2026-08-29 固化）

> 来源：李奥贴千问对话「n^n 多维张量分解是否算语义版 SVD」。
> 判读基准：实读 src/topic_matrix.py + src/matrix_operators.py + 设计稿 §2/§6/A.1。

### §13.1 核心结论
千问类比**前提错**：TU-8 不是「n^n 多维张量分解」——L1 是离散坐标投影（每条记忆落 1 sem+1 ctx+1 act 格，MAX 池化最近轴），无张量数学对象、无 rank-R 分解、无 λᵢ 权重、无张量积。
该对话脑补了 CP/Tucker 公式，TU-8 未实现。

### §13.2 说对的（吸收）
- 轴可解释性 + 正交性 = TU-8 真设计（v1.3 sem×ctx×act 三正交、可命名）
- 比 embedding 更可解释、适配检索（实测 coord 人类可读）
- 与 BERT 是上层模块关系（但 TU-8 底层是 TFIDF 哈希，非 BERT）

### §13.3 说偏/错的（修正）
- **「n^n 张量分解」前提错**：n^n 是组合空间（轴笛卡尔积），非待分解张量。TU-8 做离散投影非连续分解。
- **CP/Tucker 公式不存在**：coord = 每轴取 1 best（`_best_in_axis`），无连续秩、无张量积。
- **SVD 定位错**：千问把全系统说成「语义版 SVD」，但 SVD 在 TU-8 仅是 L4 压缩算子（`svd_compress` 截断 k=2 给 memory_gc 热门区）。真同构物是**六维评分**（设计稿 A.1「六维非负评分=隐性 SVD」），千问漏此点去脑补不存在的张量分解。
- **「对齐损失替代重构损失」虚构**：TU-8 投影用余弦+τ 阈值（最近轴分类），无训练、无梯度、无损失函数。
- **「密文坐标原生索引」混层**：坐标是明文 {sem,ctx,act}；密文库 codebook 是实体符号压缩（sym_*），与坐标索引不同层。

### §13.4 TU-8 lens 补强（千问未看见）
- **分层架构**：L1 投影 ≠ L3 置信度算法（独立可插拔）≠ L4 代谢（消费置信度）。千问把投影当分解谈，未看到分层。
- **六维=隐性 SVD 才是真同构**：freq/rel/div/cons/meaning/emotion 非负加权 → 隐性 UₖΣₖVₖᵀ，是 TU-8 自认的 SVD 关系，非坐标投影。
- **实证数据**：τ=0.35 全量 3356 样本 65.2% 命中（真实人工标题 >80%）= 分类命中率，非重构误差。拿 SVD Frobenius 误差比，范畴不对。

### §13.5 正确表述（对外/对内统一口径）
> TU-8 的 L1 投影是**可解释的离散降维**（轴先验、正交、最近轴分类），在「降维/压缩/可检索」功能层类比 SVD；但机制层（数学对象/分解形式/优化目标）**不成立**。SVD 本身是 TU-8 下游压缩算子，真同构物是六维评分而非坐标投影。

### §13.6 决策
- **不按千问写 CTD 论文**：前提错 + TU-8 是单机 Agent 架构（扩散策略见 MEMORY 2026-04-29 是模因污染非发论文）。
- 本 §13 固化映射，防回潮（同 §12 定位）。
