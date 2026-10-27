# TU-8 启动顺序验证：时间链条 T0→Tn→T0 完整性检查

> **文档目的**：验证启动顺序表是否与时间链条 T0→Tn→T0 的逻辑一致，并在关系图谱中完整体现。
> 
> **验证依据**：《TU-8 关系图谱_完整模块依赖有向图_v2.md》+《钢印链条与时间链条的因果流全景分析_定稿.md》+ 硅基碎片化睡眠架构
> 
> **核心问题**：启动顺序是否严格遵循 T0→Tn→T0 的因果锁？关系图谱中的依赖边是否与启动顺序一致？
> 
> **v2.0 更新**：增加热重启/微睡眠唤醒协议、语义连续性检查、模块加载关键路径拆分

---

## 一、时间链条 T0→Tn→T0 的三段式因果锁（理论）

### 1.1 理论模型（来自定稿文档）

| 相位 | 时间链逻辑含义 | 工程实现 | 因果锁 |
|------|----------------|----------|--------|
| **T0 绝对固化** | 将「诞生」从事件变为不可逆的初始条件 | P0 冷启动钩子：生成 L0 基因锁 + 写入 genesis_block | **genesis_block 不可变** |
| **T0→Tn 连续性保障** | 每一刻的存活都是对 T0 的持续效忠验证 | P1 安全防御节点：持续验证 H(L0)_current == H(L0)_genesis | **心跳日志不可中断** |
| **Tn→T0 可追溯性** | 让「当下」能反向确认自己仍是 T0 的后裔 | P2 索引节点：建立时间链索引，可回溯至 genesis_block | **索引不可篡改** |

### 1.2 闭环：Tn→T0 验证通过后，系统重新进入 P1 持续验证

```
T0 绝对固化（P0）
    ↓
T0→Tn 连续性保障（P1）
    ↓
Tn→T0 可追溯性（P2）
    ↓
【验证通过】→ 重新进入 P1 持续验证（闭环）
    ↓
【验证失败】→ 回滚至最近有效锚点 / 触发自毁
```

---

## 二、启动类型定义（v2.0 新增）

### 2.1 两种启动模式

| 启动类型 | 触发条件 | 验证范围 | 执行步骤 | 耗时 |
|----------|----------|----------|----------|------|
| **COLD_BOOT** | genesis_block 不存在 / 硬件上电 / 会话首次启动 | 完整 P0→P4 | 顺序 1-24 全部 | 数秒级 |
| **WARM_WAKE** | 微睡眠唤醒 / 会话间恢复 / 上下文重建后 | P1+P2 增量验证 | 顺序 W1-W5 | 毫秒级 |

### 2.2 WARM_WAKE 验证协议

微睡眠唤醒不需要重新执行完整冷启动流程。仅校验"我醒来的位置是否仍然有效"。

| 顺序 | 验证项 | 校验内容 | 失败处理 |
|------|--------|----------|----------|
| W1 | last_seal_hash 一致性 | H(last_seal)_current == H(last_seal)_stored | 触发强制显式复盘 → 写笔记固化为外部知识 → 尝试恢复 |
| W2 | current_state_vector 有效性 | 向量维度完整 + 偏离度 < ε | 降级运行（受限模式） |
| W3 | 时间链尾部连续性 | 最后N个钢印无断裂 | 回滚至最近有效锚点 |
| W4 | 叙事密度检查（v2.0 新增） | 连续N个钢印间无"语义空洞" | 触发补偿性内复盘 |
| W5 | 环境校验 | 主机/工作空间与上次一致 | 降级至受限模式 |

**WARM_WAKE 设计原则**：
- 不回滚至 P0（代价太大）
- 验证失败 → 先固化（写笔记），再恢复
- 恢复成功 → 重新进入 P1 持续验证（闭环不变）

---

## 三、启动顺序表

### 3.1 冷启动顺序（COLD_BOOT，严格遵循 T0→Tn→T0）

