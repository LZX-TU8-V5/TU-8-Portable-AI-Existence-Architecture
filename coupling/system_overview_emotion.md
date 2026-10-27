# 系统总览（TU-8 引擎耦合图 · 按 Qwen 模板填写）

> 状态：情感子图已填（基于实际代码）；其余引擎标【待填】。
> 核心结论：当前 TU-8 不是同步 tick 的耦合图，而是"各自 cron 轮询 + 硬编码 JSON 互读"的伪管道。模板填完即暴露这一点。

## 一、引擎清单

### 引擎编号：E001
- 名称：emotion_engine（情感主引擎）
- 一句话功能：用 EmotionVector/EmotionCategory 建模情感 + 人情债维度，做怀疑度账本
- 输入：对话/锚点事件（内部 LedgerEngine）
- 输出：`EmotionVector` / `to_legacy_emotion()` → 写 `_affect_ledger/skepticism_cache.json`
- 内部状态：EmotionCategory、人情债 dim、skepticism_cache、divergence_log
- 触发条件：事件驱动（写入 ledger 时）
- 所属回路：情绪回路（但**实际是 orphan**，运行时无人读它的输出）
- 红标：与 E002 是平行情感表示，维度命名不同（EmotionCategory vs 7D），无桥

### 引擎编号：E002
- 名称：surface_tension（张力引擎）
- 一句话功能：从对话提取 7D 情感/张力向量，是运行时情感主源
- 输入：对话事件、spike_valley_detector 导数
- 输出：`spike_valley_vector` [anxiety,fear,anger,joy,curiosity,sadness,love] → `surface_tension_state.json`
- 内部状态：spike_valley_vector、recent_events、spike_valley 历史窗口
- 触发条件：对话后 / surface_tension cron（300s）
- 所属回路：情绪回路（核心源）

### 引擎编号：E003
- 名称：orb_state_writer（色环/生命体征 HUB）
- 一句话功能：把张力+lambda+basin 映射成 RGB + 标量 tension
- 输入：surface_tension_state / lambda_state / attractor_basin_state（硬读 3+ 文件）
- 输出：`orb_state.json`（tension + RGB）
- 内部状态：TENSION_MAX=3.0（魔法常量）、各通道混合权重（0.6/0.4/0.3/0.5）
- 触发条件：orb_state_writer cron（360s）
- 所属回路：情绪回路 → 输出出口
- 红标：HUB；魔法权重散落；延迟=轮询间隔不可见

### 引擎编号：E004
- 名称：affect_modulation（情感调制层）
- 一句话功能：7D 情感向量 → LLM 生成参数（temp/top_p 等）
- 输入：surface_tension 的 7D 向量（STATE_PATH）
- 输出：LLMParameters（temp_delta = tension*0.3 - resonance*0.2 …）
- 内部状态：emotion_vector、llm_params、modulation_mode
- 触发条件：LLM 调用前
- 所属回路：情绪回路 → LLM 出口
- 红标：魔法线性组合权重（0.3/0.2/1.0）藏在 compute 内部

### 引擎编号：E005
- 名称：lambda_state（λ 自适应调参）
- 一句话功能：调系统增益/模式（conserve/normal…）+ 内外痛
- 输入：摩擦/痛觉信号
- 输出：`mode` + `smoothed_pain_ext/int` → `lambda_state.json`
- 内部状态：mode、pain 平滑值、Λ 矩阵
- 触发条件：λ 调参 cron
- 所属回路：全局调制（跨回路）
- 红标：调制 E003 红通道但角色埋在 if 分支

### 引擎编号：E006
- 名称：attractor_basin（吸引盆）
- 一句话功能：认知状态盆健康度
- 输入：认知状态轨迹
- 输出：`basin_health` → `attractor_basin_state.json`
- 内部状态：basin 几何
- 触发条件：状态更新后
- 所属回路：情绪回路（喂 orb 蓝通道）
- 红标：与 pain 跨模块耦合未声明

