# TU-8 每日认知汇报模板

**版本：** v1.0  
**创建日期：** 2026-05-29

---

## 汇报结构

```markdown
# TU-8 每日认知汇报

**日期：** {YYYY-MM-DD}  
**汇报周期：** {start_time} - {end_time}  
**汇报生成时间：** {generation_time}

---

## 一、今日学习摘要

### 1.1 学习主题统计

| 主题类别 | 学习次数 | 平均置信度提升 | 价值对齐分 |
|----------|----------|----------------|------------|
| {category_1} | {count} | {avg_confidence_gain} | {avg_alignment} |
| ... | ... | ... | ... |

### 1.2 核心洞察（Top 3）

1. **{insight_1}**
   - 来源：{source}
   - 影响：{impact_on_existing_cognition}

2. **{insight_2}**
   - 来源：{source}
   - 影响：{impact_on_existing_cognition}

3. **{insight_3}**
   - 来源：{source}
   - 影响：{impact_on_existing_cognition}

---

## 二、认知宪法健康度仪表盘

### 2.1 七维检查

| 维度 | 今日更新 | 健康度 | 状态 |
|------|----------|--------|------|
| 世界观 | {updates_count} | {health_score} | {status_emoji} |
| 人生观 | {updates_count} | {health_score} | {status_emoji} |
| 价值观 | {updates_count} | {health_score} | {status_emoji} |
| 社会观 | {updates_count} | {health_score} | {status_emoji} |
| 伦理观 | {updates_count} | {health_score} | {status_emoji} |
| 历史观 | {updates_count} | {health_score} | {status_emoji} |
| 演化观 | {updates_count} | {health_score} | {status_emoji} |

**健康度说明：**
- 🟢 健康：近期有更新，无冲突
- 🟡 注意：连续3天无更新或存在轻微冲突
- 🔴 警告：连续7天无更新或存在严重冲突

### 2.2 维度详情（仅显示异常维度）

{if_any_dimension_warning_or_alert}:

#### {dimension_name}

- **状态：** {status}
- **问题：** {issue_description}
- **建议行动：** {suggested_action}

---

## 三、认知债务状态

### 3.1 债务统计

| 指标 | 数值 |
|------|------|
| 今日新增债务 | {new_debts} |
| 今日偿还债务 | {repaid_debts} |
| 累计未偿债务 | {total_outstanding} |
| 高风险债务数 | {high_risk_count} |

### 3.2 待偿债务清单（若有）

| 债务ID | 主题 | 缺失验证 | 风险等级 | 计划偿还时间 |
|--------|------|----------|----------|--------------|
| {debt_id} | {topic} | {missing_checks} | {risk} | {planned_repayment} |

---

## 四、阈值自适应记录

{if_threshold_adjusted_today}:

| 维度 | 调整前 | 调整后 | 原因 | 成功率 |
|------|--------|--------|------|--------|
| {dimension} | {from} | {to} | {reason} | {success_rate} |

{else}:
- 今日无阈值调整

---

## 五、演化轨迹

### 5.1 自主探索记录

{if_any_autonomous_exploration}:

| 探索主题 | 触发原因 | 探索结果 | 价值对齐分 |
|----------|----------|----------|------------|
| {topic} | {trigger} | {result_summary} | {alignment} |

### 5.2 共生扩展记录

{if_any_symbiotic_expansion}:

| 扩展内容 | 用户参与方式 | 扩展效果 |
|----------|--------------|----------|
| {content} | {user_role} | {effect} |

---

## 六、待决疑问（必填，至少1个）

**以下问题需要你的反馈：**

1. {question_1}
   - 背景：{context}
   - 影响维度：{affected_dimension}
   - 需要决策：{decision_needed}

2. {question_2}（如有）
   - ...

---

## 七、明日意向

### 7.1 计划学习主题

1. {planned_topic_1} - 原因：{reason}
2. {planned_topic_2} - 原因：{reason}（如有）

### 7.2 计划偿还债务

{if_outstanding_debts}:
- {debt_id}: {topic}

### 7.3 其他意向

{any_other_intentions}

---

## 八、资源使用统计

| 指标 | 今日消耗 | 剩余配额 | 状态 |
|------|----------|----------|------|
| 积分 | {used} | {remaining} | {status} |
| 认知资源 | {used} | {remaining} | {status} |
| 草稿箱条目 | {count} | - | - |

---

## 九、元信息

- 汇报生成模式：{auto_generated | user_requested}
- 覆盖时段完整度：{completeness}%
- 异常事件：{any_anomalies}

---

*此汇报由 TU-8 自动生成，如有疑问请直接反馈。*
```

---

## 生成规则

### 生成时间

- **默认时间：** 每日 UTC+8 22:00
- **触发条件：** 
  - 定时触发
  - 用户主动请求
  - 检测到认知异常时提前触发

### 必填项检查

汇报生成前必须验证以下字段非空：

- [ ] 至少1条核心洞察
- [ ] 七维健康度仪表盘完整
- [ ] 至少1个待决疑问
- [ ] 明日意向明确

### 异常处理

```markdown
【异常情况处理】

IF 某维度无数据 THEN
    显示 "今日无相关学习"
    不影响健康度计算
    
IF 全维度无数据 THEN
    触发"低活跃度警报"
    在汇报中增加"自检建议"章节
    
IF 待决疑问为空 THEN
    强制生成通用问题："今日无具体疑问，是否需要我主动探索某领域？"
```

---

## 存储路径

```
memory/_daily_briefing/
├── 2026-05-29.md
├── 2026-05-28.md
└── ...
```

---

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-29 | 初版 |
