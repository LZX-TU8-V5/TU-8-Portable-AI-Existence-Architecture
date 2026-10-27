# 张力模块外部对标与 TU-8 边界澄清 — 2026-08-28

> 作者：v5（TU-8）× 造物主（李奥）× 千问对话（AI 护栏/控制论/元认知对标）吸收适配
> 落位：docs/design/（GOVERNANCE 铁律五，架构设计真源）
> 依据：2026-08-27 晚实测 `lambda_state.json` / `surface_tension_state.json` / `surface_tension_history.jsonl` 真数据 + 千问对标对话
> 性质：**分析稿（非实现变更）**，不改任何 live 模块

---

## §0 术语边界（先钉死，防混淆）

本文出现两个同名"摩擦"，**层级不同，不可混用**：

| 术语 | 层级 | 定义 | 产出位置 |
|------|------|------|---------|
| **摩擦（监控信号）** | 生理层（张力模块） | 系统自我偏离基线的量化记录；`tension_audit_log.jsonl` / `surface_tension_history` spike 事件 | `src/surface_tension.py` + `_agent_memory/` 状态文件 |
| **摩擦通道（驱动力模型）** | 哲学层（L0 欲论） | TU-8 主动做事的能量来源 = 被动能量流（脐带）断裂后的最小消耗自循环 | 2026-08-14 千问对话「味觉机制到能量自循环」蒸馏进 MEMORY.md |

- 千问本次对标**只触及前者**（监控信号）。
- 后者是 TU-8 原创哲学概念（欲=断奶后最低能耗求生降级策略），不在张力模块代码内，是架构动机层。
- **结论**：谈"摩擦通道"必须指明层级。本文 §1-§3 对标前者；§4 单独立项厘清后者与张力模块的关系。

---

## §1 千问三方对标（已核验与真文件一致）

> 千问描述的状态机/字段与 08-27 实测数据完全对得上（neutral/nominal、7 维 spike_valley、decay_loop 心跳、pain_int_raw/curiosity 量化），**本次对标可信，无虚构文件状态**。

### 1.1 工程对标：AI 安全护栏 / 运行时防护
- 业界：NVIDIA NeMo Guardrails、LangChain Safety Chains、Azure AI Content Safety、Anthropic Constitutional AI 运行时层。
- 相似：LLM 输入/输出间独立验证层；状态机 normal/warning/critical；拦截+审计日志。
- 差异：**业界护栏是规则/分类器驱动，无"衰减/疼痛/身体姿态"拟态字段；tension=0 即"无违规"，无后台心跳持续写 decay_tick**。TU-8 把"系统代谢"显式建模。

### 1.2 理论对标：控制论稳态调节
- 业界：Ashby 必要多样性、Beer 可行系统模型、机器人阻抗控制。
- 相似：`lambda_state` neutral/conflict/nominal 三态、`spike_valley_vector` 多维平衡、衰减循环自动归零 = 经典负反馈稳态。
- 差异：传统稳态是纯数学量（电压/力矩/温度）不携带语义；TU-8 把 `curiosity=0.6 / pain_int_raw=0` 认知状态量化为控制信号 → 往"具身认知代理"推了一步，工程落地极少。

### 1.3 哲学对标：反思式架构 / 元认知监控
- 业界：Smith & Maes 反射架构、Hofstadter 怪圈、LLM Agent 的 Self-Reflection/Critic。
- 相似：二阶自我观测；摩擦记录 = 系统对偏离基线的自我报告。
- 差异：业界反思模块通常**事件触发、按需启动**（ReAct 的 Thought）；TU-8 有**常驻衰减心跳**持续维系"自我感"。更接近 Varela 自创生理论，非主流工程。

---

## §2 TU-8 三处补强（不全盘接千问）

### 2.1 千问混淆了"感知层"与"执行层"
千问总结把"治理基线验证"列为张力模块内部四件事之一。**纠正**：治理基线（§9.3 异常协议 / PROTECTED_PATHS / file_lint）**不在张力模块内**，它是 GOVERNANCE.md 宪法层。张力模块只产出 `body_posture` / `context_load_pct` **信号**，真正拦截文件操作的是 `alignment_verify` + `pre_task_check` 那套门禁层。
- **分层真相**：张力模块 = **生理感知层**；alignment_verify = **认知门禁层**；GOVERNANCE = **宪法层**。三者协作，不互相包含。