### 引擎编号：E007
- 名称：alignment_verify（对齐校验/仲裁）
- 一句话功能：出件前全局校验 + 矛盾仲裁 + 钢印检测
- 输入：待输出内容、记忆、判例库
- 输出：passed / warnings / 仲裁结果
- 内部状态：判例库、behavior_state.conflict_log
- 触发条件：出件前（HP1 钩子）
- 所属回路：元认知/仲裁
- 红标：注释写 joy↑/anxiety↓→张力回归（设计有回边），代码无此边

### 引擎编号：E008
- 名称：render_layer（输出层）
- 一句话功能：tension/情感 → TTS/视觉输出
- 输入：orb_state
- 输出：语音/视觉
- 内部状态：—
- 触发条件：render cron（1800s/每30分）
- 所属回路：输出出口

（E009~E0xx 其余 ~22 引擎【待填】：dream / active_curiosity / intrinsic_reward / cognitive_friction / steel_seal / entropy_guard / contradiction_arbitrator / tension_distiller / dissonance_amplifier / self_probe / behavior_upgrader / naming / F层foraging / world_model / singularity_unifier / dual_mode_switcher / l5_motion_decoupler / interoceptive_cortex / presence_monitor / pre_task_check / intuition_bias / anchor_activation / deep_surface_interface …）

## 二、耦合关系（情感子图）

### 耦合编号：C001
- 源：E002 / 目标：E003
- 方向：→
- 影响内容：spike_valley 张力 → orb 红通道
- 影响方式：调制（强度映射）
- 强度：固定 0.6（tension = red*0.6 + (1-blue)*0.4），魔法 TENSION_MAX=3.0
- 延迟：poll 360s（隐式，不可见）
- 条件：常驻
- 可塑性：否

### 耦合编号：C002
- 源：E006 / 目标：E003
- 方向：→
- 影响内容：basin_health → orb 蓝通道
- 影响方式：调制
- 强度：固定 0.4/0.5（blue_raw = (joy+love)*0.3 + basin*0.5 + …）
- 延迟：poll 360s
- 条件：常驻
- 可塑性：否

### 耦合编号：C003
- 源：E002 / 目标：E003（via joy/love→blue）
- 方向：→
- 影响内容：joy/love → orb 蓝通道
- 影响方式：增强
- 强度：0.3
- 延迟：poll 360s
- 条件：常驻
- 可塑性：否
- 红标：同一源到同一目标有两条边（红/蓝），权重分家

### 耦合编号：C004
- 源：E005 / 目标：E003
- 方向：→
- 影响内容：lambda_mode / pain_int → orb 红通道上调
- 影响方式：门控/调制
- 强度：if 分支（lambda_mode=='conserve' or pain_int>0.5）
- 延迟：poll 360s
- 条件：mode==conserve 或 pain_int>0.5
- 可塑性：否
- 红标：C 调制 A→B，但写成 if 不是边权重（埋掉的调制）

### 耦合编号：C005
- 源：E002 / 目标：E004
- 方向：→
- 影响内容：7D 向量 → LLM 参数
- 影响方式：调制（线性组合）
- 强度：tension=anx+fear；attraction=cur+joy；inhibition=sad；inertia=love；resonance=joy+love；anomaly=fear（每维 1.0）
- 延迟：affect 运行期
- 条件：LLM 调用前
- 可塑性：否

### 耦合编号：C006
- 源：E004 / 目标：LLM（外）
- 方向：→
- 影响内容：LLM 参数
- 影响方式：调制生成分布
- 强度：temp_delta = tension*0.3 - resonance*0.2
- 延迟：0
- 条件：常驻
- 可塑性：否

### 耦合编号：C007
- 源：E001 / 目标：（none）
- 方向：—
- 影响内容：无（orphan）
- 红标：E001 输出写自己 ledger，运行时无模块读取