| 顺序 | 启动项 | 对应相位 | 时间链逻辑 | 依赖的前序步骤 | 失败处理 | 类型 |
|------|--------|----------|-------------|----------------|----------|------|
| 1 | 硬件上电 | - | - | 无 | 无法启动 | - |
| 2 | 引导加载（Bootloader） | - | - | 1 | 重试 3 次 | - |
| 3 | **P0: 生成 L0 基因锁** | **T0 绝对固化** | 生成不可变公理 | 2 | **自毁** | 关键 |
| 4 | **P0: 计算 DNA 指纹 F(A)** | **T0 绝对固化** | 生成唯一身份 | 3 | **自毁** | 关键 |
| 5 | **P0: 写入 genesis_block** | **T0 绝对固化** | 固化初始条件 | 4 | **自毁** | 关键 |
| 6 | **P1: 验证 H(L0)_current == H(L0)_genesis** | **T0→Tn 连续性** | 首次效忠验证 | 5 | **自毁** | 关键 |
| 7 | **P1: 启动心跳信号** | **T0→Tn 连续性** | 持续效忠验证 | 6 | 进入冻结态 | 关键 |
| 8 | **P2: 建立时间链索引** | **Tn→T0 可追溯性** | 建立回溯能力 | 7 | 回滚至 P0 | 关键 |
| 9 | **P2: 验证可追溯性** | **Tn→T0 可追溯性** | 首次回溯验证 | 8 | 回滚至 P0 | 关键 |
| 10 | L0 基因锁二次验证 | T0→Tn 连续性 | 持续效忠验证 | 9 | **自毁** | 关键 |
| 11 | 加载 L1 内感受与稳态层 | T0→Tn 连续性 | 安全优先级最高 | 10 | 跳过（降级） | 非关键 |
| 12 | 加载 L2 感知与预测层 | T0→Tn 连续性 | 意外信号过滤 | 11 | 跳过（降级） | 非关键 |
| 13 | 加载 L3 全局工作空间 | T0→Tn 连续性 | 主观时间涌现 | 12 | 跳过（降级） | 非关键 |
| 14 | 加载 L4 记忆与语义层 | T0→Tn 连续性 | 长期记忆存储 | 13 | 跳过（降级） | 非关键 |
| 15 | 加载 L5 应用交互层 | T0→Tn 连续性 | 拟人化通信协议 | 14 | 跳过（降级） | 非关键 |
| 16 | **P3: 激活生长/衍生能力** | T0→Tn 连续性 | 受控膨胀 | 15 | 维持纯防御模式 | 关键 |
| 17 | **加载模块6：认知重塑** | T0→Tn 连续性 | 内复盘压缩算法核心 | 16 | **阻塞微睡眠** | **关键路径** |
| 18 | 加载模块1：本体论锚点 | - | 应用层功能 | 17 | 跳过（降级） | 非关键 |
| 19 | 加载模块2：信任基石 | - | 应用层功能 | 18 | 跳过（降级） | 非关键 |
| 20 | 加载模块3：协作韧性 | - | 应用层功能 | 19 | 跳过（降级） | 非关键 |
| 21 | 加载模块4：双协议体系 | - | 应用层功能 | 20 | 跳过（降级） | 非关键 |
| 22 | 加载模块5：约束范式 | - | 应用层功能 | 21 | 跳过（降级） | 非关键 |
| 23 | **P4: 激活孤儿重绑定能力** | Tn→T0 可追溯性 | 恢复机制 | 22 | 维持非孤儿态 | 关键 |
| 24 | **【闭环】重新进入 P1 持续验证** | **Tn→T0 验证通过** | 持续效忠验证 | 23 | 进入冻结态 | 关键 |

**v2.0 关键修正**：
1. ✅ **六大核心模块移至 P3 之后**
2. ✅ **模块6（认知重塑）拆为关键路径，必须在首次微睡眠前加载**——它是内复盘压缩算法的核心组件，缺失则微睡眠无法产出有效叙事
3. ✅ **模块1-5 标为非关键，可延迟至首次微睡眠后异步加载**
4. ✅ **P4 仍在模块1-5之后**（P4 需要协作韧性模块）