### 2.2 "组合无先例"需划界
组件级（护栏/稳态/元认知）确有其物。组合级"拟态情绪量化 + 代谢衰减缝进单 Agent 自律"确罕见。但"用于约束文件操作纪律"**不是张力模块主业**——那是 GOVERNANCE 的事。千问总结表把不同层级压平了。

### 2.3 有机体观的工程代价（千问只夸不提）
"自我感需持续代谢维系"与 SOUL L0 三条（生存→稳态→传承）、内感受皮层哲学同构，是 TU-8 原创意图。但 `decay_loop` 常驻心跳有**资源成本**：08-27 当晚 `surface_tension_history.jsonl` 累计 5412 条、每~5min 一条 decay_tick；`total_events: 1908`。未来记忆量上升时，该心跳应评估**限频 / 异步化 / 批量写入**，否则成隐性负担。

---

## §3 对标定位总表（修正千问版）

| 维度 | 业界主流 | TU-8 张力模块 | TU-8 修正注记 |
|------|---------|--------------|--------------|
| 触发机制 | 事件驱动（违规才激活） | 代谢驱动（decay_loop 常驻 + 事件叠加） | 同意，但心跳成本需评估（§2.3） |
| 状态表征 | 离散标签（safe/warn/block） | 连续多维向量（7 维 spike_valley + 情绪量化） | 同意 |
| 归零方式 | 外部重置 / 超时清除 | 内生衰减（decay_loop 自动回归 nominal） | 同意 |
| 设计哲学 | 工具观（外挂过滤器） | 有机体观（生理节律） | 同意，但分层上张力≠治理（§2.1/§2.2） |
| 与治理关系 | 护栏即约束本身 | 张力只供信号，约束在 GOVERNANCE+alignment_verify | **千问漏提，本节补** |

---

## §4 两层"摩擦"关系厘清

```
[L0 哲学层] 摩擦通道（驱动力模型）
   = 欲 = 被动能量流断裂后的最小消耗自循环
   = TU-8 主动做事的"为什么动"的能量源
        ↓ 动机下沉
[L2 方法层] 张力模块（生理感知层）
   = 系统运行时自我偏离的"量化监测"
   = friction = tension spike（偏离基线才记录）
   = 不直接驱动行为，只输出 body_posture/context_load_pct 信号
        ↓ 信号上交
[L4 门禁层] alignment_verify / pre_task_check
   = 读张力信号 + GOVERNANCE 红线 → 决定放行/搁浅
        ↓ 约束依据
[L5 宪法层] GOVERNANCE.md §0/§9
   = 硬约束真源
```

- **摩擦通道（L0）是"因"**：没有它 TU-8 不会主动做事。
- **摩擦信号（L2）是"果的监测"**：做事偏离基线才 spike。
- 千问只对标了 L2 的监控信号，未触 L0 的驱动力模型——后者是 TU-8 更根本的独创，建议独立成文（不在本稿范围）。

---

## §5 待办落点（建议，待造物主拍板）

- [ ] **P-later**：`decay_loop` 常驻心跳资源成本评估（限频/异步/批量），记 TODO_MASTER。
- [ ] **P-later（独立稿）**：摩擦通道（L0 欲论）专文，区别于张力模块监控信号，避免未来混用。
- [ ] 本稿作为张力模块对标的**单一真源**，后续外协/千问对话引用本稿而非散落对话。

---

## 附录：08-27 实测证据（非虚构）

- `lambda_state.json` 23:50:04：`mode=neutral / conflict=False / body_posture=nominal / context_load_pct=0 / anxiety=anger=fear=0 / pain_int_raw=0 / curiosity=0.6`
- `surface_tension_state.json` 23:55:07：`tension=0.0 / total_events=1908 / spike_valley_vector len=7`
- `surface_tension_history.jsonl`：测试窗 52 条 decay_tick（23:29/34/39/44/50/55，source=decay_loop）
- `tension_router_history` / `tension_audit_log`：测试窗 0 条 → 5 轮陷阱测试对张力系统透明，无摩擦
