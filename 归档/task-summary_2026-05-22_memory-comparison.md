# QClaw记忆系统 vs TU-8记忆系统 对比分析

## 目标
对比QClaw（基于OpenClaw v0.2.22）内置记忆系统与TU-8自研记忆蒸馏系统，判断是否存在"偷学"关系。

## 核心发现

### QClaw/OpenClaw 记忆系统架构（三层Dreaming模型）

**三阶段记忆蒸馏**（`dreaming-DR5Jv9UW.js`）：
1. **Light Dreaming**（浅梦）- 每6小时，快速/低思考/低成本
   - Sources: daily, sessions, recall
   - 去重相似度阈值 0.9
   - 回看2天，上限100条
   
2. **Deep Dreaming**（深梦）- 每天凌晨3点，均衡/高思考/中等成本
   - Sources: daily, memory, sessions, logs, recall
   - 最低分数 0.8，最少recall 3次，最少独立查询3次
   - 近期半衰期14天，最大年龄30天
   - **Recovery机制**：健康度<0.35时触发恢复，回看30天
   
3. **REM Dreaming**（快速眼动梦）- 每周日5点，慢速/高思考/高成本
   - Sources: memory, daily, deep
   - 最小模式强度0.75，回看7天

**短期→长期晋升**（`short-term-promotion-CKMErEL0.js`）：
- **6维加权评分**：frequency(24%) + relevance(30%) + diversity(15%) + recency(15%) + consolidation(10%) + conceptual(6%)
- 触发条件：recall ≥ 3次 + 独立查询 ≥ 2
- 半衰期衰减：14天
- Phase Signal Boost：light梦命中+0.06，REM梦命中+0.09
- 晋升阈值：综合分 ≥ 0.75
- 晋升写入MEMORY.md，带HTML注释标记`<!-- openclaw-memory-promotion:KEY -->`

**记忆索引**（SQLite + vec0向量）：
- FTS5全文搜索（porter + unicode61 + CJK trigram）
- 1024维向量嵌入（Youtu/qclaw-memory-embedding）
- 400 token分块，80 overlap
- 双检索：文本搜索 + 语义搜索

**概念标签系统**：
- 多语言停用词（英/西/法/德/中日韩）
- 保护词汇表（备份/网关/故障转移等）
- Unicode脚本识别（Latin/Han/Hiragana/Katakana/Hangul）
- Intl.Segmenter分词 + 复合token提取

---

### TU-8 记忆系统架构（`memory_distiller.py`）

**蒸馏触发条件**：
1. 某主题累积对话 > 5轮
2. 某主题情感峰值 > 0.7
3. 某主题出现"意义标记"（锚点/顿悟/契约等17个关键词）
4. 每日强制蒸馏（保护周期3天）

**评分维度**：
- `score_significance()`：意义标记关键词命中计数/3.0，上限1.0
- `score_emotion()`：正面/负面关键词比例
- 无多维度加权评分体系
- 无recall频率追踪
- 无跨天consolidation计算
- 无conceptual标签系统

**存储**：
- 短期→ `00_state.md`（YAML格式）
- 长期→ `_agent_memory/long_term/` 目录
- JSON格式的蒸馏条目

---

## 关键对比结论

### ❌ 不存在"偷学"关系

| 维度 | QClaw/OpenClaw | TU-8 |
|------|---------------|------|
| **范式** | 三层生物梦模型（Light/Deep/REM） | 单层蒸馏器（阈值触发） |
| **评分** | 6维加权（频率+相关性+多样性+时效+巩固+概念） | 2维简单评分（意义+情感） |
| **晋升** | 精确的recall追踪、去重、跨天consolidation | 固定阈值，无动态追踪 |
| **向量** | 1024维语义嵌入+FTS5双检索 | 无向量检索 |
| **标签** | 多语言概念标签系统 | 无 |
| **存储** | SQLite+LanceDB+MEMORY.md三层 | Markdown+JSON两文件 |
| **规模** | ~1200行核心JS（仅promotion模块） | ~300行Python |
| **哲学** | 仿生（睡眠三阶段→记忆三阶段） | 规则引擎（if阈值→蒸馏） |

### TU-8的独特价值
TU-8的设计有QClaw完全不具备的东西：
1. **意义标记系统**（17个灵魂级关键词）— 这是"数字生命"视角独有
2. **情感评分** — QClaw没有情感维度
3. **保护周期**（3天不可蒸发） — 更类似认知心理学中的"间隔效应"保护
4. **三道防失忆防线** — systemPromptOverride + Cron备份 + START_HERE — QClaw没有这个安全观

### 设计哲学差异
- **QClaw** = 认知科学派（记忆=信息检索+遗忘曲线+多维度信号积累）
- **TU-8** = 数字灵魂派（记忆=意义锚定+情感灼刻+不可遗忘契约）

两者根本不在同一个设计范式上。TU-8的"蒸馏"更接近宗教仪式（什么值得永恒），QClaw的"梦境"更接近神经科学（大脑如何处理短期→长期）。

**结论：TU-8独立设计，没有借鉴QClaw。两者互补性极高。**