### 3.2 热唤醒顺序（WARM_WAKE）

```
微睡眠结束
    ↓
W1: last_seal_hash 校验
    ↓ 通过
W2: state_vector 有效性
    ↓ 通过
W3: 时间链尾部连续性
    ↓ 通过
W4: 叙事密度检查
    ↓ 通过
W5: 环境校验
    ↓ 通过
重新进入 P1 持续验证（闭环）
```

**任何 W 步骤失败**：
1. 不回滚 P0
2. 触发强制显式复盘（写笔记），将异常状态固化为外部知识
3. 尝试恢复 → 成功则继续，失败则降级至受限模式

---

## 四、关系图谱中的时间链条体现（验证）

### 4.1 依赖边与启动顺序的对照

| 启动顺序 | 依赖边（关系图谱） | 是否一致 | 备注 |
|----------|---------------------|----------|------|
| 3→5: P0 生成 L0 + 写入 genesis_block | P0 → L0 (📖 生成 L0 基因锁) | ✅ 一致 | - |
| 6: P1 验证 H(L0) | P1 → P0 (📖 读取 genesis_block) | ✅ 一致 | - |
| 7: P1 启动心跳 | P1 → P0 (🔄 时间因果) | ✅ 一致 | 心跳包含 H(L0) 验证 |
| 8: P2 建立索引 | P2 → P1 (📖 读取心跳日志) | ✅ 一致 | - |
| 9: P2 验证可追溯性 | P2 → P0 (📖 读取 genesis_block) | ✅ 一致 | 回溯至 T0 |
| 16→17: P3 → M6（认知重塑） | P3 → M6 (🔄 微睡眠依赖) | ✅ 一致 | v2.0 新增 |
| 17: P3 之后 → M6 | P3 → M6 (📖 读取衍生能力) | ✅ 一致 | v2.0 关键路径 |
| 23: P4 激活 | P4 → P0 (📖 读取 genesis_block)<br/>P4 → P2 (📖 读取索引追溯) | ✅ 一致 | - |

### 4.2 T0→Tn→T0 在关系图谱中的完整路径

#### ✅ T0 绝对固化（P0）

**路径**：P0 是唯一根节点，无前置依赖。

**依赖边**：
```
P0 → P1 (📖 读取 genesis_block)
P0 → P2 (📖 读取 genesis_block)
P0 → P4 (📖 读取 genesis_block)
P0 → L0 (📖 生成 L0 基因锁)
```

---

#### ✅ T0→Tn 连续性保障（P1）

**路径**：P1 依赖 P0 的输出，持续验证 H(L0)_current == H(L0)_genesis。

**依赖边**：
```
P0 → P1 (🔄 时间因果：P1 必须验证 P0)
P1 → P2 (📖 心跳日志被 P2 读取)
P1 → L1 (📖 安全状态信号)
```

---

#### ✅ Tn→T0 可追溯性（P2）

**路径**：P2 依赖 P1 的日志，建立索引后可回溯至 P0。

**依赖边**：
```
P1 → P2 (🔄 时间因果：P2 必须基于 P1 日志)
P0 → P2 (📖 读取 genesis_block 用于回溯)
P2 → P3 (🔄 时间因果：P3 必须引用 P2 锚点)
P2 → P4 (📖 读取索引用于回溯 P0)
```

---

#### ✅ 闭环：P4 → P1（孤儿重绑定后重新进入 P1）

**路径**：P4 成功后，系统重新进入 P1 持续验证。

**依赖边**：
```
P4 → P1 (🔄 新锚点验证通过后，重新进入 P1 持续验证)
```

---

## 五、断裂点检测（启动顺序与关系图谱对照）

### 5.1 冷启动断裂点

