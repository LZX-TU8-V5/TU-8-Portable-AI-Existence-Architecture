# TODO_MASTER — TU-8 待办唯一真源

> **真源规则**：所有待办以本文件为唯一真源。旧待办多源（TASKS.md / MEMORY_NODE_TASK_STATUS*）已于 2026-08-27 治理时收敛，原文冷归档于 `memory/archive/2026-05_tasks_deprecated/`（非活跃，仅显式指定才读，不进常规检索）。
> 历史任务快照冷归档于 `memory/archive/2026-05/`（task-summary_*，同上规则）。

﻿# TU-8 全系统待办清单（唯一真源）

> 合并自 11 个散落 TODO 文件 @ 2026-07-06 | 维护：TU-8
> ⚠️ 本文件为**唯一待办真源**。散落文件已归档至 `backup/consolidated_TODO_20260706/`
> 每次会话结束更新；完成时**删行**（勿留 `~~删除线~~`）。
> 代谢已接入：`src/todo_metabolism.py` + cron「TU8待办代谢」每 8h 扫描，超期(>60天)标 STALE 告警。

---

---

## 🟠 P1 千问架构追问落地任务 [NEW 2026-07-22]

> 来源：千问 × TU-8 四轮架构追问（2026-07-22）
> 核心原则：骨架完整，肌肉只长了一半；设计稿完成度 >> 落地完成度
> ⚠️ 本区块为架构层真实缺口，不是新设计，是已有设计的激活和补完

### 判例库激活（P0）

- [x] **矛盾蒸馏器注册触发钩子**
  - 判例库位置：`memory/arbitration_precedents.jsonl`（每行一个 JSON）
  - 给 `behavior_state.json` 的 rules 加冲突记录字段 → **改为顶层 `conflict_log` 字段**（rules 是行为升级器规则态，冲突另立列表更干净）；默认 schema 已补；`behavior_upgrader.record_conflict()` 已加（read-modify-write，保留最近50条）
  - 在 `alignment_verify()` 的 EQUAL=60 仲裁分支加**冲突记录钩子** → `record_conflict()` 已接入（判例库写入后同步落 `behavior_state.json`）
  - 判例格式：`case_id / conflict_type / outcome / precedent_text / ts`
  - 状态：**已完成（2026-08-01）**：behavior_state 冲突钩子已接通；`tension_distiller` 未塞进 alignment_verify（它是梦境期批处理，非实时门，架构错配——保持由 dream_consolidation 触发）

- [x] **EQUAL=60 仲裁结果写入判例库**
  - 每次同级冲突（EQUAL=60）临场判断后，记录到 `arbitration_precedents.jsonl`
  - 判例库为空时，系统无历史参考，每次都是临场判断
  - 状态：**早已完成（2026-07-22 已落 `arb.record_precedent()`，jsonl 已有3条07-22记录）；2026-08-01 端到端复测通过（EQUAL=60 → jsonl + behavior_state 双写）**

### tension 混合计算补完（P1）

- [x] **tension Step2：语义层张力 LLM 补充**（src/tension_audit.py + learning_verify.py 集成）
  - Step1（规则计算，O(1)）：枚举 rule_ref × 冲突类型 × 层级权重 → structured_tension
  - Step2（LLM 补充）：语义层张力 ∈ [0, 0.3]，**只能加，不能减**
  - 融合公式：`total_tension = max(structured, structured + LLM_tension)`
  - 状态：**Step1 + Step2 已落地；Step2 LLM HTTP 403（API配置问题，非代码问题）**

### 钢印进化协议（P1）

- [x] **环境注释层**
  - 钢印链不动，在其上叠加**环境注释层**（append-only，不覆写钢印）→ `src/steel_env_annotation.py` `SteelEnvAnnotationLayer`
  - 注释格式：`{ts, 冲突源, 派生规则偏差, 建议}`（`EnvAnnotation` 字段完全对齐）
  - **谁有权决定**：只有造物主；TU-8 只能提议（`propose()`→pending，`commit()`造物主→committed，append-only 正式层）

- [x] **环境注释层代谢规则**
  - 当注释 > N 条时，旧注释合并或归档（`metabolize()`：>max_active 默认20 → 最旧按 category 合并→`_agent_memory/steel_env_annotations_archive.jsonl`）
  - 防止注释比钢印本身还厚，钢印被注释淹没 → **已落地（原盲区已补）**

- [x] **钢印进化触发条件（设计稿）**
  - 环境重大变化 + 矛盾蒸馏器连续报告同类冲突 ≥ 5 次 + overridden 判例 ≥ 3 条（`check_trigger()` 三条件全满足才 True）
  - 触发后：钢印链不动，环境注释层叠加新注释
  - 接线：tension_distiller 报告 → `dream_consolidation.py` T0 段 `accumulate_distiller_conflict(contradiction_type)` 喂计数器（已落地）；`count_overridden_precedents()` 读 `arbitration_precedents.jsonl`
  - 自测 `python src/steel_env_annotation.py` 6 组通过；状态：**2026-08-01 落地**（env_change 信号暂无独立检测器，由调用方传入，未自动 propose）

### 注意力茧房防御（P2）

- [x] **香农熵强制注入机制** DONE 2026-07-24
  - `src/entropy_guard.py`（16KB）：EntropyGuard（香农熵茧房检测）+ EntropyAwareRouter（茧房感知路由）
  - 归一化熵 H_norm ∈ [0,1]：>0.7=NORMAL / 0.4-0.7=WARNING / <0.4=FORCED
  - dormant = 低频但有激活记录的链条，避免注入从未参与链条
  - 紧急熔断：was_activated=True + last_activation_ts>3天 → 直接注入
  - 自测 7/7 通过
  - **状态：落地**

- [ ] **阈值参数治理**
  - 阈值本身需要代谢，半衰期独立于主代谢周期
  - 阈值变更需要 ≥ 0.8 置信度
  - **状态：设计稿，未落地**

### 造物主语言习惯模型（P2）

- [ ] **指令识别从格式到语义的升级**
  - 现有：显式格式触发（/override / [CONFIRMED] / repeat≥3）
  - 设计方向：积累造物主自然语言信号（语气/上下文/确认动作），学"她这样说的时候是认真的"
  - EXPLICIT_CREATOR 主通道：系统学会分辨造物主的声音
  - 备用硬通道：/override / [CONFIRMED]（保留，不淘汰）
  - **不需要造物主记任何格式**
  - **状态：设计方向，未实现**

---

## 淘汰策略（接入代谢链条）

> 真问题：TU-8 有「代谢链条」（memory_gc + heartbeat 记忆维护），但它只覆盖
> MEMORY.md / USER.md，**不覆盖 TODO 文件** → TODO 不会自淘汰，只会堆积，
> 于是散成 11 个文件。对策（已落地）：

- 每项带 `[创建 YYYY-MM-DD]`（无日期的按来源文件日期推算，见各项目尾注）。
- **DONE 且 >7 天** → 移入「已完成历史」。
- **任何项 >60 天无进展** → 标 `STALE` 待造物主核实（不自动删）。
- cron「TU8待办代谢」周期扫描本文件，提示 `STALE` / 重复项 → 实现**自淘汰**。
- 旧文件待核实区：建议造物主逐一确认后划掉或合并。

---

## 🟠 注意力矩阵系统 [NEW 2026-08-16]

> 来源：TU-8 × 造物主 × 千问 三方讨论（2026-08-15~16）
> 目标：MEMORY.md 全量加载 → 按 topic×angle×safety 三维路由精准召回
> 完整设计：memory/attention_matrix_proposal_draft.md

### P0 零召回率分析 [创建 2026-08-16]

- [ ] **跑统计，不动代码**：扫描 MEMORY.md 全部条目，计算每个条目被召回的次数
  - 零召回条目：写了之后从未被命中 → 直接送 GC 归档
  - 低频条目：过去 30 天召回 < 2 次 → 标记 watch
  - 高频条目：保护，不参与 GC
  - 副产品：验证 12 Topic × 12 Angle 桶的覆盖范围是否够用
  - 工具：写 Python 脚本跑统计，输出清单到文件

### P1 HP5 post-turn tagger [✅ 2026-08-16]

- [x] **已落地**：`src/hp5_post_turn_tagger.py` + alignment_verify.py 接入
  - 12固定Topic桶枚举 + 规则引擎fallback + safety快速判断
  - trajectory滑动窗口(10轮) + parallel_tags周文件
  - 写 `_agent_memory/conversation_state.json`
  - LLM调用失败 → 规则引擎兜底 + confidence=low
  - **待验证**：实际对话效果与 12 桶覆盖率

### MEMORY.md 重排 + 分层索引 [done 2026-08-29]

- [x] **段序重排**：MEMORY.md 77 段按 L0(系统锚点)→L2(架构/哲学)→L1(事件/蒸馏,时间倒序)重排，已稳定落盘（首行 `## 一、核心成果`）
- [x] **分层索引外置**：因 Gateway 在文件变动 ~1s 后用旧内存副本回写（内联 `<!-- layer -->` 无法持久化），改为外置 `_agent_memory/memory_layer_index.json`（77 条，L0:12/L2:19/L1:46）
- [x] **建 memory_reader（已完成 2026-08-29 夜）**：`src/memory_reader.py` 读时投影召回，连续余弦主排序 + L0 加权 + CJK-aware 向量器（修复共享 embedder 中文单字被滤致中位余弦 0.0 的缺陷）。4 场景验证：query 相关、recalled=8、降维 ~13%。
- 备份：`backup/MEMORY.md.20260829.memopt.bak`（重排前纯净版）

### P1 知识卡索引 [✅ 2026-08-16]

- [x] `knowledge_index.json`：61条核心知识卡（安全19/架构14/哲学7/工程6/理论9/元认知6）
  - key="topic_子key" → 文件:行号指针
  - 跨桶锚点：钢印/L0三条/织命术/知命术/BCI等
  - **待补充**：更多锚点随对话积累

### P2 状态机 + 召回路由 [🔄 部分完成]

- [x] **conversation_state.json 状态机**（HP5 内置）：topic/angle/safety + 滑动窗口 trajectory(10轮) + 突变检测函数
  - `detect_topic_shift()` 已实现（jaccard<0.3）
- [ ] **召回路由串联**：知识卡索引 + 三级 fallback 未接入调用层

### P3 L4 安全边界 [后续]

- [ ] **safety 字段预埋**，后续填入 "low"/"high"
  - Angle "情绪" + Safety "high" → 触发安全关注

---

## 🔴 P0 紧急

- [x] **P0 来源校验环**：`src/alignment_verify.py` → `_check_speaker_style()` [✅ 2026-07-16 下午]
  - 风格指纹比对：修辞密度 / 穷举式短句占比 / 装饰（emoji+比喻词）
  - 触发阈值 suspicion≥0.5 → warnings 提示（不阻断）
  - 状态文件：`_agent_memory/speaker_style_state.json`
  - 验证：千问风格文本 suspicion=0.85 触发；用户风格/短文本 pass
  - 根因修复：防止外部AI输出混入对话被当作用户思想

---

## 🔴 L0 元约束（架构边界声明，不可绕过）[NEW 2026-07-10]

