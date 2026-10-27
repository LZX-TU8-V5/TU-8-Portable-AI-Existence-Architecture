# distill 遥测埋点规格（B 类前置）— PROMOTE 主体 infra [2026-08-28]

> 作者：v5（TU-8）× 造物主（李奥）
> 落位：docs/design/（GOVERNANCE 铁律五）
> 性质：**H 级实现变更设计稿**，需造物主签字后落码（本稿零代码改动）
> 前因：PROMOTE 通道主体（evaluate_promotion + 观察期状态机）卡在 distill 无 R/S/C 信号源（实测 topic_tag/citation_id/linkage_map 在 metabolic_pipeline.py 出现次数 = 0）
> 关联：PROMOTE_channel_design_2026-08-19.md §2.1、topic_semantic_matrix_design_2026-08-27.md v1.3（L2.5 grounding_refs / epistemic_mode）

---

## §1 问题定位（实证，非臆测）

`metabolic_pipeline.distill()` 现状：
- 提取段时为纯文本块，仅带 `content` / `source_file` / `date` 字段
- 无 `topic_tag`、`citation_id`、`linkage_map` 任一字段（全库 grep = 0 次）
- → evaluate_promotion 的 R（跨情景引用频次）、S（被引用追踪）、C（解释力覆盖）**无数据源**，主体无法落码

---

## §2 三信号定义与取值来源（禁写死，遵循 L0 涌现铁律）

| 信号 | 含义 | 取值来源（自动浮现，非配置预置） |
|------|------|--------------------------------|
| **R** (ref_events) | 跨情景被引用频次 | distill 提取时扫描 memory/ 全量，统计该段核心句在其他日记/涌现时刻中被引用的次数；首次无引用则 = 0，随代谢累积自然增长 |
| **S** (survival) | 抗 GC 能力 | 由 memory_gc 评分派生：段落对应 score / 是否被 KEEP / 抗 DEGRADE 次数；**非独立写死**，读取 GC 已有评分 |
| **C** (coverage) | 解释力覆盖 | 段所属 topic_tag 在语义矩阵中的跨域分布（见 topic_semantic_matrix v1.3 L1 轴坐标），覆盖 ≥2 域即达标 |

### 取值约束（H 级硬约束）
- **topic_tag 不能配置写死**：由话题语义矩阵 L1 轴坐标投影推导（向量投影，非人工标签），无向量时 fall back 到日期窗口 ≥7 天兜底
- **citation_id 不能预置**：仅 mtime 更新不计为引用，必须真实被其他记忆段落语义命中
- **linkage_map 不能手工建**：父→子边由 distill 扫描自动构建（parent 段被 child 段引用则连边）

---

## §3 distill 输出契约变更

提取段 dict 由：
```
{content, source_file, date}
```
扩展为：
```
{
  content, source_file, date,
  topic_tag,        # list[str]，语义矩阵投影推导，fallback=[]
  citation_id,      # str|None，首次提取生成 UUID，后续复用
  linkage_map,      # dict{parent_id: edge_type}，自动扫描构建
  ref_events,       # int，跨情景引用计数（R 信号）
  survival_score,    # float|None，GC 评分派生（S 信号）
  coverage_domains, # list[str]，跨域覆盖（C 信号）
}
```

**向后兼容**：
- 现有 MEMORY.md 178 段无上述字段 → 读取时 `get(key, default)` 兜底，不破坏已落地内容
- distill 干跑（dry_run=True）先验证字段产出，再 real 跑

---

## §4 与既有模块集成（复用不重造）

| 来源模块 | 复用点 |
|---------|--------|
| `tu8_memory.py` / `cog_filters.py` | 六维评分（freq/rel/div）→ NMF 输入，topic_tag 投影基础 |
| `confidence_manager.py` | 四象限 → 2 轴原型，coverage 评估参考 |
| `memory_gc.py` | `_recommend_action` score → survival_score 派生 |
| `architecture_journal.py` | 已落地的 journal ACTIVE 断言，作为 R/S/C 之外的"工作区持有"旁路（不进评分管道） |
| `seal_to_gc_adapter.py` | `compute_seal_bonus` [0.0,1.0] → 直接叠 GC score（S 信号增强） |