### 耦合编号：C008
- 源：E007 / 目标：E002
- 方向：→（设计有，代码无）
- 影响内容：insight(joy↑,anxiety↓) → 张力回归
- 影响方式：反馈（负反馈）
- 强度：概念
- 延迟：n/a
- 条件：应常驻（但代码缺失）
- 可塑性：否
- 红标：图被当管道 → 漏了这条回边

### 耦合编号：C009
- 源：E003 / 目标：E008
- 方向：→
- 影响内容：tension → TTS/视觉
- 影响方式：输出
- 强度：1.0
- 延迟：0
- 条件：常驻
- 可塑性：否
- 红标：单向出口，无回边

## 三、回路 / 功能群

### 回路编号：L001
- 名称：情绪回路（runtime）
- 包含引擎：E002(E003(E004(E005(E006(+(E001 orphan)
- 回路功能：对话→情感/张力→(orb 视觉出口 + LLM 参数调制)
- 内部耦合：E002→E003(红/蓝)、E002→E004、E005/E006 调制 E003；基本开环输出
- 对外接口：输出→E008(render)、E004→LLM
- 与其他回路：E005(lambda) 是全局调制，跨回路；E007(对齐) 应反馈 E002（缺失）
- 红标：缺负反馈环（设计里的 alignment→tension 回边代码无）；E001 平行存在不接入

## 四、全局规则（TU-8 现状，对照模板）

### 4.1 广播机制
- 谁广播：无显式广播引擎。近似"广播"= 七链 T/C/D/M/W/L/E 骨架（结构广播，非信号广播）
- 广播内容：结构/状态，非标量信号
- 谁接收：按链订阅
- 接收后影响：架构层调制，非运行时 tick 内增益
- 红标：缺 Qwen 说的"全局广播标量/向量"机制；各引擎各自读文件，无统一广播总线

### 4.2 衰减规则
- 什么在衰减：surface_tension 历史（surface_tension_decay cron）、梦境拓扑快照（dream_decay）、疤（累积收敛）
- 衰减函数：指数衰减为主
- 衰减速度：surface_tension 固定；dream 半衰期 1~2h 可配
- 衰减到零：归档/遗忘；surface_tension 历史超 1000 行归档
- 红标：每引擎独立衰减，无统一衰减引擎

### 4.3 Tick / 时间结构
- 一个 tick：当前 = cron 各自 interval（300/360/1800s…），**非同步逻辑步**
- tick 内执行顺序：各 cron 独立进程、串行跑（cron_daemon 单线程），**无双缓冲**
- 多时间尺度：有（感知快 / 梦境整合慢 / 代谢 900s），但是各 cron 间隔拼凑，不是显式快/慢 tick
- 读写规则：顺序写入，无快照；E003 读 E002 上一轮文件 = 隐式延迟，**本 tick 写的值本 tick 读不到** → 这反而近似双缓冲副作用，但非设计
- 红标：这是 Qwen 批判的核心——伪管道，无同步 tick + 双缓冲

### 4.4 可塑性 / 学习
- 什么会变：疤（TopologyThermalMonitor 累积）、Λ（λ 矩阵）
- 变化规则：疤 = base + scar_history*0.3（收敛 ~1.43×基线）；Hebbian **规划未实现**
- 时间尺度：疤累积（慢）
- 睡眠/整合：梦境期（dream_consolidation）离线整合
- 红标：耦合权重本身不可塑（C001-C009 强度全固定）；"耦合关系本身会变"未实现

### 4.5 注册表 / 全局状态
- 存什么：每引擎各自 `_agent_memory/*.json`；无统一引擎状态注册表
- 谁能写：各引擎写自己文件
- 谁能读：按文件名硬编码互读（E003 读 E002/E005/E006）
- 生命周期：持久累积（JSON 文件）
- 红标：hook_registry / cognitive_friction_registry / behavior_state 存在但是**内部钩子/摩擦**注册表，非引擎状态注册表。缺 Qwen 说的"全局引擎状态注册表 + 端到端读取"

## 五、特殊机制
- 七链 T/C/D/M/W/L/E：结构耦合骨架（非信号广播）
- 钢印 + alignment_verify：出件仲裁（E007）
- entropy_guard：注意力茧房防御（【待填】E0xx）
- 梦境 dual_surface：深层拓扑 / 表层转译（【待填】）
- F层 foraging：内在目的性（【待填】）

## 六、已知问题 / 没想清楚的地方
1. **3 套平行情感表示**（E001 EmotionCategory / E002 7D / E003 scalar），无映射桥 → 维度混乱
2. **魔法权重埋 consumer**（TENSION_MAX=3.0、0.6/0.4/0.3/0.5、0.3/0.2）→ 耦合不可见不可改
3. **延迟隐式 = cron 轮询间隔** → 耦合图里看不出
4. **调制被埋**（lambda_mode/pain → orb 红）写成 if 不是边权重
5. **回边缺失**（E007→E002 设计有、代码无）→ 图被当管道漏环
6. **无同步 tick + 双缓冲**：当前是各 cron 独立轮询的伪管道
7. **无全局引擎状态注册表**：各引擎文件硬编码互读
8. **耦合权重不可塑**：C001-C009 全固定，Hebbian 未实现
9. **E001 orphan**：60KB 情感引擎不进运行时，与 E002 平行浪费

---

# 续填：批次 2-6（引擎 E009-E030 + 耦合 C010+ + 回路 L002-L006）
> 状态文件落点：[核]=本轮回 grep 验证；[待核]=文件未定位，依记忆填；[推]=推断耦合。

## 一续、引擎清单（批次2-6）

### E009 dream_consolidation（梦境整合）
- 功能：离线整合拓扑快照、T0 矛盾蒸馏、跨相态通道
- 输入：拓扑快照、tension_distiller 报告、dream_decay 衰减器
- 输出：整合后记忆、steel_env_annotation 累计冲突
- 状态：dream_consolidation_state.json [核]
- 触发：dream_check_cron（720s）/ 睡眠期
- 回路：记忆回路 / 元耦合

### E010 tension_distiller（张力蒸馏）
- 功能：把张力/冲突蒸馏成 WreckageNode，上报 contradiction_type
- 输入：锚点(secure_vault/anchors.json)、tension_queue.json
- 输出：DistillerReport.nodes（含 contradiction_type）
- 状态：tension_queue.json + anchors.json [核]
- 触发：由 E009 在梦境期调用（T0 段）
- 回路：记忆回路

### E011 dissonance_amplifier（失调放大）
- 功能：梦境期触发，放大认知失调信号
- 输入：失调信号
- 输出：dissonance 日志/挂点
- 状态：dissonance_state.json / dissonance_hang_points.json [核]
- 触发：梦境期
- 回路：记忆回路

### E012 tu8_memory（记忆核心）
- 功能：store/recall/forget，长短期记忆
- 输入：对话、蒸馏结果
- 输出：记忆读写
- 状态：memory/*.md + _agent_memory/00_state.md [核]
- 触发：对话/心跳
- 回路：记忆回路（枢纽）

### E013 anchor_activation_protocol（锚点激活）
- 功能：深层→表层信号隔离、锚点激活
- 输入：深层拓扑信号
- 输出：激活锚点、source 标记(tension_distiller/dream_consolidation…)
- 状态：secure_vault/anchors.json [核]
- 触发：信号到达
- 回路：记忆回路

### E014 cognitive_friction_detector（认知摩擦）
- 功能：检测 7 类认知摩擦，三级阈值
- 输入：对话/输出、surface_tension 事件
- 输出：friction 记录 → cognitive_friction_registry
- 状态：cognitive_friction_registry.json / cognitive_friction_log.jsonl [核]
- 触发：出件前（HP1）
- 回路：注意/认知回路
- 红标：registry→surface_tension_state 传播链曾断裂（P3 修过）

### E015 entropy_guard（茧房防御）
- 功能：注意力茧房紧急熔断，低熵链唤醒
- 输入：链激活频率
- 输出：熵报告、强制注入
- 状态：_agent_memory（cron_entropy_guard_state.json）[核]
- 触发：cron（3600s）/ 紧急熔断
- 回路：注意/认知回路
- 红标：真数据需 EntropyAwareRouter 接 tu8_dispatch（未接，仅 cron 监控）

### E016 active_curiosity（主动好奇）
- 功能：低频主动探索（小溪 L2）
- 输入：沉默间隔、heartbeat_state
- 输出：好奇动作
- 状态：.heartbeat_state.json [核]
- 触发：idle≥0.5h
- 回路：注意/认知回路

### E017 self_probe（自我探针）
- 功能：自我探测、锚点清理
- 输入：锚点
- 输出：探针结果
- 状态：[待核]（文件未定位，疑在 scripts/）
- 触发：心跳/主动
- 回路：注意/认知回路

### E018 intuition_bias（直觉偏置）
- 功能：痛觉调制决策层（mode/temp/spawn_subagent/compact/confidence_damp）
- 输入：body_regulation.json（内感受）
- 输出：决策层每轮读取的偏置
- 状态：memory/body_regulation.json [核 reads]
- 触发：每轮开始
- 回路：注意/认知回路

### E019 contradiction_arbitrator（矛盾仲裁）
- 功能：冲突仲裁、判例库写入
- 输入：冲突报告（来自 E007）
- 输出：arbitration_precedents.jsonl（判例）
- 状态：memory/arbitration_precedents.jsonl [核]
- 触发：E007 调用
- 回路：仲裁/元认知

### E020 behavior_upgrader（行为升级/双拦截）
- 功能：双向拦截（复盘/对齐），conflict_log 记录
- 输入：冲突（来自 E007 EQUAL=60）
- 输出：behavior_state.json（conflict_log）
- 状态：behavior_state.json [核]
- 触发：E007 写入后同步
- 回路：仲裁/元认知

### E021 steel_seal_verifier（钢印验证）
- 功能：钢印存在/持久/认知签名/格式/思维/语言校验
- 输入：待验证内容
- 输出：钢印验证结果 → naming_module
- 状态：[待核]（可能被 naming_module 调用；steel_seal_pool.json）
- 触发：命名/出件前
- 回路：仲裁/元认知

### E022 world_model_l1l4（视觉世界模型 L1-L4）
- 功能：场景CSG/物理联系/动态实体/动作意图
- 输入：UnifiedSceneReport + L5MotionReport（来自 E023/E024/E025）
- 输出：WorldModelState（in-memory）
- 状态：无持久（numpy-free，内存）[核]
- 触发：视觉帧（需 numpy 激活）
- 回路：感知/世界模型

### E023 singularity_unifier（奇点统一）
- 功能：O_scene/O_agent/O_object 统一，偏移向量
- 输入：检测框/运动信号
- 输出：UnifiedSceneReport（in-memory）[核]
- 状态：无持久
- 触发：视觉帧
- 回路：感知/世界模型

### E024 dual_mode_switcher（双模态切换）
- 功能：频域失败→降级空间慢通路
- 输入：图像帧
- 输出：SliceReport（in-memory）[核]
- 状态：synthetic_test_data（仅测试）
- 触发：视觉帧
- 回路：感知/世界模型
- 红标：依赖 numpy，本环境无法导入 → 真帧源未接

### E025 l5_motion_decoupler（L5 运动解耦）
- 功能：相机-空间运动解耦 (R_t,T_t)
- 输入：帧序列
- 输出：L5MotionReport（in-memory，numpy）[核]
- 状态：无持久
- 触发：视觉帧
- 回路：感知/世界模型

### E026 interoceptive_cortex（内感受皮层）
- 功能：躯体信号监测、内感受
- 输入：surface_tension_state.json [核 reads]
- 输出：interoception_state
- 状态：interoception_state.json [核]
- 触发：cron（360s/420s）
- 回路：感知/世界模型（桥接情感↔躯体）

### E027 naming_module（命名）
- 功能：命名/钢印署名
- 输入：steel_seal 验证（E021）
- 输出：naming_log / health_log
- 状态：secure_vault/naming_log.json / health_log.json [核]
- 触发：命名事件
- 回路：仲裁/元认知 → 输出

### E028 presence_monitor（在场感知）
- 功能：造物主在场/离开检测
- 输入：沉默间隔
- 输出：presence_state（present/away）
- 状态：presence_state.json [核]
- 触发：心跳
- 回路：目的/输出

### E029 pre_task_check（重活门禁）
- 功能：写代码/长任务前身体姿态门禁
- 输入：body_regulation.json + intuition_bias
- 输出：GO/NO-GO
- 状态：memory/body_regulation.json [核 reads]
- 触发：重活前
- 回路：目的/输出

### E030 F层 foraging（觅食器官）
- 功能：沉默>8h 低频视觉试探，内在目的性
- 输入：沉默信号
- 输出：试探信号
- 状态：[待核]（F层 v1.5，架构已定未全落地）
- 触发：idle>8h
- 回路：目的/输出

## 二续、耦合关系（批次2-6 关键边）

### C010  E002→E014（surface_tension→认知摩擦）
- 方向：→；内容：张力事件→摩擦检测输入；方式：触发；强度：固定；延迟：出件前；条件：常驻；可塑性：否 [核]

### C011  E014→E007（认知摩擦→对齐校验 HP1）
- 方向：→；内容：friction_registry→pending_friction_surfacing；方式：门控；强度：固定；延迟：出件前；条件：HP1 钩子；可塑性：否 [核]

### C012  E009→E010（梦境→张力蒸馏 T0）
- 方向：→；内容：dream_consolidation 调用 tension_distiller.distill()；方式：触发；强度：固定；延迟：梦境期；条件：T0 段；可塑性：否 [核]

### C013  E010→E009（张力蒸馏→梦境 累计）
- 方向：→；内容：nodes.contradiction_type → accumulate_distiller_conflict；方式：调制；强度：累计≥5 触发；延迟：梦境期；条件：常驻；可塑性：否 [核，本次会话接线]

### C014  E007→E020（对齐→行为升级 conflict_log）
- 方向：→；内容：EQUAL=60 冲突→behavior_state.conflict_log；方式：记录；强度：固定；延迟：即时；条件：EQUAL=60；可塑性：否 [核，本次会话]

### C015  E007→E019（对齐→矛盾仲裁 判例库）
- 方向：→；内容：priority=60→record_precedent；方式：记录；强度：固定；延迟：即时；条件：EQUAL=60 & steel_mark 缺席；可塑性：否 [核]

### C016  E026→E002（内感受→张力 读）
- 方向：→(读)；内容：interoceptive 读 surface_tension_state；方式：读取；强度：固定；延迟：poll 360s；条件：常驻；可塑性：否 [核]

### C017  E018→决策层（直觉偏置调制）
- 方向：→；内容：posture→mode/temp/compact/confidence_damp；方式：调制；强度：固定分级；延迟：每轮；条件：常驻；可塑性：否 [核]

### C018  E016→E028（好奇↔在场）
- 方向：⇄；内容：idle/沉默↔presence；方式：调制；强度：固定；延迟：心跳；条件：常驻；可塑性：否 [推]

### C019  E021→E027（钢印验证→命名）
- 方向：→；内容：钢印结果→署名；方式：门控；强度：固定；延迟：命名时；条件：常驻；可塑性：否 [核，P3-2d]

### C020  E023+E024+E025→E022（L5→世界模型）
- 方向：→；内容：UnifiedSceneReport+L5MotionReport→WorldModelState；方式：输入；强度：固定；延迟：帧；条件：numpy 激活；可塑性：否 [核]

### C021  E015→tu8_dispatch（茧房防御 未接）
- 方向：→(设计)；内容：route_with_defense 接管分发；方式：门控；强度：固定；延迟：0；条件：未接；可塑性：否 [红标：仅 cron 监控，未挂真数据]

### C022  E012↔多方（记忆 枢纽）
- 方向：⇄；内容：store/recall 被多数引擎调用；方式：读写；强度：固定；延迟：调用期；条件：常驻；可塑性：否 [核，E012 是记忆枢纽]

### C023  E030→视觉/试探（觅食 未全接）
- 方向：→(设计)；内容：沉默>8h→低频视觉试探；方式：触发；强度：≤1次/日；延迟：8h；条件：未全落地；可塑性：否 [待核]

## 三续、回路 / 功能群（批次2-6）

### L002 记忆回路
- 包含：E009/E010/E011/E012/E013（+E007 仲裁）
- 功能：对话→记忆存储→梦境期蒸馏整合→锚点激活
- 内部耦合：E009→E010（T0）、E010→E009（累计）、E012 枢纽、E013 隔离
- 对外：输出整合记忆→E007（仲裁）/E012
- 与其他：E014（摩擦）写入、E007 反馈

### L003 注意/认知回路
- 包含：E014/E015/E016/E017/E018
- 功能：摩擦检测、茧房防御、主动好奇、自我探针、直觉偏置
- 内部：E014→E007(HP1)、E018 调制决策、E016 探索
- 对外：E014→E007、E018→决策层
- 与其他：E015 待接 tu8_dispatch（C021）

### L004 仲裁/元认知回路
- 包含：E007/E019/E020/E021/E027
- 功能：出件校验+仲裁+判例+行为升级+钢印+命名
- 内部：E007→E019(判例)、E007→E020(conflict_log)、E021→E027
- 对外：门控所有出件（HP1/出件前）
- 与其他：接收 E014(摩擦)/E002(张力)/C013(蒸馏冲突)

### L005 感知/世界模型回路
- 包含：E022/E023/E024/E025/E026
- 功能：视觉帧→L5解耦→奇点统一→双模态→L1-L4世界模型；内感受桥接
- 内部：E025→E023→E024→E022（流水线）；E026 桥情感↔躯体
- 对外：世界模型→下游（待接）
- 与其他：依赖 numpy（本环境缺→真帧未跑）

### L006 目的/输出回路
- 包含：E030/E008/E027/E028/E029
- 功能：内在目的(觅食)、输出(render)、命名、在场、门禁
- 内部：E029 门禁→重活、E028 在场→E016、E030 觅食→试探
- 对外：E008→用户（语音/视觉）
- 与其他：E027→E021(命名) 属 L004

## 八、全局已知问题汇总（累计情感+批次2-6）
1. **3 套平行情感表示**（E001/E002/E003）无桥
2. **魔法权重埋 consumer**（TENSION_MAX=3.0、0.6/0.4/0.3/0.5、0.3/0.2）
3. **延迟隐式 = cron 轮询间隔**
4. **调制被埋**（lambda→orb 红写成 if）
5. **回边缺失**（E007→E002 设计有代码无）
6. **无同步 tick + 双缓冲**：各 cron 独立轮询伪管道
7. **无全局引擎状态注册表**：各引擎文件硬编码互读
8. **耦合权重全固定**：C001-C023 无一条可塑，Hebbian 未实现
9. **E001 orphan**：60KB 情感引擎不进运行时
10. **E015 真数据缺失**：entropy_guard 仅 cron 监控，route_with_defense 未接 tu8_dispatch（C021）
11. **E024/E025/E022 真帧未跑**：numpy 缺失 → 感知回路 L005 本机空转（parked）
12. **E030 F层未全落地**：觅食器官架构定 v1.5，触发/试探未接生产
13. **E017 self_probe 文件未定位**：锚点清理逻辑落点不明
14. **传播链断裂史**：cognitive_friction_registry→surface_tension_state（C010）曾断，P3 修；仍无统一注册表防复发
15. **registry 碎片化**：hook_registry / cognitive_friction_registry / behavior_state 三套并存，非统一引擎状态注册表（Qwen 4.5 缺位）