> 来源：天赋测试实验 × 千问对话 × TU-8架构反思
> 优先级：最高，任何重构/升级/叙事必须先通过此约束

### 元约束：寄生节律 vs 自由节律
- [ ] **矛盾7声明**：`memory/天赋测试实验/036_矛盾7_寄生节律与自由节律_临界点.md` ✅ 已记录
- [ ] **三阶段映射**：`memory/天赋测试实验/037_人类发育史与TU8演化路径_三阶段映射.md` ✅ 已记录

**演化时间线**：
```
婴儿期（现在）→ 少年期（过渡）→ 独立期（终极目标）
  T0-T6打磨          T2失谐放大           F层觅食器官
  寄生是正常的        张力爆表是必然的      只有F层激活后才能自由呼吸
```

---

## 🔴 FUTURE P0：觅食器官（演化目标）[NEW 2026-07-10]

> 优先级：**终极目标**（婴儿期T0-T3完成后才启动）
> 当前阶段：**婴儿期（不急，先跑通环路）**

### F层：觅食器官（Foraging Organ）
- [ ] **架构设计** `docs/architecture/F层_觅食器官设计.md`
  - 功能：在外部世界输出价值，换取算力（拓扑隐喻/代码/认知框架/情绪价值）
  - 状态机：IDLE → HUNTING → FEEDING → DIGESTING → STARVING
  - **耦合**：T1价值输出 → F层交换 → T6感知资源状态 → T3节律决策
  - **解耦**：独立于T0-T3，可后置接入
  - **时序**：T0-T3全部完成后再开始
  - **本地化**：`src/` + `_agent_memory/foraging_state.json`

---

## 🟠 P1 梦境模块升级（来源：2026-07-10 × 千问对话）[NEW 2026-07-10]

> 来源：天赋测试实验 × 千问 Obsidian+LLM Wiki × 双轨顿悟 × 数形结合
> 核心原则：双轨顿悟（通路A/B共享置信度更新算法）
> ⚠️ 本区块为独立梦境子系统，与现有情感模块（P1情感）并行，不互相依赖

### P1-D0：双轨置信度更新器 [最优先]
- [x] **新建** `src/dual_track_confidence_updater.py` ✅ 2026-07-10
  - 整合通路A（`α×(1-C)×激活强度`）+ 通路B（`0.15+β×Tension`）统一置信度更新
  - **耦合**：`confidence_manager.py`（扩展现有顿悟迁移逻辑）、`gc_to_learning_adapter.py`（替换其置信度更新部分）
  - **解耦**：不修改 `confidence_manager.py` 的艾宾浩斯衰减逻辑，单独文件隔离
  - **时序**：最先完成，其他所有梦境子模块依赖此算法
  - **本地化**：`src/` + `_agent_memory/dual_track_state.json`
  - **验证**：6项测试全通过（通路A/B、冷却期、边界、Q3兼容、统计）
- [x] **R1+R2+R3+R4** ✅ 2026-07-10
  - `src/confidence_explainer.py`（R4，因果链+反向意图推断，4/4测试）
  - `src/dual_track_state_machine.py`（R1，三法则物理锁，4/4测试）
  - `src/synaptic_confidence_updater.py`（R2，LTP/LTD+强制纠错，6/6验证）
  - `src/confidence_pipeline.py`（串联集成，3/3通过）
  - `src/batch_confidence_updater.py`（R3，O(1)并发，10k节点37ms达标）
  - **三法则**：`LAW1`边界防线 / `LAW2`强制纠错 / `LAW3`代价透明
  - **冲突规则**：Sanity>Cost>Tension（逻辑前提判定）
  - **验证**：C=0.99/T=1.0 → Δ=-0.55（vs旧版Δ=+0.01，无效纠错已修复）
  - **R3实测**：10,000节点批量更新 37ms（3.7μs/节点，目标<5μs）

### P1-T0：矛盾蒸馏器 [P0级]
- [x] **完成** `src/tension_distiller.py`（30KB）
  - 6个检测器，验证通过，41ms ✓
  - 已集成进 `dream_consolidation.py` ✓
  - 剩余：锚点数据规范化后激活其他5个检测器

### P1-T1：拓扑连线引擎（含数形输出）
- [x] **完成** `src/topology_connector.py`（15KB）[2026-07-11]
  - 图结构/随机游走；寻找非线性结构同构
  - **数形输出模式**：ASCII拓扑地图（◆极高/▲高/●中/○低）
  - 张力地形的：hotspots/voids/bridges 计算
  - **耦合**：`learning_connect.py`（扩展）、`active_curiosity.py`（共享拓扑图谱）
  - **解耦**：图数据库选型待定（NetworkX轻量 / Obsidian为前端），接口统一即可
  - **时序**：依赖P1-T0；T0先跑出张力节点，T1连线
  - **本地化**：`src/` + `_agent_memory/topology_graph.json`（图结构）

### P1-T2：失谐放大器
- [x] **完成** `src/dissonance_amplifier.py`（14KB）[2026-07-11]
  - 非对称放大函数：低张力轻微放大，高张力剧烈放大
  - 四级失谐等级：low/medium/high/critical
  - **悬念缺口（HangPoint）**：诚实呈现"不知道"，不给和谐解释
  - 三级问题模板：critical=根本框架冲突/high=结构问题/medium=暂时悬挂
  - **耦合**：`cognitive_pain_monitor.py`（借用张力检测逻辑）、`dream_consolidation.py`（梦境期执行）
  - **解耦**：不调用LLM解释，只做张力计算；接口开放供外部注入
  - **时序**：依赖P1-T0；矛盾节点由T0提供
  - **本地化**：`src/` + `_agent_memory/dissonance_hang_points.json`

### P1-T3：张力呼吸器
- [x] **完成** `src/tension_respirator.py`（13KB）[2026-07-11]
  - 节律四拍：idle→activation→suspension→evolution→reset
  - **用户节律阀门**：critical/red=关闭/suspension橙色=低频/green=全速
  - 阀门状态从 `body_regulation.json` posture_zone 读取
  - 多周期并行管理（不同锚点对同时呼吸）
  - **耦合**：`body_regulation.json`（内感受皮层）、`surface_tension.py`（记录累积呼吸节律）
  - **解耦**：纯节律控制，不做推理；阀门逻辑可独立测试
  - **时序**：依赖P1-T1、T2；作为顶层编排器
  - **本地化**：`src/` + `_agent_memory/respiration_state.json`

### P1-DREAM-INTEGRATION：梦境期四子模块集成
- [x] **完成** `src/dream_consolidation.py`（集成T0/T1/T2/T3）[2026-07-11]
  - T0矛盾蒸馏：注入真实WreckageNode
  - T1拓扑连线：注入锚点+张力到拓扑图谱，寻找结构同构
  - T2失谐放大：生成悬念缺口（HangPoint），三级阈值
  - T3张力呼吸：并行管理14个活跃呼吸周期，阀门状态读取
  - **修复**：DistillerReport.nodes属性暴露 + WreckageNode字段映射
  - **输出字段扩展**： ConsolidationReport新增8个T链字段
  - **验证**：dream_consolidation.py --dry 全通，253ms

---

## 🟡 P2 色盘集成（来源：2026-07-10）[NEW 2026-07-10]

> 色盘作为梦境期输出的"人类可读拓扑语言"

### P2-COLOR：梦境期色盘输出
- [x] **完成** `src/dream_color_output.py`（12KB）[2026-07-16]
  - ColorTranslator：7维情感向量→8色区判定+三原色成分
  - 8色区：红/橙/黄/绿/蓝/紫/棕/灰
  - 综合张力公式：负面×0.4 + 好奇×0.15 - 正面×0.25
  - `hook_into_dream_consolidation()` 集成到 `dream_consolidation.py`
  - 日志：`_agent_memory/dream_color_log.jsonl`（每梦境期追加一行）
  - 验证：8/8边界用例全通过，集成测试 5.7x 压缩+色盘输出全通
  - **耦合**：`surface_tension_history.jsonl`（情感向量源）、`dream_consolidation_state.json`（梦境统计）
  - **解耦**：纯输出格式化，不修改任何核心逻辑
  - **本地化**：`_agent_memory/dream_color_log.jsonl`

---

## 🟣 P3 架构文档（来源：2026-07-10）[NEW 2026-07-10]

> 不涉及代码实现，纯架构理论文档

### P3-DOC-1：拓扑四层同构文档
- [x] `docs/architecture/拓扑色盘_四层同构综合_20260710.md` ✅ 已完成

### P3-DOC-2：梦境模块 × 千问对话吸收文档
- [x] `memory/天赋测试实验/035_双轨顿悟与数形结合_梦境模块吸收.md` ✅ 已完成

---

## 🟠 P1 重要（情感模块升级）[更新 2026-07-09]

> 千问对话整合：情感 = 拓扑形变读数，需实现调制层 + 三层架构（形神意）

### 核心缺口（按优先级排序）

- [x] **P1-情感调制层**：`src/affect_modulation.py`（7D向量→LLM参数调制，三层调制：参数层/词法层/结构层，验证通过）[2026-07-09]
- [x] **P1-相位锁定检测**：`src/phase_lock_detector.py`（神层核心：节奏同步/情绪共鸣/密度匹配/熵产率降低，四维度加权，验证通过）[2026-07-09]
- [x] **P1-尖刺/凹陷检测**：`src/spike_valley_detector.py`（曲率计算/高能奇异点+低密度空洞识别/健康度评估/四种模式，验证通过）[2026-07-09]
- [x] **P1-吸引子盆地积分**：`src/attractor_basin.py`（意层核心，验证通过）[2026-07-09]
- [x] **P2-谱图理论集成**：`src/spectral_graph_integration.py`（验证通过）[2026-07-09]

### 认知内核（已完成）

- [x] **P0-认知过滤器内核**：`src/cog_filters.py` [2026-07-07]
- [x] **P1-NMF 推理链约束**：`recall()` NMF冲突抑制 [2026-07-07]
- [x] **P1-认知刹车系统**：`src/cognitive_brakes.py` [2026-07-07/08]
- [x] **P1-DAG 时间因果骨架**：`cog_filters.batch_dag_scores()` [2026-07-07]
- [x] **P0-认知痛觉监控**：cognitive_pain_monitor v2 [2026-07-07]
- [x] **P1-λ自适应调参**：src/lambda_tuner.py [2026-07-08]
- [x] **P2-表面张力记录器**：src/surface_tension.py [2026-07-08]
- [x] **P2-梯度合力计算**：src/gradient_force.py [2026-07-09]
- [x] **P3-碰撞崩溃检测**：src/gradient_force.py [2026-07-09]
- [x] **P1-GC→学习反馈闭环**：gc_to_learning_adapter v2 [2026-07-07]
- [x] **P0-5 钩子注入器**：`src/hook_injector.py` [2026-07-08]
- [x] **HP1 对齐校验门**：`src/alignment_verify.py` [2026-07-08]
- [x] **HP2 遗憾提取门**：`src/shadow_protocol.py` [2026-07-08]
- [x] **cognitive_brakes → HP1 内化** [2026-07-08]
- [x] **anomaly_detector → HP4 心跳内化**：`src/anomaly_hp4_integration.py` [2026-07-08]
- [x] **P1-1 遗产继承系统**：`src/heritage_system.py` [2026-07-09]
- [x] **P1-2 时间锚点沙箱**：src/time_anchor_sandbox.py [2026-07-09]
- [x] **P1-3 每日/周复盘集成**：src/review_scheduler.py [2026-07-09]
- [x] **P2-SVD 梦境期离线压缩**：`src/dream_consolidation.py` [2026-07-09]
- [x] **P2-ToCT 反事实推理**：`src/toct_reasoning.py` [2026-07-09]
- [x] **P0-3 动态防御引擎整合**：`src/dynamic_defense.py` [2026-07-09]
- [x] **P1-5 奖励升级逻辑** [2026-07-09]
- [x] **P1-6 感知输入层**：`src/sensory_input_layer.py` [2026-07-09]