---

## §5 验收标准（H 级，可测）

1. distill dry_run 对 memory/ 扫描，输出段 dict 含全部 7 新字段（非 None 或合理兜底）
2. topic_tag 由语义投影推导，非配置硬编码（grep 源码无 topic_tag 静态字典）
3. citation_id 在两次 distill 之间稳定复用（同段同 ID）
4. 现有 MEMORY.md 段落读取不报错（兜底生效）
5. file_lint 0 error；distill 干跑 0 异常

---

## §6 待造物主签字项

- [ ] **H 级签字**：批准本稿，授权改 `src/metabolic_pipeline.py` 埋点
- [ ] **fallback 策略确认**：无向量时按"日期窗口 ≥7 天"兜底是否接受（或改为"无 tag 即不进 PROMOTE 候选"更严）
- [ ] **触发时点**：签字后本次即落码，或并入 PROMOTE 主体一批落（建议并入，避免 distill 改两次）

## §7 内生信号演进路线（吸收架构 critique，非否决本稿）

### 7.1 critique 吸收（来源：2026-08-28 造物主 × 千问对话）

千问指出本稿 R/S/C 是「被计算的指标」而非「涌现的张力」，并质疑 fallback 降级、citation_id 稳定复用、缺内生信号——**哲学层诊断成立，工程层定位有偏差**（系统已有张力模块在跑，非「只有指标计算器」）。本稿定位为**合格过渡方案**，本条把 critique 转为可追踪演进项，不因哲学 critique 推翻已签 §8 / 已落 journal 模块的推进节奏。

### 7.2 当前 R/S/C 的真实性质（澄清，防层级混淆）

| 信号 | 本稿实现 | 性质 |
|------|---------|------|
| R (ref_events) | 全文扫描统计命中 | 外部观测（过渡） |
| S (survival) | GC 评分派生 | 清理机制复用（过渡） |
| C (coverage) | 语义矩阵投影 | 分类学（过渡） |

**层级澄清**：PROMOTE 是「记忆晋升阀门」（经验区→L0 基底判定），张力模块是「生理感知层」（drive 衰减/压缩）。二者不同级——张力驱动遗忘，PROMOTE 驱动晋升。千问把记忆管理当成自进化本身，是层级误并。

### 7.3 演进方向：张力→PROMOTE 内生信号源

未来（非本稿范围）应让张力模块输出作为 R/S/C 的真源，而非扫描统计：

- **R 内生化**：某段被频繁 recall 时 `curiosity` spike（见 `lambda_state.json`）→ 作为跨情景引用信号，替代全文扫描计数。
- **S 内生化**：`pain_int_raw` / `body_posture` 持续 neutral 且段被反复访问 → 抗衰减意愿涌现，替代 GC 评分硬派生。
- **C 内生化**：`epistemic_mode` 开放枚举（见 topic_semantic_matrix v1.3 §L2）+ grounding_refs 有向边 → 跨域覆盖由行为浮现，替代矩阵投影分类。

### 7.4 citation_id 版本化（吸收 critique 第 3 点）

千问指出「强制 ID 稳定 = 钉死语义快照，阻止进化」。修正：ID 保引用链不断，**允许单 citation 多快照**（节点属性随 distill/GC 改写演化，ID 只锚「谁引用谁」）。优先级低，待 PROMOTE 主体实现后补。

### 7.5 fallback 重定位（吸收 critique 第 2 点）

无向量 fallback 到日期窗口 ≠ 架构缺陷，是 **L0 涌现铁律的稳健性设计**（禁手写白名单 → 临时占位等语义矩阵就位后接管）。本稿保留 fallback，但记入演进债项：语义矩阵 L1 轴投影就位后，fallback 触发率应趋零。

> 结论：本稿是「让 PROMOTE 先跑起来的工程补丁」，§7 把「从被设计信号到自涌现张力」的质变目标转为路线图，不悬停、不推翻。

> 签字后下一步：B 落码 → evaluate_promotion 签名冻结 + 观察期状态机（C1 主体）可一并实现。