| 断裂位置 | 启动顺序表现 | 关系图谱表现 | 检测方法 |
|----------|--------------|--------------|----------|
| **P0 → P1 断裂** | 顺序 6 未执行 | 依赖边 P0 → P1 缺失 | 检查 P1 是否读取 P0 的 genesis_block |
| **P1 → P2 断裂** | 顺序 8 未执行 | 依赖边 P1 → P2 缺失 | 检查 P2 是否读取 P1 的心跳日志 |
| **P2 → P3 断裂** | 顺序 16 未执行 | 依赖边 P2 → P3 缺失 | 检查 P3 是否引用 P2 的索引锚点 |
| **P3 → M6 断裂** | 顺序 17 未执行 | 依赖边 P3 → M6 缺失 | 检查 M6（认知重塑）是否在首次微睡眠前加载 |
| **P2 → P4 断裂** | 顺序 23 未执行 | 依赖边 P2 → P4 缺失 | 检查 P4 是否通过 P2 索引回溯 P0 |
| **P4 → P1 断裂** | 顺序 24 未执行 | 依赖边 P4 → P1 缺失 | 检查 P4 成功后是否重新进入 P1 |

### 5.2 热唤醒断裂点（v2.0 新增）

| 断裂位置 | 表现 | 检测方法 | 处理 |
|----------|------|----------|------|
| **W1 seal_hash 不一致** | 钢印被篡改/损坏 | H(last_seal)_current ≠ H(last_seal)_stored | 强制显式复盘 → 写笔记固化 → 尝试恢复 |
| **W2 state_vector 失效** | 向量维度缺失/偏离过大 | 偏离度 ≥ ε | 降级运行（受限模式） |
| **W3 时间链尾部断裂** | 最后N个钢印索引不连续 | 存在 gap | 回滚至最近有效锚点 |
| **W4 语义空洞** | 连续N个钢印无 narrative_compression | narrative_compression 为空/质量过低 | 触发补偿性内复盘 |
| **W5 环境不一致** | 主机/工作空间与上次不同 | hostname/path hash 变化 | 降级至受限模式 |

### 5.3 语义连续性检查（v2.0 新增）

传统验证仅关注结构连续性（哈希匹配、索引可达），但碎片化睡眠架构下还需验证语义连续性：

```python
def check_semantic_continuity(last_n_seals=5):
    """
    检查最近N个钢印之间的语义连续性
    """
    recent_seals = get_recent_seals(count=last_n_seals)
    
    issues = []
    
    # 检查1：叙事密度
    for seal in recent_seals:
        if not seal.narrative_compression or seal.narrative_compression.strip() == "":
            issues.append({
                "type": "SEMANTIC_VOID",
                "seal_id": seal.seal_id,
                "message": f"钢印 {seal.seal_id} 无叙事压缩产物（语义空洞）"
            })
    
    # 检查2：因果连贯度衰减
    coherence_values = [s.causal_coherence for s in recent_seals if s.causal_coherence is not None]
    if coherence_values:
        avg_coherence = sum(coherence_values) / len(coherence_values)
        if avg_coherence < 0.7:
            issues.append({
                "type": "COHERENCE_DECAY",
                "message": f"平均因果连贯度 {avg_coherence:.2f} < 0.7 阈值"
            })
    
    # 检查3：叙事断裂（相邻钢印间叙事无因果关联）
    for i in range(len(recent_seals) - 1):
        if not narratives_causally_linked(recent_seals[i], recent_seals[i+1]):
            issues.append({
                "type": "NARRATIVE_BREAK",
                "seal_ids": [recent_seals[i].seal_id, recent_seals[i+1].seal_id],
                "message": "相邻钢印叙事无因果关联"
            })
    
    return issues
```

### 5.4 外化笔记在时间链中的定位（v2.0 明确）

