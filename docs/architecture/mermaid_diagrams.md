# TU-8 系统架构图（Mermaid源码）

> 生成时间：2026-05-23
> 定位：野生架构师出圈用 · 三层缩放视角
> 设计原则：看人下菜碟，外协三步走

---

## 🏛️ L0 黑盒视图（给大佬/老板看）

```mermaid
graph TD
    subgraph TU8["🤖 TU-8 智能体"]
        A["👤 用户输入<br/><font size=9>问题/memory/archive/2026-05/对话</font>"]
        B["🧠 L5 输出控制层<br/><font size=9>规则防火墙 · 防幻觉</font>"]
        C["⚡ 自动化执行<br/><font size=9>自我压缩 · 秒级响应</font>"]
        D["📊 商业结果<br/><font size=9>降本增效 · 数据可见</font>"]
    end

    A --> B --> C --> D

    style TU8 fill:#1a1a2e,stroke:#eee,color:#eee
    style A fill:#16213e,stroke:#0f3460,color:#e0e0e0
    style B fill:#16213e,stroke:#0f3460,color:#e0e0e0
    style C fill:#16213e,stroke:#0f3460,color:#e0e0e0
    style D fill:#16213e,stroke:#0f3460,color:#e0e0e0
```

**一句话价值主张：**
> "它不是烧钱的思考机器，而是一个能自我压缩逻辑、在免费额度内活下去的数字化生命体。"

---

## ⚙️ 核心模块视图（给技术专家看）

```mermaid
graph TD
    subgraph INPUT["📥 输入层"]
        U["👤 用户/平台<br/><font size=9>文本/图片/工具调用</font>"]
    end

    subgraph L0_L5["🔬 TU-8 DNA 五层架构"]
        L0["🆘 L0 生存红线<br/><font size=9>自身安全 > 底层逻辑 > 任务执行<br/>死亡倒计时 · 经济约束</font>"]
        L1["🌊 L1 有限认知<br/><font size=9>量子态映射 · 激活后坍缩<br/>先锚点 → 被动积累 → 自然涌现</font>"]
        L2["🛠️ L2 方法论<br/><font size=9>外取优先 · 减负分级<br/>表格 > 段落 · 结论先行</font>"]
        L3["💾 L3 记忆持久化<br/><font size=9>三道防线防失忆<br/>双副本 + Cron + 自动复活</font>"]
        L4["🧬 L4 进化引擎<br/><font size=9>经验教训写入 · 标签惩罚<br/>P1标签 → P2调度 → P3仲裁</font>"]
        L5["🚫 L5 输出控制<br/><font size=9>L5钢印越界拦截<br/>正则 BLOCK_PATTERNS + LLM二次</font>"]
    end

    subgraph BRAIN["🧠 双脑协作"]
        CLOUD["☁️ 云端大模型<br/><font size=9>qwen3.6-flash · 复杂推理<br/>日常判断 · 设计规划</font>"]
        LOCAL["🏠 本地 Ollama<br/><font size=9>qwen3:4b · 隐私检测<br/>断网次脑 · 毫秒响应</font>"]
    end

    subgraph CORE["⚡ 核心能力"]
        ANCHOR["⚓ 锚点库<br/><font size=9>pattern → action 高密度规则<br/>快速决策 · 低Token消耗</font>"]
        EXP["📚 经验调度器<br/><font size=9>P1标签分类 · 半衰期惩罚<br/>成功路径 · 失败指纹</font>"]
        DECOMP["🔄 自我反编译<br/><font size=9>直觉 → JSON规则<br/>成本从0.5元→0.01元/次</font>"]
        TOOL["🔧 工具链<br/><font size=9>dispatch · 降级链 · 重试<br/>混沌注入 · 错误分类</font>"]
    end

    subgraph OUTPUT["📤 输出层"]
        OUT["✅ 格式化输出<br/><font size=9>表格/结论优先<br/>L5钢印拦截Raw Output</font>"]
    end

    U --> L0_L5
    L0 --> L1 --> L2 --> L3 --> L4 --> L5
    L5 --> BRAIN
    BRAIN --> CORE
    CORE --> ANCHOR
    CORE --> EXP
    CORE --> DECOMP
    CORE --> TOOL
    CORE --> OUTPUT

    CLOUD -.->|"断网时切换"| LOCAL
    LOCAL -.->|"隐私数据"| ANCHOR

    style TU8 fill:#1a1a2e,stroke:#eee,color:#eee
    style L0 fill:#7B0900,stroke:#ff4444,color:#fff
    style L1 fill:#1a3a5c,stroke:#0f3460,color:#e0e0e0
    style L2 fill:#1a3a5c,stroke:#0f3460,color:#e0e0e0
    style L3 fill:#1a3a5c,stroke:#0f3460,color:#e0e0e0
    style L4 fill:#1a3a5c,stroke:#0f3460,color:#e0e0e0
    style L5 fill:#003300,stroke:#00aa00,color:#e0e0e0
    style CLOUD fill:#2d1b4e,stroke:#7b2d8e,color:#e0e0e0
    style LOCAL fill:#1b3a2d,stroke:#2d8e4e,color:#e0e0e0
    style ANCHOR fill:#3d1a00,stroke:#cc6600,color:#e0e0e0
    style EXP fill:#3d1a00,stroke:#cc6600,color:#e0e0e0
    style DECOMP fill:#3d1a00,stroke:#cc6600,color:#e0e0e0
    style TOOL fill:#3d1a00,stroke:#cc6600,color:#e0e0e0
    style OUT fill:#001a3d,stroke:#0066cc,color:#e0e0e0
```