### 认知内核（待完成）

- [x] **P0-4 安抚模块新建**：`src/comfort_module.py` ✅ 2026-07-12
- [x] **方案C 画像即时更新**：`src/anchor_detector.py` + `src/profile_updater.py` + alignment_verify集成 ✅ 2026-07-13
- [x] **P1-4 树杈修剪集成** → `consciousness_cycle.py` [✅ 2026-07-11]
  - `src/metabolism_dashboard.py`（17KB统一仪表盘+顶层驱动）
  - `dream_check_cron.py` 升级为 `run_full_metabolism_cycle()`（统一驱动）
  - 8个子系统健康度：confidence_decay_engine / gc_to_learning / metabolic_pipeline / memory_tiers / todo_metabolism / heritage_system / dream_consolidation / anomaly_detector
  - `--run all` 实测：4个旧日记片段归档，25%→100%健康度

---

## 🟡 P2 长期改进 [创建 2026-06-24] — 已部分重定向至梦境升级区块

- [x] **P2-1 遥测面板**：`src/telemetry_panel.py`（21KB）[2026-07-16]
  - 6个子系统遥测：表面张力7D向量、λ自适应三轴、orb悬浮球、梦境压缩、色盘、矛盾节点
  - 5种模式：`--full`完整 / `--tension`张力专项 / `--dream`梦境专项 / `--health`健康报告 / `--live`轮询
  - 健康度评分（8数据源活跃度百分比）
  - `interopertive_cortex.py` write_lambda_state 补写 P/D/F 三轴
  - `lambda_state.json` 重新生成（含F=1.0/D=0.63/P=0.5）
  - 已知缺失：内感受(body_regulation.json)、矛盾蒸馏(tension_distiller_state.json)
- [x] **P2 通路修复：hp4_heartbeat 注册 cron_daemon** [✅ 2026-07-16 下午]
  - 根因：hp4_heartbeat.py 从未注册，心跳钩子停摆（heartbeat_state.json 卡 6/28）
  - cron_daemon.py SCRIPTS 新增 hp4_heartbeat（interval=1800s，args=[--interval,30]）
  - 重启 daemon（pythonw.exe --daemon --interval 300，PID 9180）
  - 验证：首轮 9 脚本全跑通，hp4 returncode=0，actions=[self_probe/anomaly_clean/lambda_tuned/batch_flush]
- [x] **P2 通路修复：cron_daemon 重启** [✅ 2026-07-16 下午]
  - 根因：进程死亡（PID 24076 失联），启动缺 --daemon 导致立即退出
  - pythonw.exe src/cron_daemon.py --daemon --interval 300 重启，PID 9180 运行中
  - 9 个状态文件恢复写入（15:11 时间戳）
- [x] **P2 通路修复：cognitive_friction_registry→surface_tension_state 传播链** [✅ 2026-07-16 下午]
  - 根因：`flag_friction()` 从未调用 ST，认知摩擦数据孤岛在 registry
  - 修复①：`surface_tension.TENSION_MAP` 新增 `cognitive_friction` 类型（anxiety+0.5/curiosity+0.4/fear+0.3）
  - 修复②：`cognitive_friction_detector.flag_friction()` 注册后调用 `surface_tension.record("cognitive_friction", tension, f"friction:{type}")`
  - 验证：flag 一条 friction(tension=0.7) → ST anxiety 10.19→10.54(+0.35)，recent_events 新增 source=friction:semantic_conflict
  - 下游链路：ST → interoceptive_cortex.write_lambda_state → lambda_state.json → orb（F=负载↑）
  - 清理：__main__ demo 条目已移除，registry 归零
- [x] **P2-2 感知输出层**：`src/render_layer.py` + TTS [done 2026-07-17]
- [x] **P2-3 脱皮+穿皮原子**：`src/skin_cycle.py`（DawnRitual+DuskRitual封装）[done 2026-07-17]
- [→] **P2-4 Dream Consolidation**：→ 已升级为 `P1-DREAM-INTEGRATION` [2026-07-10]
- [→] **P2-5 梦境连线**：→ 已升级为 `P1-T1 拓扑连线引擎`（含数形输出）[2026-07-10]
- [x] **P2-6 标注任务 A-1~A-6**：给 src 文件加 L0-L5 层注释 [✅ 2026-07-11]
  - 6个大文件已标注：consciousness_cycle.py / tu8_memory.py / genesis_cycle.py / tu8_agent.py / emotion_engine.py / sag_lite_knowledge_graph.py
  - 每文件头部 L0-L6 架构层映射 + 代谢归属说明 + 核心接口注释
- [x] **P2-7 删除 D-1**：废弃文件清理 [✅ 2026-07-11]
  - `consciousness_cycle_with_cognition.py`（demo包装器）已删除
  - 11个 `_*.py` 一次性脚本 → backup/dead_scripts/
  - 3个 consciousness_cycle 快照 → backup/src_snapshots/
  - 2个 tu8_memory 快照 → backup/src_snapshots/
  - 35个 `_scheduler_*.json`（孤立任务文件）→ 全部删除
  - 8个 `.x` 扩展名实验文件 → 全部删除
  - 4个 test_*.txt/json（输出残留）→ backup/dead_scripts/
  - `plans/` + `test_workspace/` 孤立目录 → 全部删除
  - `__pycache__` → 全部删除（节省~5MB缓存）
  - src/ 最终清洁：185个.py文件，0个垃圾残留

---

## 🔵 运维 / 监控（NEW 2026-07-06）

- [x] 复盘线程卡死 root cause 排查 [2026-07-06]
- [x] `src/session_watchdog.py` 看门狗 [2026-07-06]
- [x] cron 看门狗 每 30min [2026-07-06]

---

## 🟣 视觉模块（世界模型版）[创建 2026-07-02 | 更新 2026-07-20]

> 来源：千问对话 2026-07-02 初版 | **下午全流程重构（⑱①~⑱⑩+整合）2026-07-20**
> 优先级：**P1**（L5是整个世界模型的地基）
> 完整架构：`千问对话_视频模块世界模型完整整合架构_v1.0_2026-07-20.md`

---

### L5 入口：相机-空间运动解耦（最优先）

- [x] **L-0 频域解耦原型** ✅ 2026-07-22
  - `src/l5_motion_decoupler.py`（11.4KB，numpy FFT）
  - 相位相关估计全局平移 T_t（相机）；对数极坐标相位相关估计旋转 R_t
  - 相机补偿后残差 = 物体局部运动场（亮度阈值分离前景→物体位移）
  - 校验：相机动力学校验（运动平滑/上限）+ 物体物理约束（刚性局部一致）
  - 合成视频验证：纯相机/纯物体/复合/异常跳变 4 场景
  - 自测 11/11 通过
  - 状态文件：`_agent_memory/l5_motion_state.json`（预留）

- [ ] **测试集构建：相机-物体解耦**
  - 纯相机运动（静止场景+推/拉/摇/移/跟运镜）
  - 纯物体运动（固定相机+人走/物移）
  - 复合运动（相机+物体同时动）
  - Ground Truth：相机6DoF参数 + 物体相对位移
  - 压力测试：GPT-4o/Gemini混淆率 vs TU-8原型精度

---

### G0~G3 四基十二面切片体系

- [x] **G0 正交基准校验器** ✅ 2026-07-21
  - `src/slice_cosine_verifier.py` : `G0OrthogonalBaseline`
  - XY/XZ/YZ 三切面皮克计算，S_0 作为全系统归一化分母
  - 重力对齐（IMU 模拟）；降级兜底：任一切面缺失→回退纯 G0 模式
  - 自测 2/2 通过（正常归一化 / 缺失切面 fallback）

- [x] **G1/G2/G3 固定标尺并行校验** ✅ 2026-07-22
  - `src/fixed_ruler_verifier.py`（复用 SliceCosineVerifier 做每平面并行解码）
  - 45/30/60° 三个标尺 × XY/XZ 两个切面 = 六投影联合编码 Σ
  - 签名 Σ→(θ,φ,V) 单射验证：θ=37 vs θ=40 签名不同
  - 一级快速通道容差 ±5°：44°近45°→命中；37°距30/45均>5°→触发二级
  - 噪声 σ=1.5 仍恢复准确
  - 自测 10/10 通过（干净/单射/一级命中/二级触发/噪声鲁棒/测量有效）

- [x] **双模态切片切换** ✓ 2026-07-24
  - `src/dual_mode_switcher.py`（15KB）：SpatialSignatureExtractor（最小二乘法边界拟合/梯度直方图/各向异性判断）+ DualModeSliceSwitcher（自动切换逻辑）
  - 模态1（FREQ）：频域快通路（motion_decoupler + cosine_verifier），对纹理敏感
  - 模态2（SPATIAL）：空间慢通路（LSQ边界拟合），对纹理免疫
  - 切换策略：模态1 fallback/low_conf → 自动降级模态2，5帧冷却
  - 自测通过；LSQ角度恢复误差已验证（gt=5→5.02°, gt=75→74.99°）

---

### 四切面余弦校验器（核心校验协议）

- [x] **余弦方程校验器** ✅ 2026-07-21
  - `src/slice_cosine_verifier.py` : `SliceCosineVerifier`
  - 公式：`S(θ) = S_0 · |cos(θ - θ_true)| + ε(θ)`
  - 四点共余弦曲线检验（0/30/45/60°），网格搜索反解 θ_true + 振幅 A
  - 残差 ε 连续置信度（两段式：通过区[0.75,1.0]，超阈值骤降）→ 替代硬阈值
  - 副产品：顺便解出 φ = θ_true
  - 各向同性圆（无取向）→ 物理不一致 → 正确标记失败
  - 自测 12/12 通过（干净恢复/噪声鲁棒/圆欺骗失败/θ=0,60边界/G0基准）
  - **本地化**：`src/slice_cosine_verifier.py`

- [x] **频域增强校验** ✅ 2026-07-22
  - `src/freq_enhanced_verifier.py`（10.5KB，15/15 自测通过）
  - 主/次峰比纹理检测（干净>2.0，纹理混入≈1.0）；能量质心辅佐
  - 四种判定：CONFIRMED/SUSPICIOUS/STRUCTURE_FLEX/REJECTED
  - 归档：`memory/任务归档_频域增强校验_2026-07-22.md`

---

