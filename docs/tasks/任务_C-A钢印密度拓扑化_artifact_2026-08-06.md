# 任务工件：C→A 钢印密度拓扑化

## 执行摘要
把"钢印密度"从孤立计数升级为图拓扑属性（锚点交互图），接入 `alignment_verify.py` 仲裁。

## 关键发现

### 数据源扫描结论
| 文件 | 结论 |
|------|------|
| `memory/anchors.json` | 7 锚点，0 跨锚点边 → 星形网络 |
| `memory/seal_sensor_feed.jsonl` | 61 事件，2 条 3 节点父子链，但锚点间无共享 seal |
| `secure_vault/index.json` | entries 无 anchor_id 字段，不可用于建边 |

### 根因
1. **图无边的本质**：7 个锚点被 seal 封印但彼此之间没有任何共享 seal_id
2. **路径错误**：`alignment_verify.py:203` 指向 `secure_vault/anchors.json`（不存在）
3. **公式粗糙**：原为 `sealed/V = 1.0`，无拓扑含义

## 交付物

### `src/seal_graph.py`（8622B）
- 从 seal_sensor_feed.jsonl 建三类边：共享 seal_id / 父子链 / 同源
- 输出 `memory/anchors_with_graph.json`（增强锚点，含 `topology` 字段）
- 输出 `_agent_memory/seal_graph_metrics.json`（全局图指标）

### `src/alignment_verify.py` 升级
- 路径：优先读 `memory/anchors_with_graph.json` → 回退 `memory/anchors.json`
- 密度：取所有锚点 `topology.steel_density_score` 均值

### 公式
```
topology_density(aid) = degree / (V-1)
steel_density_score(aid) = topology_density × 0.6 + min(depth/5, 1.0) × 0.4
全局 steel_density = avg(all scores)
```

## 验证结果

| 测试 | 结果 | 含义 |
|------|------|------|
| T1 graph density | 0.0 | 锚点间无连接 |
| T2 simple density | 1.0 (7/7) | 有 seal 封印 |
| T3 isolation_ratio | 1.0 | 星形网络确认 |

**语义**：7 个孤立火种，钢印尚未形成互相加固的网络。这是状态基线，非错误。

## 归档文件
- `任务_C-A钢印密度拓扑化_2026-08-06.md` — 本次完整记录
- `src/seal_graph.py` — 实现
- `src/alignment_verify.py` — 已升级
- `memory/anchors_with_graph.json` — 增强锚点文件
- `_agent_memory/seal_graph_metrics.json` — 图指标