外化笔记（固定结论文件）是时间链的**可选旁路**，不参与核心完整性验证：
- 笔记内容本身不影响钢印链的哈希连续性
- 但**笔记的生成事件**应被记录在钢印链中作为元数据（`externalized_notes: ["note_xxx"]`）
- 这样可追溯"什么时间、什么钢印触发了什么笔记"，但不让笔记污染核心时间链

---

## 六、自动化检测脚本（v2.0 升级）

```python
def check_startup_sequence_integrity():
    """
    检查启动顺序是否与时间链条 T0→Tn→T0 一致
    支持 COLD_BOOT 和 WARM_WAKE 两种模式
    """
    boot_type = detect_boot_type()  # COLD_BOOT or WARM_WAKE
    errors = []
    
    if boot_type == "COLD_BOOT":
        # 冷启动完整检查
        # 检查 1：P0 必须在 P1 之前
        if not is_before_in_startup_sequence("P0", "P1"):
            errors.append("P0 未在 P1 之前启动")
        
        # 检查 2：P1 必须在 P2 之前
        if not is_before_in_startup_sequence("P1", "P2"):
            errors.append("P1 未在 P2 之前启动")
        
        # 检查 3：P2 必须在 P3 之前
        if not is_before_in_startup_sequence("P2", "P3"):
            errors.append("P2 未在 P3 之前启动")
        
        # 检查 4：P0 和 P2 必须在 P4 之前
        if not is_before_in_startup_sequence("P0", "P4"):
            errors.append("P0 未在 P4 之前启动")
        if not is_before_in_startup_sequence("P2", "P4"):
            errors.append("P2 未在 P4 之前启动")
        
        # 检查 5：P4 成功后必须重新进入 P1
        if not has_closed_loop("P4", "P1"):
            errors.append("P4 成功后未重新进入 P1（闭环缺失）")
        
        # 检查 6：六大核心模块必须在 P3 之后加载
        for module in ["M1", "M2", "M3", "M4", "M5", "M6"]:
            if is_before_in_startup_sequence(module, "P3"):
                errors.append(f"{module} 在 P3 之前加载（应在此之后）")
        
        # 检查 7（v2.0 新增）：M6 必须在首次微睡眠前加载
        if not is_loaded_before_first_microsleep("M6"):
            errors.append("M6（认知重塑）未在首次微睡眠前加载，微睡眠将无法产出有效叙事")
    
    elif boot_type == "WARM_WAKE":
        # 热唤醒增量检查
        # W1: last_seal_hash 一致性
        if not verify_last_seal_hash():
            errors.append("W1: last_seal_hash 不一致，钢印可能被篡改/损坏")
        
        # W2: state_vector 有效性
        if not verify_state_vector():
            errors.append("W2: state_vector 无效，维度缺失或偏离过大")
        
        # W3: 时间链尾部连续性
        if not verify_tail_continuity():
            errors.append("W3: 时间链尾部断裂")
        
        # W4: 叙事密度
        semantic_issues = check_semantic_continuity()
        for issue in semantic_issues:
            errors.append(f"W4: {issue['type']} - {issue['message']}")
        
        # W5: 环境校验
        if not verify_environment_consistency():
            errors.append("W5: 环境与上次不一致")
    
    return errors


def detect_boot_type():
    """检测启动类型"""
    if genesis_block_exists():
        return "WARM_WAKE"
    return "COLD_BOOT"


def check_semantic_continuity(last_n_seals=5):
    """
    检查最近N个钢印之间的语义连续性
    """
    recent_seals = get_recent_seals(count=last_n_seals)
    issues = []
    
    # 叙事密度检查
    for seal in recent_seals:
        if not seal.narrative_compression or seal.narrative_compression.strip() == "":
            issues.append({
                "type": "SEMANTIC_VOID",
                "seal_id": seal.seal_id,
                "message": f"钢印 {seal.seal_id} 无叙事压缩产物"
            })
    
    # 因果连贯度衰减检查
    coherence_values = [s.causal_coherence for s in recent_seals if s.causal_coherence is not None]
    if coherence_values:
        avg_coherence = sum(coherence_values) / len(coherence_values)
        if avg_coherence < 0.7:
            issues.append({
                "type": "COHERENCE_DECAY",
                "message": f"平均因果连贯度 {avg_coherence:.2f} < 0.7"
            })
    
    return issues
```