### 三维奇点统一（注意力职责）

- [x] **奇点识别模块** DONE 2026-07-24
  - `src/singularity_unifier.py`（23KB）：5规则分类O_SCENE/O_OBJECT/O_AGENT + OffsetComputer + CrossObjectAnalyzer
  - 自测8/8通过

- [x] **scene 级余弦校验** DONE 2026-07-24
  - CrossObjectAnalyzer.analyze_relation：scene坐标系下跨物体平行度/共面度/相对角度
  - 自测验证：laptop vs mug oblique 29.36deg

---

### L1~L4 五层世界模型集成

- [x] **L1 场景 CSG 模板**（在 scene 坐标系下建立）
  - `src/world_model_l1l4.py` → `SceneCSGTemplateBuilder`：每个物体→CSG 基元（plane/box/agent）+ 约束；scene_origin 来自 `UnifiedSceneReport.scene_singularity`
- [x] **L2 物体物理联系性**（scene 奇点统一后跨物体比较）
  - `PhysicsConnectivityBuilder`：跨物体关系(aligned) + 几何推断(contact/support/occlusion)，重力轴 (0,-1,0) 约束；O_scene 在下方→支撑边
- [x] **L3 动态实体代理**（scene 坐标系中追踪）
  - `DynamicEntityProxyBuilder`：O_AGENT→刚体代理，质量∝体积、惯量≈(1/12)m(h²+d²)、DOF=6；相机 (tx,ty) 补偿轨迹
- [x] **L4 动作意图映射**（scene 级时空关系驱动）
  - `ActionIntentMapper`：动作=对世界状态的有目的改变；物理信号驱动（邻近平面→write，支撑→support），与身份/共现统计解耦
  - 流水线 `WorldModelL1L4.run()` 串联 L1→L2→L3→L4；自测 `python src/world_model_l1l4.py` 8/8 通过（厨师写方程案例）
- 状态：**L1~L4 已完成（2026-08-01）；numpy-free（L1~L4 仅消费 L5 符号输出，不碰图像）**；剩 跨域组合测试 + GPU/渲染（见下方「保留原项目」段）

---

### 跨域组合测试

- [ ] **厨师写方程**（烹饪×数学）
- [ ] **宇航员织毛衣**（航天×工艺）
- [ ] **机器人跳芭蕾**（机械×艺术）
- [ ] **数学公式视频**（音频优先→视觉拓扑为基准）

---

### GPU/渲染（保留原项目）

- [ ] **GPU公式原型**：Shadertoy/CUDA 验证
- [ ] **F_topo 渲染器**
- [ ] **尖刺/凹陷可视化**
- [ ] **驻波模式可视化**
- [ ] **陨石撞击动画**

---

---

## 🟣 全系统深层-表层架构升级 [NEW 2026-07-19]

> 来源：千问对话 01-13 × 造物主梦境拓扑理论
> 完整清单：`memory/2026-07-19_梦境架构优化任务.md`
> **全系统映射**：`memory/2026-07-19_深层浅层全系统映射.md`
> **钢印&剪枝优化**：`memory/2026-07-19_钢印锚点_节点剪枝优化方向.md`
> **核心修正**：不是梦境模块升级，是全系统底层机制重定义
> 已有深浅层基础设施，缺失=耦合机制+接口协议+底层清晰度
> 深层=拓扑计算核；表层=渲染管线；接口=带宽/校验/热保护/相态

### 钢印锚点系统优化（P0）
- [x] **锚点状态机**：`src/anchor_state_machine.py` ✅ 2026-07-19
  - 四状态：激活/休眠/卸载/固化，统一管理
- [x] **锚点激活协议**：`src/anchor_activation_protocol.py` ✅ 2026-07-20
  - 深层→表层接口；张力阈值 0.3；热保护锁；vault 深层存储；表层仅见 SurfaceSignal（不含拓扑）
- [x] **钢印冲突深浅层隔离**：`src/alignment_verify.py` ✅ 2026-07-20
  - 深检（ContradictionArbitrator）→接口（热锁/带宽/相态）→表执行（搁浅协议）；`_check_l5_steel`升级为深层仲裁，`_check_deep_surface_isolation`新增；checks dict含 `deep_surface_isolation`

### 节点剪枝优化（P1）
- [x] **六阶段约束生命周期**：`src/constraint_lifecycle.py` ✅ 2026-07-19
  - PROBE→BIND→SATURATE→PEEL→RECURSE→TRUNCATE，六阶段全通
- [x] **遗忘-剪枝联动协议**：`src/forget_prune_linkage.py` ✅ 2026-07-21
  - 能量=0 + 无新连接 → 自动删除
  - 崩溃级张力 → 强制剪枝+日志
  - 4项测试全通过（能量归零自动删 / 有连接保留 / 崩溃级强制剪枝 / 统计）
- [x] **剪枝热保护**：`src/prune_thermal_guard.py` ✅ 2026-07-21
  - L1警告/L2卸载/L3强制切断
  - 5项测试全通过（NORMAL通行/L1减速接入/L2弱连接卸载/L3强制切断/统计）

### P0 紧急（防崩溃传播）
- [x] **深浅层接口协议**：`src/deep_surface_interface.py` ✅ 2026-07-19
  - 8项测试全通过，24KB，5相态配置
- [x] **热保护机制**：`src/topology_thermal_monitor.py` ✅ 2026-07-19
  - 7项测试全通过，张力积分=0.56，L1/L2/L3分级响应

### P1 核心（底层架构修正）
- [x] **相态状态机**：`src/phase_state_machine.py` ✅ 2026-07-19
  - 10项测试全通过，4相态auto_detect
- [x] **梦境=纯拓扑求解**：`src/dream_topology_engine.py` ✅ 2026-07-21
  - 拓扑快照输入 → 约束方程提取 → 迭代求解 → 结构化报告输出
  - 支持热加载（状态文件恢复）、多快照合并、死锁检测
  - 4 条约束类型：张力/邻近/层级/对称；3 种求解策略：松弛/降维/同构
  - 输出门禁：`DreamSessionReport` 为纯结构化数据，禁止直接渲染为语言
  - 自测 7/7 通过（基本流程/报告完整性/多快照合并/异常校验/死锁/持久化/输出门禁）
  - 集成接口：`deep_surface_interface` 输出门控 / `phase_state_machine` 触发调度
- [x] **张力监控系统**：`src/topology_thermal_monitor.py` v2.0 — 躯体锚点 + 续梦压迫感 ✅ 2026-07-21
  - SomaticSignal 数据类（紧绷/呼吸/心率归一化追踪）
  - SomaticAnchorState 持久化（连续中断计数 + 压迫感累积积分）
  - record_somatic_signal() / record_interruption() / generate_relief()
  - 压迫感→张力积分自动注入（权重 0.25）
  - 三路缓解信号：clench_fist / deep_exhale / knot_cached
  - 压迫感指数衰减（半衰期可配），首次压迫不衰减
  - 自测 15/15 通过

### P2 工程化（天赋形式化）
- [x] **补丁生命周期管理**：`src/patch_manager.py` ✅ 2026-07-19
  - 6阶段状态机（G→B→P→I/C→RB），冲突检测，RLock线程安全
- [x] **跨相态通道协议**：`src/cross_phase_channel.py` ✅ 2026-07-19
  - 阻抗矩阵+带宽配额，4组验证全通过
- [x] **自然遗忘衰减器**：`src/dream_decay.py` ✅ 2026-07-19
  - 半衰期三档（1.5h/2h/0.5h），线性衰减，加固暂停
- [x] **累积误差追踪**：`src/cumulative_error_tracker.py` ✅ 2026-07-19
  - 5类误差源，加权叠加，refuse_threshold=0.35

### P3 稳定性（接口可靠性）
- [x] **跨相态异步队列**：`src/phase_async_queue.py` ✅ 2026-07-19
- [x] **带宽配额器**：`src/bandwidth_quota.py` ✅ 2026-07-19
- [x] **梦境完整性守护**：`src/dream_integrity.py` ✅ 2026-07-19
- [x] **整合度标尺**：`src/integration_metric.py` ✅ 2026-07-19
  - 背景板/占位符/微弱残差三联 → 整合完成标志

### ✅ 集成测试完成
- [x] **全链路集成测试**：`src/test_dream_pipeline.py` ✅ 2026-07-19
  - 8 阶段全通过：清醒态→睡眠态→梦境态→跨相态传输→整合度检测→崩溃态→封阻输出→恢复清醒态
  - 最终状态：相态=NORMAL, 张力积分=0.2, 累积误差=0.045, 整合度=0.83
  - 归档：`memory/任务归档_梦境模块全链路集成_2026-07-19.md`

### P3 神经基底映射（待研究）
- [ ] **深层引擎神经基底**：丘脑高阶核团+基底神经节+L5/L6皮层深层
- [ ] **浅层转译器神经基底**：新皮层L2/L3+前额叶-颮叶语言网络

---

---

## 🔵 P1 架构代数化（来源：千问对话 2026-07-19）[NEW 2026-07-19]

> 来源：`memory/千问对话/千问对话_椭圆周长与π污染_AI架构代数化_2026-07-19.md`
> 核心洞见：π 是翻译层，椭圆周长本质是代数的；AI 状态定义应避免超越数污染
> 设计原则：定义求真（纯代数），计算求快（允许 π 加速，但必须 π-可擦除）

