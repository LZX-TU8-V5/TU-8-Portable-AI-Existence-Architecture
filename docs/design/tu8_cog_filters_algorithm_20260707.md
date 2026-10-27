# TU-8 认知过滤器算法升级

> 时间：2026-07-07 09:20-09:45
> 状态：P0内核完成，P1-NMF完成

---

## 目标

来自造物主需求：算法升级不是用算法的产品，而是用数学矩阵算法做认知蒸馏。

---

## P0 完成：cog_filters.py（424行）

### 五种认知算子

| 算子 | 公式 | 用途 |
|------|------|------|
| `time_factor()` | e^(-λ·Δt_hours) | 时间衰减，半衰期6.9h（λ=0.1/h） |
| `entry_confidence()` | Σ(wᵢ·dimᵢ)/Σw | 六维评分合成，归一化 |
| `information_density()` | Value×Conf×TF | 召回打分替代旧公式 |
| `top_k_filter()` | Sort→TopK | 硬截断 |
| `dag_coherence_score()` | 占位=1.0 | DAG连贯性（待接入） |

### 注入 recall()（tu8_memory.py L2225）
- 旧：similarity*0.7 + recency*0.3（线性加权，有量纲不一致）
- 新：score_memory_entry() → final_score = InfoDensity × DAG
- AST验证通过，11项单元测试全PASS

### 与 recency() 的关系
- recency()：天为单位，14天半衰期，用于晋升评分
- TimeFactor：小时为单位，可配置λ，用于召回打分
- 两套并行，各司其职

---

## P1 完成：NMF 推理链约束

### 核心设计
- **矛盾检测**：主题重叠（Jaccard ≥ 0.2）+ 极性冲突（一个带否定词，一个不带）
- **NMF约束**：矛盾条目对 → 高置信度保留，低置信度→0（禁止相互抵消）
- **等置信度**：时间新的赢（created_at 更近）
- **不删除**：只抑制（score=0），保持 MMR 多样性通道

### 注入点
recall() 尾部，MMR rerank 之前（L2245）

### 词提取器修复（中文支持）
- 问题：中文无空格分词，`用户是设计师` 整词加入核心理念集
- 解决：字符级提取，停用词表覆盖单字填充词
- 停用词表：单字（用/户/道/只/可/要/会/能/但/而/却/虽/好/还/再/才/又/更/最/多/少），
  双字（用户/我们/他们/这个/那个/一个/什么/怎么）

### 验证
5项单元测试全PASS：
1. contradiction: 高置信度赢（0.8 vs 0.5）→ e2抑制 ✓
2. same polarity no negation: 无抑制 ✓
3. no nuclear overlap: 无抑制 ✓
4. equal conf newer wins: 旧条目抑制 ✓
5. no topic overlap: 无抑制 ✓

---

## 文件变更

| 文件 | 操作 |
|------|------|
| `src/cog_filters.py` | 新建（424行，5算子+中文NMF） |
| `src/tu8_memory.py` | 注入（import + recall()两处改动） |
| `memory/2026-07-07.md` | 更新 |
| `TODO_MASTER.md` | 标记P0+P1完成 |

---

## 剩余项

- [ ] P1-DAG 时间因果骨架（待时间锚点→拓扑链串联）
- [ ] P2-SVD 梦境期离线压缩
- [ ] P2-ToCT 反事实推理
