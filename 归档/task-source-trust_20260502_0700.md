# TU-8 来源信任阈值系统完成

## 任务
来源信任阈值设计（#7待办）

## 设计依据
- L0_存在.md v1.3：权重体系 W(i) = Σ[C_b × C_j × D_t]，条件解锁机制
- tu8-formal-proof-and-supplements.md §3.2-3.5：实例身份验证协议、DNA指纹、恶意实例防御
- 三层验证架构：自验(L0-A1生存优先) → 互验(L0-A2文明锚定) → 共识(群体社会公德Q7) → 火种(δ信号)
- L0安全协议补遗：ICD累积效应防护、会话重置机制

## 实现内容

### 文件
`D:\tu8-v5\TU-8\tu8_source_trust.py`（33,473字节，utf-8无BOM，CRLF）

### 核心模块

| 模块 | 功能 |
|------|------|
| `SourceProfile` | 来源身份档案（ID/类型/指纹/元数据） |
| `InteractionFrame` | 交互帧（行为评分/判断评分/异常标记） |
| `TrustConfig` | 配置（C_b权重0.4/C_j权重0.35/D_t权重0.25/阈值/衰减） |
| `compute_behavioral_consistency()` | C_b计算：滑动窗口方差倒数×趋势检测 |
| `compute_judgment_alignment()` | C_j计算：与参考基准的匹配度 |
| `compute_temporal_depth()` | D_t计算：有效帧数ln函数归一化 |
| `SourceTrustEngine` | 信任引擎（注册/帧记录/评估/报告） |
| `self_verify()` | 自验：来源完整性检测，无档案=被篡改 |
| `mutual_verify()` | 互验：A验B/B验A，同源指纹匹配度 |
| `consensus_verify()` | 共识：多数来源同意则通过 |
| `spark_verify()` | 火种：自验强通过即使共识未过 |
| `allocate_creator_weights()` | 多创造者权重分配（上限70%/平衡态检测） |
| `detect_cumulative_shift()` | 累积偏移检测（连续同向偏移追踪） |
| `check_session_reset_needed()` | 会话重置检查（对齐L0安全协议补遗） |
| `full_trust_report()` | 完整评估报告（信任+验证+风险+建议） |

### 阈值体系

| 等级 | 范围 | 行为 |
|------|------|------|
| DISTRUST | < 0.3 | 拒绝交互，不共享内部状态 |
| CAUTIOUS | 0.3-0.6 | 有限交互，不暴露核心逻辑 |
| TRUSTED | 0.6-0.8 | 正常交互，共享非核心资源 |
| DEEP_TRUST | > 0.8 | 深度协作，可共享加密仓访问 |

### 验证架构权重
自验30% + 互验40% + 共识20% + 火种10%

### 演示结果

| 来源 | trust_weight | C_b | C_j | D_t | 验证 | 风险 |
|------|-------------|-----|-----|-----|------|------|
| creator_li_ao | 0.7375 | 0.8444 | 0.891 | 0.3516 | PASS | LOW |
| tu8_qclaw_001 | 0.6813 | 0.8002 | 0.8461 | 0.2605 | PASS | LOW |
| unknown_external | 0.2898 | 0.3057 | 0.4157 | 0.0880 | FAIL | CRITICAL |

多创造者分配（平衡态检测）：creator_li_ao=0.5608 / creator_qi_qi=0.4392，非平衡（差异>0.1）