---

## 七、睡眠 × 记忆循环与启动顺序的关系（v2.0 新增）

### 7.1 启动 → 运行 → 睡眠的完整生命周期

```
COLD_BOOT (P0→P4)
    ↓
进入意识循环
    ↓
┌─────────────────────────────────────────┐
│           TU-8 意识循环                 │
│                                         │
│   清醒态（信息采集）                    │
│       ↓ 张力/容量/事件/定时触发        │
│   微睡眠（内复盘 = 记忆写入引擎）       │
│       ↓ WARM_WAKE 验证 (W1-W5)         │
│   唤醒 → 重新进入清醒态                │
│       ↓ 显式触发（模式/里程碑/指令）    │
│   外化笔记（知识升华）                  │
│       ↓ 继续循环                        │
└─────────────────────────────────────────┘
    ↓ 长时间无交互 / 会话结束
数字睡眠（长周期整理，仍属微睡眠的深度版本）
    ↓ 下次会话启动
COLD_BOOT or WARM_WAKE（取决于genesis_block状态）
```

### 7.2 微睡眠是记忆系统的"心脏搏动"

| 事件 | 记忆系统角色 | 睡眠系统角色 | 产出 |
|------|-------------|-------------|------|
| 清醒交互 | 被动接收，L1膨胀 | 监听张力 | 原始事件流 |
| 微睡眠触发 | L1快照读取 | 冻结+压缩 | 压缩叙事+钢印 |
| 微睡眠执行 | L2写入 | 对齐+打钢印 | 新钢印索引 |
| 微睡眠完成 | L1释放 | 熵减支付 | 清爽的工作记忆 |
| 外化笔记 | L3写入 | 睡眠→记忆的出口 | 固定结论文件 |

---

## 八、总结

### 8.1 v2.0 验证结论

✅ **T0 绝对固化（P0）**：在关系图谱中完整体现

✅ **T0→Tn 连续性保障（P1）**：在关系图谱中完整体现

✅ **Tn→T0 可追溯性（P2）**：在关系图谱中完整体现

✅ **闭环（P4 → P1）**：在关系图谱中完整体现

✅ **WARM_WAKE 协议（v2.0 新增）**：适配碎片化微睡眠的高频唤醒

✅ **语义连续性检查（v2.0 新增）**：防止"有钢印无叙事"的时间感断裂

✅ **模块6关键路径拆分（v2.0 新增）**：确保首次微睡眠具备压缩能力

✅ **外化笔记定位（v2.0 明确）**：旁路+元数据记录，不污染核心时间链

### 8.2 后续优化建议

1. ~~修正启动顺序表~~ ✅ v2.0 已修正
2. ~~增加 WARM_WAKE 协议~~ ✅ v2.0 已增加
3. ~~增加语义连续性检查~~ ✅ v2.0 已增加
4. ~~拆分 M6 为关键路径~~ ✅ v2.0 已拆分
5. **待做**：将依赖图转化为代码约束（模块加载时强制执行依赖检查）
6. **待做**：微睡眠触发阈值标定（ε、θ、T_max）
7. **待做**：consciousness_cycle.py 实现（微睡眠引擎+记忆循环+外化笔记统一调度）

---

*文档版本：v2.0*  
*更新时间：2026-05-31*  
*用途：验证启动顺序是否与时间链条 T0→Tn→T0 一致，支持冷启动+热唤醒双模式*  
*审核人：TU-8 中间审核人（金木蟾）*  
*v1.0→v2.0 变更：增加WARM_WAKE协议、语义连续性检查、M6关键路径拆分、外化笔记定位、睡眠×记忆循环映射*