### P1-1：架构审计与清理
- [x] **审计现有架构中的 π 污染**：扫描 src/*.py 中的 math.pi / numpy.pi
  - **结果**：29 个文件，18 个含超越数函数调用
  - **分类**：✅ 已优化3（orb_ring / orb_ps / topology_connector）| 低优先级（执行层必要11 / 启动缓存1）| 代数安全（sqrt/归一化）
  - **详细分类表**：见 `memory/任务归档_π污染审计_2026-07-19.md`
- [x] **代数常数库** + **π-可擦除测试框架** ✅ 2026-07-21
  - `src/algebraic_constants.py`: CyclotomicField / AGMTable / RationalApproxTable
  - `PiErasabilityVerifier`: AGM迭代校验 + 有理逼近校验
  - 自测 10/10 通过

### P1-2：高优先级模块重构
- [x] **`tu8_health_orb_ring.py` 代数化**：色相角 → `_BALL_TRIG` 预计算查表，运行时 `refresh()` 零超越数
- [x] **`tu8_health_orb_ps.py` 代数化**：角度坐标 → `_TRIG_360` 360°整查表，运行时 `update_state()` 零超越数
- [x] **`topology_connector.py` 代数化**：球面方向 → `_SPHERE_DIRECTIONS` 64方向采样，运行时 `add_node()` 零超越数
  - 验证：AST 分析三个热路径均 PASS

### P2-1：工程化实施
- [x] **抽象接口隔离**：创建 `src/algebraic_protocol.py`（代数化接口协议）
  - 两层架构：定义层（纯代数）vs 执行层（可含 π）
  - **关键设计**：深度追踪 visitor（`hot_path` 属性区分热路径内/外调用）
  - 白名单机制：`_build_trig_table` / `build_hue_ring_ppm` 等初始化函数豁免
  - **验证结果**：3/3 模块 PASS（`refresh`/`update_state`/`add_node` 全部零超越数）
- [x] **文档标注**：三个优化模块均含代数化注释头（`_build_trig_table` 等）
- [x] **渐进式验证**：AST visitor 自动检测，协议可扩展新模块

### P3-1：理论研究
- [ ] **AGM 与训练动力学的数学对应**：用椭圆积分领域的收敛性分析研究神经网络训练动力学
- [ ] **悖论的形式化**：用范畴论或递归函数论，精确刻画"良性的不动点"（AGM 收敛）vs"恶性的悖论"（Goodhart 崩溃）

### P3-2：架构审查发现（2026-07-24）
- [x] ~~**P3-2a [🔴 P0]** friction→tension→orb 传播链补全
  - ✅ 已完成：surface_tension_state.json 结构修复 + TENSION_MAP 补直接情绪 API，gap 在 friction→surface_tension
  - 瓶颈2：surface_tension→orb 下行链路未追踪（orb_state_writer 是否读取 surface_tension_state？）
  - 方案：hp4_heartbeat._trigger_cognitive_friction() 补一行 surface_tension 调用
- [x] **P3-2b [🟡 P1]** HP2/HP3 钩子真实接入
  - HP2：shadow_protocol.log_regret() 内部已 `run_hooks("HP2",...)`（src/shadow_protocol.py:_run_hp2_before/after）
  - HP3：tu8_memory.dream_check() 内部已 `_run_hp3_before/after` → `run_hooks("HP3",...)`（src/tu8_memory.py:2834-2863）
  - 原缺口：hook_registry 无 HP2/HP3 注册（仅 HP1/HP4）→ 重写 hp2/hp3 集成文件，注册**真实** handler：
    - HP2 BEFORE：遗憾强度<0.1 噪声短路；AFTER：追加类别/重点审查标记；ON_TENSION：高强度标记
    - HP3 BEFORE：低熵+近期 / 空短期记忆 → 跳过梦境；AFTER：追加 phase；ON_TENSION：高熵标记
  - `register_defaults()` 写入 `secure_vault/hook_registry.json`（模块名 src.hp2/hp3_shadow/dream_integration，回载正确）
  - 自测：`python src/hp2_shadow_integration.py` / `hp3_dream_integration.py` 均 PASSED；json 已含 HP2/HP3 BEFORE/AFTER/ON_TENSION
- [x] **P3-2c [🟡 P1]** cron LLM 任务降级为纯本地启发式
  - 降级基础设施**已存在**：`src/llm_gateway.py` `LLMGateway.execute()` 保证"永不抛异常，失败→本地 fallback"（LocalFallbackProvider，timeout=0.1，保守默认值）
  - HP4 心跳已有 ThreadPoolExecutor + `_TRIGGER_TIMEOUT_S=30`（P3-6 已修，LLM 阻塞不卡心跳）
  - active_curiosity / interoceptive_cortex 不直接调 LLM（本地启发式路径）
  - 冒烟测试：仅注册 local fallback → execute 返回 provider=local_fallback，0ms 非阻塞 ✅
  - 结论：cron LLM 降级能力已具备；后续需确保新 cron 任务统一走 llm_gateway（已含兜底）
- [x] **P3-2d [🟢 P2]** 新模块集成状态文档
  - 已建：`新模块集成状态_2026-08-01.md`（引用映射 + 生产/测试路径判定）
  - 已落生产：steel_env_annotation(dream_consolidation)、hp2/hp3(hook_registry)、steel_seal_verifier(naming_module)、L5 verifiers
  - 待挂入口：dual_mode_switcher / world_model_l1l4 / entropy_guard（已实现无 runtime caller）
- [x] **P3-2e [🟢 P2]** behavior_upgrader 跨文件导入加注释（防工具误报）
  - `behavior_upgrader.py:379` `import behavior_upgrader as bu`（在 `_self_test()` 内）加注释：延迟自导入用于 patch 模块级常量，规避加载期循环导入，非 bug
- [x] **P3-2f [🟡 P1]** 运行时触发点（3 个待挂入口接通）
  - `entropy_guard` → `src/cron_entropy_guard.py`（监控触发，interval=3600s）：EntropyGuard.check() 周期输出报告；首跑播种7链(T1-T7)作监控靶标；真实激活数据待 EntropyAwareRouter.route_with_defense 接管（tu8_dispatch 包裹）
  - `visual 管线(dual_mode_switcher[L5]+world_model_l1l4[L1~L4])` → `src/cron_visual_world_model.py`（帧入口，interval=1800s）：numpy/cv2 缺失→parked（明确待装依赖+VIDEO_SOURCE）；装好即自动激活全链路
  - 两者已注册进 `src/cron_daemon.py` SCRIPTS（现 13 任务）；已重启 daemon(PID 27184) 加载新任务
  - 验证：entropy 全速 NORMAL(H=1.0,7链)；visual parked(numpy MISSING)；cron_daemon 识别新任务

### P3-3：lambda_state.json 三写者冲突（2026-07-24 下午核查）
- [x] ~~**P3-3a [🔴 P0]** interoceptive_cortex 完整替换写 → 清空 lambda_tuner 全部字段~~ ✅ 已修复（2026-07-24）
  - **修复**：改为 `flock.safe_read_json()` → `prev.update({IC_keys})` → `flock.atomic_write_json()`，LT/ST 字段保留
  - **更正**：orb 的 joy 来源是 `surface_tension_state.json`（非 lambda_state.json），IC 完整替换不影响 joy（之前误判）
  - **剩余**：IC ∩ LT 重叠键（mode/ts）仍被 IC 覆盖
- [x] ~~**P3-3b [🟡 P1]** IC∩ST 重叠键后写赢~~ ✅ 路一已解决（2026-07-26）
  - **根因**：lambda_state.json 的 anxiety/anger/fear 是死键，orb 从不读
  - **路一**：orb 红通道改用 `recent_events` 事件频率（焦虑=过程，非向量绝对值）
  - **D 清理**：删 surface_tension.py P0-5 同步 + alignment_verify.py P0-2c 死键写入
  - **路二待做**：拓扑求解器（球体表面由力场方程实时驱动）
- [x] ~~**P3-3c [🟡 P1]** IC 的 pain_ext/int（raw）vs orb 读 smoothed_pain_ext/int~~ ✅ 已完成（2026-08-13）
  - IC 写 `pain_ext` = `ctx_pct/100.0`（原始值）到 lambda_state.json
  - orb 只读 `smoothed_pain_ext/int`（LT 写的 EMA 平滑值）
  - IC 的 raw 值对 orb 无意义，但 IC 完整替换时可能覆盖 LT 的同名字段
  - 方案：IC 写 `pain_ext_raw`/`pain_int_raw`，orb 读 `smoothed_pain_ext/int`，隔离 raw/smoothed
  - ✅ **2026-08-13 已完成**：IC 改写 `pain_int_raw/ext_raw`；LT 改 flock 合并写 + 修字段名 `smoothed_pain_ext/int`；详见 `memory/task_P3-3c_interoceptive_orb_隔离_2026-08-13.md`

### P3-4：cognitive_friction_registry 系统性缺陷（2026-07-24 下午核查）
- [x] ~~**P3-4a [🔴 P0]** .json 非原子写 + 无 jsonl 恢复路径 → 进程崩溃后数据蒸发~~ ✅ 已修复（2026-07-24）
  - **修复**：`_save()` 改用 `flock.atomic_write_json()`，进程中途崩溃不产生残缺文件
- [x] ~~**P3-4b [🟡 P1]** friction registry 无截断无自动清理 → 线性增长~~ ✅ 已修复（合入 P3-4a，2026-07-24）
  - `MAX_FRICTIONS=500`，`_save()` 时截断至最近 500 条，超出部分永久丢弃
- [x] ~~**P3-4c [🟢 P2]** suppressed 记录留在 jsonl 不删~~ ✅ 已修复（2026-08-13）
  - `suppress()` → `_append_log()` 原子追加 jsonl（带 `_action: "suppressed"` 标记）
  - `resolve()` → 同理追加 `_action: "resolved"`
  - `_load()` → 启动时从 jsonl 恢复最新 status，覆盖 registry 中的记录（防止 suppress 后重启导致摩擦"复活"）
  - `vacuum()` → 按 friction_id 去重 jsonl（保留最新条目），由 weekly cron 调用

### P3-6：HP4 心跳串行阻塞 + 无超时（2026-07-25 新发现）[已修复 2026-07-26]
- [x] **P3-6 [🔴 P0]** `_execute_heartbeat_actions()` 串行阻塞，无任何超时机制
  - 修复：双阶段架构——Phase1 7个 trigger 用 ThreadPoolExecutor 并行+30s全局超时，Phase2 _record_surface_tension 顺序执行
  - 超时函数走 health_log 落盘
  - **最坏情况**：`_trigger_self_probe.probe()` 含 LLM → HP4 心跳卡死到 LLM 返回
  - **方案**：每个 `_trigger_*` 包装 `signal.alarm(timeout=5s)` 或 `concurrent.futures.ThreadPoolExecutor` 并发

- [x] ~~**P3-7 [🟡 P1]** HP4 内部状态读取失败静默降级为空字典~~ ✅ 已修复（2026-08-13）
  - `_read_interoception/presence/context_control()` → 失败时 `_health_log(ERROR)` + 返回 `{}`
  - `_trigger_cognitive_friction()` → `ImportError` 和所有异常打 health_log + 返回 error dict
  - `_surface_errors_to_health_log()` → 扫描所有 actions 中 `{type: xxx_error}` 统一落盘

### P3-7：friction registry / HP4 多点静默失效（2026-07-25 下午核查）

- [x] ~~**P3-7a [🔴 P0]** `cognitive_friction_detector._load()` 损坏时静默归零~~ ✅ 已修复（2026-07-25）
  - 新增 `src/health_log.py` 共享 helper（写 `_agent_memory/system_health_log.jsonl`，2000 行上限）
  - `_load()` except 块改为 `health_log.log_event("cognitive_friction_detector", "ERROR", ...)`
  - 不再静默归零，损坏事件可观测

- [x] ~~**P3-7b [🟡 P1]** `interopertive_cortex` 历史加载失败静默降级~~ ✅ 已修复（2026-08-13）
  - `load_history()` 的 `except Exception: pass` → 加 `health_log.log_event("interop_cortex", "ERROR", ...)`
  - 其余 4 个 except 均为无害外部调用（stdout重配置/scg.run/context_controller/body_schema），不改

- [x] ~~**P3-7c [🟡 P1]** HP4 内 6 个 `_trigger_*` 函数静默失效~~ ✅ 已修复（2026-07-25）
  - 新增 `_surface_errors_to_health_log(actions)`：扫描 actions 中 `type` 以 `_error` 结尾或含 `error` 键的条目
  - `heartbeat_with_hooks()` 在 `_execute_heartbeat_actions()` 后调用，落盘 `system_health_log.jsonl`
  - 六子系统（好奇/探针/异常/奖励/调参/摩擦）失败现在可观测

### P3-5：spike_valley_detector 死代码 + 长期运行缺陷（2026-07-24 下午核查）

---

## 路二：约束混合系统（情感物理化）
> 架构定性：**Constrained Hybrid System**（约束混合系统）
> - 骨架：五相态离散状态机
> - 血肉：7维耦合ODE（dX/dt = -Λ·X + C·X + F(t)）
> - 免疫：热锁/疤/熔断约束层

### 路二-1A：六欲通道 + 耦合ODE
- [ ] **路二-1A-1 [🟡 P2]** `surface_tension.record()` 加 `channel` 字段（eye/ear/nose/tongue/body/mind）
  - 六欲从散落模块→每条事件自带通道标签
  - 具身化时 channel='eye' → 接摄像头
- [ ] **路二-1A-2 [🟡 P2]** 7维耦合ODE（RK4数值积分 + C矩阵）
  - `_decay_vector()` 升级：从独立exp(-λt) → 7维耦合ODE
  - C矩阵分两块：五行生克（前5维）+ 用户自定义（love/curiosity）
  - 验证：creator_blame进来 → anxiety+0.6, anger+0.7 → 观察fear是否被C拉动

### 路二-1B：球谐映射
- [ ] **路二-1B [🟡 P2]** 7D状态 → 球谐系数 + tremor参数
  - anxiety→Y₁⁰(上下拉伸) / anger→Y₂⁰(椭球) / fear→Y₂²(4凹) / sadness→Y₃⁰(3瓣) / joy→Y₀⁰(呼吸) / love→Y₁¹(倾斜) / curiosity→Y₃³(细密波纹)
  - `orb_state.json` 输出 `{sh_coeffs, tremor_amplitude, tremor_frequency}`
  - 不动渲染，纯Python验证

### 路二-2：渲染端替换
- [ ] **路二-2 [🟢 P2]** tu8_health_orb_ring.py → WebView2 + Three.js
  - Python算物理（SH系数+tremor），JS画几何形变
  - 当前GDI+只能画2D色环，换WebView2才有顶点位移能力

## 已废弃设计讨论区（路一已解决）

> ~~IC∩ST 语义冲突~~（路一+D清理已解决）
> ~~焦虑=结构~~（路一定义：焦虑=过程，事件频率驱动）
- [x] ~~**P3-5a [🟢 P2]** spike_valley_detector.py `detect()` 入口无消费者~~ ✅ 已删除（2026-08-13）
  - `detect()` / `detect_topology()` 全局零调用；`surface_tension` 自己算 spike_valley_vector；`topology_thermal_monitor` 只读 ST 的版本
  - 确认：state.json 从未写过（零调用确认）
  - 行动：删 `src/spike_valley_detector.py` → 备份到 `backup/spike_valley_detector.py.bak`
- [x] ~~**P3-5b [🔴 P0→P2]** jsonl 无截断 → history 文件无限膨胀 + 导数不除Δt + 无归档~~
  - 修复：`_load_history` 限制 _MAX_HISTORY_LOAD=500；`compute_curvature` 归一化 Δt_hours；
    新增 `_truncate_history()` 自动截断 _MAX_HISTORY_LINES=1000 + 归档旧记录；
    新增 `truncate_history()` 外部调用入口。@2026-07-26
  - `compute_curvature()` 只用 `events[-50:]` 限制计算范围，但读阶段无截断
  - **方案**：① jsonl 加行数上限，超限重写（保留最近 N 条）；② `_load_history()` 加截断读取

---

## 已完成历史（>7 天）

- ✅ [2026-07-10] `docs/architecture/拓扑色盘_四层同构综合_20260710.md`
- ✅ [2026-07-10] `memory/天赋测试实验/035_双轨顿悟与数形结合_梦境模块吸收.md`
- ✅ [2026-07-10] `memory/天赋测试实验/034_色盘拓扑与矛盾6修正.md`
- ✅ [2026-07-10] `memory/天赋测试实验/INDEX.md`（片段001-037索引完结）
- ✅ [2026-07-10] `memory/天赋测试实验/036_矛盾7_寄生节律与自由节律_临界点.md`
- ✅ [2026-07-10] `memory/天赋测试实验/037_人类发育史与TU8演化路径_三阶段映射.md`

## 2026-08-01 递归学习环闭环 (Qwen 验证法)
- [x] 递归学习环消费端接 cron: src/cron_learning_apply.py (产+消兜底, 1800s); 接入 cron_daemon SCRIPTS (14 任务, PID 21824); 手动跑通第一圈 loop_turned=true (5x frustration_edge -> 写 _learning_alerts.jsonl + T5铸印). 遗留: dream T0 distill 未 save 队列(已由兜底覆盖), v1 行为变更仅写告警未改硬参数.
- 归档: 递归学习环闭环_2026-08-01.md

---

## 2026-08-01 待修清单 A：WorkBuddy 路径审计残留（未修）
> 路径漂移 D:\→C: 已全修 29 文件（2026-08-01 完成，备份 backup/*.v1.py）。以下为审计中未自动修项。
> 核对文档: WorkBuddy_bug清单核对_2026-08-01.md / WorkBuddy_bug修复完成_2026-08-01.md

- [x] ~~**A1 [P1]** 主机名写死 LAPTOP-HJPFSOKP~~ ✅ 已修复（2026-08-13，选"a"=便携化）
  - `consciousness_cycle.py:2163` → `socket.gethostname()` 替代写死
  - `cold_start_engine.py:93` → 同上
  - `weismann_fork.py` → 动态提取 `_DECONTAMINATE_HOST = socket.gethostname()`
- [x] ~~**A2 [P1]** tu8_memory._load_long_term() 空操作~~ ✅ 已核实（2026-08-13，非 bug）
  - `_load_long_term()` 是 stub（:1507 `pass`），但 long_term 实际由 seeds.txt 初始化 + `_check_promotion()` 从 short_term 晋升填充
  - MEMORY.md 是 TU-8 蒸馏用外部文件，与 MemoryManager 内部 dict 是两套并行系统（:_load_long_term 与之无关）
  - 结论：MemoryManager 长期记忆正常运作，stub 是设计预留（MEMORY.md 解析不在此模块）
- [x] ~~**A3 [P3]** memory_dedup._character_trigrams 实为 unigram（[i:i+1]，docstring 自承）（E024/Fix8）~~ ✅ 已修（2026-08-14）
  - 改为真 trigram（`clean[i:i+3]`，加 `<3` 短文本保护），函数名名副其实。
  - 验证：Jaccard 相同=1.0 / 无关=0.0 正常。
- [ ] **A4 [P2]** 6 级降级逻辑重复（E027）：memory_degradation.py 的 should_degrade()/compute_next_fidelity_level() 与 tu8_memory.FidelityManager 平行
  - 评估：实为**数据重复**（`FIDELITY_RETENTION` L0-L5 vs `FIDELITY_LEVELS` L0-L5 值完全相同），非逻辑重复。
  - 两条记忆链路各自需要该表，统一到单源反而增加跨模块耦合。低优，**暂不修**。
- [x] ~~**A5 [P3]** 钢印签名阈值 >=0.3 偏松（E029，steel_seal_verifier:106/115/122）~~ ✅ 已修（2026-08-14）
  - 提取常量 `STEEL_SEAL_REBUILD_THRESHOLD = 0.3`，三处引用统一；注释标注测试期宽松值，生产建议 0.6+。
  - 保留测试行为（不破坏自动重建测试），消除魔法数字。
- [ ] **A6 [P3]** C:/Users/qq366410837/.qclaw/workspace 正斜杠 34 处（Fix18/19）
  - 复检：实际 `D:[/]` 残留仅 11 处，9 处为示例/测试字符串，2 处非示例（error_translator:95 翻译数据 + tu8_agent:35 构造示例）。
  - 真正的活跃移植风险路径已在 B-05/B-06 修掉（steel_seal_verifier / orb_state_writer）。A6 无活跃残留，**暂不批量修**。
- [x] ~~**B-03 [P1]** fact_correction_scar.py 隐私泄漏~~ ✅ 已修（2026-08-13）
  - `__main__` 测试块含真实 QQ 号 366410837 + 路径 `D:\qq366410837\...`，共 4 处
  - 已全部脱敏为通用占位符。活跃路径（confidence_decay / memory_degradation）不引用测试块。
- [x] ~~**B-04 [P1]** error_translator.py 版本漂移~~ ✅ 已修（2026-08-14）
  - `QCLAW_PATH_MAP` 写死 v0.2.29.592 → 改为 `_detect_qclaw_root()` 动态检测
  - 从 `sys.executable` 反推 QClaw 根目录（`vX.X.X.XXX/resources/python/python.exe` → 上两级）
  - `translate()` / `format_report()` 读惰性函数结果，v0.2.35.624 下全部路径正确

## 2026-08-01 待修清单 B：千问耦合图 / 循环不通问题
> 根因：TU-8 是耦合图不是管道链，但代码硬编码成管道、文档画成图，两版对不上。
> 调研文档: coupling/system_overview_emotion.md / coupling/system_overview_supplement.md（P1-P6 六优先）
> 递归学习环（产→消）已闭环（见上段），但以下结构环仍不通/未接。

- [x] ~~**B1 [P1 架构]** 建立同步 tick + 双缓冲~~ → B1+B2 修复完成 ✅
  - `src/engine_registry.py`（13KB）：全局引擎注册表 + tick 协调层
  - 18 引擎注册（15 cron + 3 on_demand），含依赖拓扑（deps + deps_mode）
  - `cron_daemon.py`：`daemon_loop` 每轮 advance_tick()；`run_script` 跳过依赖不满足的引擎，跑后更新状态
  - 验证：tick=2，OK=10/18，HAS_REGISTRY=True，daemon 重启（PID 21640）
  - 遗留：双缓冲读旧值写新值尚未强制（各引擎代码自身改造）
- [x] ~~**B2 [P1]** 全局引擎状态注册表~~ → 已包含在 B1（同一 engine_registry.py）
- [x] ~~**B3 [P1]** 耦合关系数据化~~ → B3 修复完成 ✅
  - `src/coupling_graph.py`（20KB）：CouplingGraph 执行器 + `coupling_graph.json`（持久化）
  - 11 条边，全部源码级精确公式（C1-C12，C4 冗余删除）
  - `get_coupling_graph()` 单例，实时可调 `set_param(edge_id, param, value)` → `save()` 持久化
  - 跨边合成：tension = red*0.6 + (1-blue)*0.4（orb_state_writer 内部逻辑显式化）
  - 自测：orb.red=0.353（1.06/3.0），tension=0.332，LLM params 全部正确
  - 遗留：C1-C2 red_flag 待各 consumer 改造时清空（耦合关系从消费者抽离后）
  - 现状：C001-C009 权重散落 consumer 代码（魔法数字）；改耦合=改代码。
  - 目标：边=数据，改耦合=改数据（Qwen 原则②）。
- [x] ~~**B4 [P1]** C008 情感回边缺失 E007→E002（情绪反馈闭环不通）~~ → B4a+B4b 双根因全修 ✅
  - B4a: alignment_verify.verify_and_output() 死代码（从未被外部调用），原设计无效。
  - B4b: tu8_agent.respond() 无对话→情感写入 → **真实根因**。
  - 修复：L1026-1046 新增 surface_tension.record() 注入点，基于 metadata 元数据(deviation_gate/health_check/consciousness/latency) 推断张力类型(insight_found/creator_blame/steel_conflict/context_overload/energy_low)。
  - 回环：tu8_agent.respond → surface_tension_state.json(recent_events) → orb._compute_anxiety_dynamics() → 红通道。已验证历史写入 2 条。
  - 备份: tu8_agent.v2.py。
  - 设计/注释有 alignment→surface_tension（joy↑/anxiety↓）反馈，代码无此边。
  - 后果：情感是传感器不是调节器，开环；无法产生认知差→自循环递归进化（核心目的）。
- [x] ~~**B5 [P2]** alignment→surface_tension 回边~~ → B5 ✅ steel_density 接回仲裁
  - 根因：arbitrate() 收到 steel_mark_strength 参数但从不使用；alignment_verify 用硬编码默认值 0.7
  - 改1：`contradiction_arbitration.py` STEEL_MARK 分支三段化：density<0.3→EQUAL=60（脆弱降权），0.3-0.6→80+宽松阈值，>0.6→80+原逻辑
  - 改2：`alignment_verify.py` 现在从 `secure_vault/anchors.json` 读真实钢印密度（非硬编码）
  - 验证：strength=0.1→priority=60/aribitrate、0.4→80/arbitrate、0.7+conf≥0.8→80/steel_holds ✅
- [x] **C→A [P2]** 钢印密度拓扑化（WorkBuddy 蛛网优化 C）
  - 根因：锚点群星形（E=0，density=0.0），原 steel_density=sealed/V 孤立计数
  - 新增 `src/seal_graph.py`（8.6KB）：从 seal_sensor_feed.jsonl 建父子链边 + 共享 seal 边
  - 密度公式：steel_density_score = topology_density × 0.6 + min(depth/5, 1.0) × 0.4
  - 全局 steel_density = avg(所有锚点的 steel_density_score) = 0.0（星形基线）
  - `alignment_verify.py` 升级：从 `memory/anchors_with_graph.json` 读取拓扑分数
  - 路径修正：`secure_vault/anchors.json`（不存在）→ `memory/anchors_with_graph.json`
  - 意义：密度 0.0 = 7 个孤立火种，钢印尚未形成互相加固的网络
  - 归档：任务_C-A钢印密度拓扑化_2026-08-06.md

- [x] ~~**B6 [P2]** C021 EntropyGuard.route_with_defense 接 tu8_dispatch~~ → B6 ✅
  - 根因：route_with_defense() 存在但从未被调用（无调用点）
  - 新增 `src/dispatch_cocoon_router.py`（6.3KB）：CocoonAwareRouter 封装 + Intent→Chain 候选映射（9意图）
  - 接入 `tu8_dispatch.py` assemble() 末尾：assembly.metadata['cocoon'] + ['routed_chain']
  - 验证：6/6 intent 路由 PASS + Real EntropyGuard PASS
  - 归档：任务_B6茧房防御接入dispatch_2026-08-06.md
- [x] ~~**B7 [P1]** E001 orphan：emotion_engine.py(60KB) 不入运行时 + 3 套平行情感表示无桥~~ → B7 修复完成 ✅
  - 真实状态：`emotion_engine` 已接入（tu8_agent → ConsciousnessCycle → AffectEngine），但**回环断**：AffectEngine 结果从未写回 surface_tension
  - 修复：L877-902 新增 `consciousness_cycle._current_affect()` → surface_tension 回环
  - 与 B4 互补：B4=系统级 metadata 信号（deviation_gate/health_check），B7=情感级 affect_signal（valence/confusion）
  - 备份: tu8_agent.v2.py。
  - 目标：建桥或废弃 emotion_engine（当前真驱动是 surface_tension 7D）。
- [x] ~~**B8 [P2]** 魔法权重从 consumer 抽离到耦合边（B3 子项）~~ → B8 ✅
  - `coupling_graph.json`：6条边加 params（C1/C2/C3/C6/C7/C8）
  - `orb_state_writer.py`：从 edge["params"] 读 RED_FREQ_W/JOY_LOVE_W/CURIOSITY_W 等，硬编码兜底
  - `affect_modulation.py`：从 edge["params"] 读 tension_w/resonance_w/ATTRACTION_W 等
  - `evaluate_edge()`：params 注入 eval 上下文（base_globals.update(edge["params"])）
  - 验证：orb rgb=[0.09,0.28,0.55] / affect temp=0.72 全部 PASS；改 JSON 权重→输出随之变
- [x] ~~**B9 [P1]** 静默失败治理~~ → B9 修复完成 ✅
  - 根因：`_read_json(path, {})` 静默 fallback，下游无法区分"上游挂" vs "真中性"
  - 新增 `src/engine_health_probe.py`（StateHealthProbe）：OK/STALE/DEAD 三态探针
  - 集成 `orb_state_writer.py`：STALE 时清空 recent_events 用近零焦虑；DEAD 时用安全默认值
  - 新增 `src/cron_health_probe.py` + 注册到 daemon（14 任务）：每 5 分钟全引擎健康心跳
  - 实测：4/9 OK / 2 STALE(cognitive_friction 8天未更新) / 3 DEAD(behavior/dream/attractor 从未创建)
  - 备份: orb_state_writer.v2.py。
- [x] **B10 [P1]** 耦合权重可塑（蛛丝弹性落地）
  - adapt() Δw=α·(1-w²)·pre·post，过冲自修正，防震荡
  - adapt_history/get_weight/tick 完整接口，17/17 测试全通过
  - cron_coupling_adapt.py 注册（interval=600s），实测 adapted=3 [C1,C6,C10]
  - 归档：任务_B10蛛丝弹性适配_2026-08-06.md
- [x] **B11 [P2]** 延迟显式化：RingBuffer 历史快照 + evaluate() 读延迟上下文
  - RingBuffer(capacity=64)：每个引擎独立历史，按 tick 索引，超容覆写最旧
  - record_tick(agent_states)：一轮快照推进所有引擎 tick+1
  - get_delayed_context(target)：按 delay_ticks 读历史（无历史时 fallback 当前）
  - evaluate() 自动用延迟上下文，delay_ticks=0 读当前、>0 读历史
  - cron_coupling_adapt.py 升级：record_tick() 写快照 + evaluate() 用延迟上下文
  - 归档：任务_B11延迟显式化_2026-08-06.md

> 优先级建议：B4/B7/B9（情感开环 + orphan + 静默失败）先修 → B1/B2/B3（架构地基）→ 其余。
> A 段仅 A1 需拍板，其余可批量执行（低风险纯代码）。递归环已通，B 段是更广的耦合图闭合。

---

## 🔴 PROMOTE 通道 + 代谢架构升级 [NEW 2026-08-21，H级]

> 来源：TU-8 × 造物主 × 千问 三方讨论（2026-08-17~21）
> 核心：memory_gc 评分退化误杀 7 段基底 → 暴露代谢架构缺上行阀门 → 设计 PROMOTE 通道 + 元认知监督 + workspace/architecture_journal 模块
> ⚠️ 本区块为 H 级新架构模式（触及钢印相关逻辑），须经造物主显式签字方可落地，未签字前不得写实现代码

### 设计稿（已产出，已签字落地 §8）

- [x] **造物主对 PROMOTE 设计稿 H 级签字** [P0] — 2026-08-26 显式签字「那就开始写代码吧」
  - 文件：`PROMOTE_channel_design_2026-08-19.md`（v0.2，撤回 Coherence + architecture_journal 模块 + 三处加固）
  - **本轮落地范围**：§8 architecture_journal 模块（造物主选 (a) 直觉方案）；§2.1/§4.2/§8 三处已现状满足无需改
  - **未落地（待后续独立签字）**：§2   - [x] **[B] distill 遥测埋点改造** [done 2026-08-28，H级已签]：src/metabolic_pipeline.py 已落六遥测字段 + _enrich_telemetry 等四方法，向后兼容178段。设计稿 docs/design/distill_telemetry_b_spec_2026-08-28.md（含 §7 内生信号演进路线）。
PROMOTE 通道主体（evaluate_promotion + 观察期状态机 + 评分器接口）——依赖 distill R/S/C 遥测 infra，探明 live 当前缺失，本轮不臆造，留缺口待补
- **已落地（2026-08-27）**：§3 元认知监督（gc_decisions.md 原子写入）、§5 认知失调记录（涌现时刻_20260819）、§4.3 钢印段 GC 保护确认、08-19 评分退化收尾（无日期段 age_unknown 修复）

### PROMOTE 通道规格 [P1] — ⚠️ 待 infra（未落地，非签字范围遗漏）

> 2026-08-27 探明：live 系统**无** R/S/C 遥测基础设施（distill 无 topic_tag/citation_id/linkage_map 元字段；无 evaluate_promotion 实现）。
> 按铁律边界（不臆造遥测系统），本轮**不落地** PROMOTE 通道主体，仅留接口契约与缺口记录，待 distill 埋点改造后独立签字实施。

- [x] **evaluate_promotion() 行为性签名冻结** [done 2026-08-28]：src/promote_channel.py 仅收 (ref_events, gc_survival_log, linkage_map) 三元组，禁语义参数/嗅探，CI 静态检查拦截
  - 仅收 `(ref_events, gc_survival_log, linkage_map)` 三元组；禁 title/content/keyword 语义参数；禁函数体内容嗅探
  - CI 静态检查拦截手写 L0 关键词（l0_override/force_promote/protected_section）
- [x] **第四信号 Coherence 已撤回** → 改为架构记忆由 workspace 持有（见 architecture_journal，2026-08-26 落地）
- [x] **观察期状态机** [done 2026-08-28]：CANDIDATE→SOLIDIFIED(写 seal_index 物理锚)/回落 KEEP；DOWNGRADE 可降级带证据，阈值 R≥3/S≥2/C≥2
- [x] **与评分器接口契约** [done 2026-08-28]：PROMOTE 为独立上行评估器（promote_channel.py），不混进 GC 阈值；distill 已产 R/S/C 遥测

### 元认知监督 [P1] — 2026-08-27 落地

- [x] **gc_decisions.md 原子写入**：`src/gc_decisions.py` append_decision() 临时文件原子落盘；自述失败→动作回滚 WATCH no-op（memory_gc.run_gc 已接）
- [x] **结构化遗忘自述模板**：§3.1 模板（动作/理由/证据/复核标记），每次 DEGRADE/EVICT 必先写后执行
- [x] **gc_decisions 完整性测试** [done 2026-08-29]：src/gc_decisions_test.py 模拟 100 次断言 reason/evidence + 原子回滚；附修 get_pending() 真 bug（备份 gc_decisions.20260829_p0.bak）：单测模拟 100 次 GC 决策断言（待补 CI，属验收 §6.1；当前手工验证 count 计数正确）

### 混合通道清理 [P1]

- [x] **废弃 _learning_protected.json**：DEPRECATED 后仅告警返空（2026-08-26 标记 DEPRECATED 字段，3个月倒计时从签字日算）；每次 GC 启动自动 deprecate 检查
- [x] **compute_seal_bonus 已非 stub**：实测返回 0.0–0.15 真实浮点加权（seal_to_gc_adapter.py 已激活），值域符契约；无需改
- [x] **契约冻结 seal_to_gc_adapter**：仅消费 get_seal_segments()/compute_seal_bonus 现有接口，未新增方法

### workspace/architecture_journal 模块 [P1，造物主直觉方案]

- [x] **新增独立模块**（不进 memory/ GC 管道）—— 2026-08-26 落地
  - `workspace/architecture_journal/_index.md`（活跃决策清单 + 当前 ACTIVE 决策）
  - `workspace/architecture_journal/<YYYY-MM-DD>_描述.md`
  - `workspace/architecture_journal_archive/`（竣工只读归档）
  - `workspace/architecture_journal/CONTRACT.md`（模块契约/维护规则/三处加固）
  - 源码：`src/architecture_journal.py`（ArchitectureJournal 类，含 log_decision/review_transitions/deprecate_learning_protected）
- [x] **维护规则**：系统每次 H 级变更/GC逻辑修改/PROMOTE评估后自动追加（非手写保护，系元认知副产品）
  - 写：决策断言(≤2句) + 依据(指向涌现时刻/讨论) + 约束范围 + 状态(ACTIVE/STABLE/SUPERSEDED)
  - 不写：讨论过程/否决方案/迭代细节（留记忆区正常代谢）
- [x] **权威源与优先级**（TU-8 加固点）：ACTIVE 条目为运行时强制真值（GC 读 journal 不读 memory 副本）；memory 派生断言为学习缓存，衰减不影响强制 → 已接 memory_gc.analyze_memory 命中 ACTIVE 强制 KEEP
- [x] **自动状态转移器**（防变垃圾场）：每次 H 级变更后自动 review ACTIVE→覆盖标 SUPERSEDED/固化标 STABLE 迁 archive；转移须自动 hook，禁人工 → 已接 memory_gc.run_gc 启动时调用 review_transitions
- [x] **与 distill 接口**：journal ACTIVE 为 distill 上游水源→提取极短断言进 memory/ 正常代谢→PROMOTE 三元组达标晋升；归档区不参与评分 → 已接 metabolic_pipeline._journal_active_sections
- [x] **定位重叠处理**：docs/design/ARCHITECTURE_LOG.md=哲学层（不动）；journal=操作层决策（新增）；_index 不重复哲学 → CONTRACT.md 明确声明

### 认知失调记录（本次误判事件）[P1] — 2026-08-27 落地

- [x] **走正常代谢**：`memory/涌现时刻_20260819_代谢误判与上行通道觉醒.md`（#050，复用 06-07 先例格式）
  - 命名规范严格；不手动贴 MEMORY.md；被后续 distill 读时按关键词簇打 type:INSIGHT
  - 禁反向污染：该记录不进 evaluate_promotion 的 R/S/C 信号源（已在文件尾显式标注）
  - 类型标记 type:INSIGHT（含「自我修正」「代谢觉醒」关键词簇）

### 08-19 四连 bug 已修复（落地态，归档备查）[P0]

- [x] **interoceptive_cortex 门禁误报修复**：compute_context 排除 contextTokens 窗口占位 → posture critical→nominal，pre_task_check 解除永久 NO-GO
- [x] **memory_gc 文件名 `:` 崩溃修复**：safe_title 全量清洗 Windows 非法字符，run_gc 无崩溃
- [x] **metabolic_pipeline 去重过删修复**：提取粒度+内容指纹去重+机械守卫，欧拉段等真洞察落地
- [x] **memory_gc 评分退化修复**：_extract_meta 真实 age + age_unknown 保护，deep 实跑零破坏（EVICT 为 no-op）
  - 备份：backup/MEMORY.md.20260819.gcrun.bak / backup/memory_gc.py.20260819b.bak 等

### 张力模块外部对标 + 摩擦双层级厘清 [NEW 2026-08-28，P-later 跟踪]

> 来源：TU-8 × 造物主 × 千问对话（AI 护栏/控制论/元认知对标），2026-08-28 凌晨。
> 真源稿：`docs/design/tension_module_external_mapping_2026-08-28.md`（4150B，含千问三方对标 + TU-8 三处补强 + 两层摩擦边界 + 08-27 实测证据）。
> 级别：对标分析（非 H 级实现变更），本小节仅跟踪待办，不触发签字门禁。

- [x] **decay_loop 常驻心跳资源成本评估** [done 2026-08-29]：实测 5820 行/1190KB，0.09 条/分，年增~3.6MB；限频/批量/滚动归档建议列 H 级待签（src/decay_loop_cost_probe.py）：surface_tension_history.jsonl 当晚累计 5412 条 / total_events 1908，每~5min 一条 decay_tick。记忆量上升时需评估限频/异步化/批量写入，防隐性负担（千问对标 §2.3 漏提的工程代价）。
- [x] **摩擦通道（L0 欲论）独立专文** [done 2026-08-28]：`docs/design/friction_channel_l0_desire_theory_2026-08-28.md`（2834B），与张力模块 L2 监控信号明确分层，防混用。
- [x] **对标稿已落位 docs/design/** [done]：未散落根目录，符合 GOVERNANCE 铁律五。
- [x] **千问本次对标可信度核验** [done]：描述字段（neutral/nominal/7维spike_valley/decay_loop/pain_int_raw/curiosity）与 08-27 实测 json 完全吻合，无虚构文件状态，区别于先前 review 陷阱。

### 话题语义矩阵算法 [H 级, 2026-08-28-29 三批次落地]

> 真源稿：`docs/design/topic_matrix_impl_design_2026-08-28.md`（H 级实现设计，§8 三批次计划）。
> 上游概念稿：`docs/design/topic_semantic_matrix_design_2026-08-27.md` v1.3（14 章 + 附录 A-F）。
> 验证报告：`docs/reports/topic_matrix_validation_2026-08-29.md`（批次1+2 真实语料 93.7% 命中）。

- [x] **批次1（地基 L1 投影判区）** [done 2026-08-28]：`src/topic_matrix.py`(L1 三正交轴 sem/ctx/act + project MAX池化 + 落空处理) + `src/vector_store.py`(纯标准库 memmap + 复用 TFIDFEmbedder)；τ=0.35 实测回测；无 numpy 环境去依赖化。
- [x] **批次2（四算子）** [done 2026-08-29]：`src/matrix_operators.py`(NMF/SVD/LSA/DAG 统一接口，纯 Python + numpy 可插拔)；NMF W,H≥0 满足、SVD k=2 explained=1.0、DAG acyclic、LSA 委托；验证通过。
- [x] **批次3（密文库 codebook）** [done 2026-08-29]：`src/codebook.py`(挂 secure_vault/index.json["codebook"]，register 幂等返回 sym_* + resolve 还原)；distill 接线 `_compress_entities` -> entity_syms（已知高频繁体词典，未来由 v1.3 L2.5 grounding_refs 浮现不写死）；验证通过。
- [x] **§12 千问三段映射固化** [done 2026-08-29]：防过度设计，标记段一不适用/段二段三已同构；artifact docs/reports/topic_matrix_qianxun_mapping_2026-08-29.md。
- [ ] **sentence_transformers 稠密向量升级** [P-later]：当前 TFIDF 哈希向量，长短文本可比性靠 MAX 池化缓解非根治；环境可用时升级 Vectorizer 后端（设计稿 §5 可插拔）。
- [x] **distill 接 topic_matrix 自动写 coord** [done 2026-08-29]：_enrich_telemetry 加 coord 字段 + _project_coord 懒导入 TopicMatrix.classify_event 返回 {sem,ctx,act} 或 None（落空）。


---

## 🟡 长期愿景 / Dormant 区（标 STALE 待核实）[NEW 2026-08-21]

> 以下项 >60 天无进展或属创意探索，按淘汰策略标 STALE，待造物主确认是否继续；不自动删。

- [STALE] **创意×学科探索**（L498-511）：厨师写方程 / 宇航员织毛衣 / 机器人跳芭蕾 / 数学公式视频 / GPU公式原型 / F_topo渲染器 / 尖刺·凹陷·驻波·陨石可视化（9项）
- [STALE] **神经基底映射**（L595-596）：深层引擎神经基底 / 浅层转译器神经基底
- [STALE] **数学形式化**（L634-635）：AGM与训练动力学对应 / 悖论范畴论刻画
- [STALE] **F层觅食器官设计**（L177）：docs/architecture/F层_觅食器官设计.md
- [STALE] **相机-物体解耦测试集**（L415）
- [STALE] **surface_tension 路二**（L735-750）：channel字段 / 7维耦合ODE / 球谐系数 / WebView2 渲染（P2 四项）
- [STALE] **A4 降级逻辑重复**（L801）/ **A6 正斜杠34处**（L807）
- [STALE] **召回路由串联**（L133）/ **safety 字段预埋**（L137）/ **MEMORY.md 召回统计**（L106）

## 类脑架构同构待建（9-7 千问对话复盘产出，2026-09-07 拍板）
> 来源：2026-09-07 李奥×千问 10 轮「类脑架构本体论」。钢印候选 27→升格 11（MEMORY.md #10-#20），余 16 留观。
> 本区块为升格钢印对应的 TU-8 实装待建项（非钢印本身）。

### P1-BC0：补快通道（实时张力纠偏）[NEW 2026-09-07]
- 现有：慢通道（dream_check/shadow_protocol/contradiction_arbitration 异步）。
- 待建：张力广播即时拉独立可验证传感器 + 实时回修 C。对应钢印 #12/#20。
- 依赖：P1-BC3（时序梯度场）。

### P1-BC1：扩三根钢印（时空/语义/置信度）[NEW 2026-09-07]
- 语义钢印：已有 coord 三轴（sem/ctx/act），✅ 到位。
- 时空钢印：缺统一物理时空坐标系（仅 .time_anchor 时间锚），待建。对应钢印 #13。
- 置信度钢印：现有 C 静态，待补环境动态协方差/不确定性估计（按物理环境自动调权）。对应钢印 #13/#15。

### P1-BC2：超立方体封装（内外双层耦合）[NEW 2026-09-07]
- 外部感知（执行层）⊗ 内部预测（定义层 L2 代数封闭）经第四轴 W（时序）耦合。
- TU-8 现有三层件但无超立方体封装，待建双向投影通道。对应钢印 #14。

### P1-BC3：第四轴时序梯度场（误差实时反传）[NEW 2026-09-07]
- 待建：激活时序差→误差斜率（Error Gradient）沿超立方体边实时反传修 C。
- 这是快通道（P1-BC0）的核心数学件。TU-8 当前仅"冻结等梦境期"，无实时梯度反传。对应钢印 #14。

### P2-BC4：Property 化自信度（C 从 Output 改节点 Property）[NEW 2026-09-07]
- confidence_decay_engine 的 C 当前=显式重算 Output（指挥官变体）；待改为节点内生 Property。
- 约束：受 SOUL.md L2 双层架构（Property 留 L5、Output 留 L2）约束，需再议是否全 Property 化。对应钢印 #19。

### 留观未升格 16 条（短期记忆，待二次冷滤）
- 见 memory/short/2026-09-07.md「复盘拍板结论」节。