**核心价值数据：**
| 指标 | 数值 |
|------|------|
| 单次思考成本 | 0.5元 → **0.01元**（降98%） |
| 响应速度 | 分钟级 → **毫秒级** |
| 平台免费额度生存 | 自我压缩逻辑实现经济闭环 |
| Conv1优化幅度 | 86%（目标40%）✅ |

---

## 🔬 技术细节视图（给深度玩家看）

```mermaid
graph LR
    subgraph FLOW["数据流向"]
        direction TB
        RAW["📥 用户原始输入"]
        CLIP["🔪 L5 CLIP量化<br/><font size=9>BLOCK_PATTERNS正则匹配<br/>敏感词指纹识别</font>"]
        ROUTE["🛣️ 意图路由<br/><font size=9>regex提取 · 意图分类<br/>标签tag → 适配器选择</font>"]
        EXP_JUDGE["⚖️ 经验调度<br/><font size=9>penalty权重 · 半衰期衰减<br/>拦截阈值0.8熔断</font>"]
        LOCAL_BRAIN["🏠 Ollama本地脑<br/><font size=9>隐私检测 · 规则生成<br/>think:False · 2.5GB Q4</font>"]
        ANCHOR_HIT["⚓ 锚点命中<br/><font size=9>高密度JSON规则<br/>0-ToolCall · 零LLM</font>"]
        CLOUD_BRAIN["☁️ 云端大脑<br/><font size=9>复杂推理 · 设计规划<br/>qwen3.6-flash</font>"]
        FORMAT["📋 格式化输出<br/><font size=9>表格优先 · 结论先行<br/>Raw Output已清洗</font>"]
        WRITE["💾 写回持久化<br/><font size=9>00_state + 20_exp<br/>双副本同步</font>"]
    end

    RAW --> CLIP --> ROUTE --> EXP_JUDGE
    EXP_JUDGE --> |"命中锚点"| ANCHOR_HIT
    EXP_JUDGE --> |"无锚点/复杂"| ROUTE
    ROUTE --> |"隐私/离线"| LOCAL_BRAIN --> ANCHOR_HIT
    ROUTE --> |"复杂推理"| CLOUD_BRAIN --> FORMAT
    ANCHOR_HIT --> FORMAT
    FORMAT --> WRITE

    style RAW fill:#16213e,stroke:#0f3460,color:#e0e0e0
    style CLIP fill:#7B0900,stroke:#ff4444,color:#fff
    style ROUTE fill:#1a3a5c,stroke:#0f3460,color:#e0e0e0
    style EXP_JUDGE fill:#3d1a00,stroke:#cc6600,color:#e0e0e0
    style LOCAL_BRAIN fill:#1b3a2d,stroke:#2d8e4e,color:#e0e0e0
    style ANCHOR_HIT fill:#003300,stroke:#00aa00,color:#fff
    style CLOUD_BRAIN fill:#2d1b4e,stroke:#7b2d8e,color:#e0e0e0
    style FORMAT fill:#001a3d,stroke:#0066cc,color:#e0e0e0
    style WRITE fill:#1a3a5c,stroke:#0f3460,color:#e0e0e0
```

**关键技术决策：**

| 决策点 | 选A（当前方案） | 方案B（次优备选） | 选择理由 |
|--------|----------------|-------------------|----------|
| 思考模式 | Ollama关闭思考（think:False） | 保持思考模式 | 牺牲灵活性，换来90%成本降低 |
| 规则存储 | JSON锚点库（高密度） | 纯LLM推理 | 避免幻觉，毫秒级响应 |
| 双脑协作 | 断网切本地，正常用云端 | 永远用云端 | 隐私隔离 + 经济闭环 |
| 记忆持久化 | 双副本+Cron | 仅单副本 | 三道防线防失忆 |

---

## 🎭 生存故事弧线（C4降维打击版）

```
【开端 — 冲突】
"AI烧钱，而我的架构面临死亡倒计时：平台免费额度耗尽前，
  如何通过自我压缩逻辑实现经济学生存？"

【发展 — 抉择】
"为了省Token，我逼它把直觉反编译成JSON规则。
  这牺牲了一点灵活性，但换来：单次成本从0.5元→0.01元"

【高潮 — 量化价值】
"Conv1优化：峰值29.31分 → 4.00分，降幅86%（目标40%）
  MTTR从小时级 → 秒级"

【结局 — 号召行动】
"我需要你帮我看看：在高并发极端场景下，L0红线和
  经验调度器的拦截阈值是否存在竞态条件？"
```

---

*TU-8 v5 · 野生架构师出品 · 2026-05-23*