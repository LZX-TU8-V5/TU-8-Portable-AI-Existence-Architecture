# 02_config — 配置层

> 所有JSON配置文件。修改前建议阅读对应注释。

## 文件清单

| 文件 | 用途 | 生效位置 |
|------|------|---------|
| `penalty_config.json` | 惩罚体系：四类错误×衰减半衰期×阈值 | TU-8调度层 |
| `reward_config.json` | 奖励体系：正面行为加分表 | TU-8调度层 |
| `value_weight_config.json` | 决策权重：短期/长期权重分配 | TU-8决策层 |
| `tag_registry.json` | P1标签系统：21标签+文档关系+有向边 | 经验调度器(P2) |
| `success_patterns.json` | 正面经验库：索引+成功模式 | 经验调度器(P2) |
| `sanitization_rules.json` | 脱敏规则：JSON格式，Ollama预处理+规则阻断 | tu8_dispatcher.py |
| `sensitive_data_checklist.md` | 敏感数据清单：脱敏层检测范围 | tu8_dispatcher.py |

## 命名规范
- `*_config.json` = 机器可读配置
- `*_checklist.md` = 人工可读清单
- 修改JSON后运行对应测试验证

## 关联代码
- 脱敏配置 → `03_code/sanitization_layer.py` + `03_code/tu8_dispatcher.py`
- 惩罚/奖励 → TU-8调度层内部逻辑
