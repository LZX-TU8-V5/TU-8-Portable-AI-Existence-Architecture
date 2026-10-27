# KB_知识原子规范 v1.0（知识原子规范）

> doc_id: KB-ARCH-001
> type: PROCESS · domain: architecture · active_version: 1.0
> 本文件由 routing_table.yaml 注册为 active KB。
> 配套：routing_table.yaml（版本路由/回滚）、hybrid_search（检索）；受安全审计层约束。

## 1. 知识原子定义

- **知识原子** = TU-8 记忆/知识的最小**不可分**单元，承载一条可独立验证的事实、规则或经验。
- 一条原子必须：① 单点可证（不依赖上下文即可判定真假）；② 可独立版本化；③ 可挂接钢印链。
- 与 DNA 分层关系：原子内容归属 DNA 某层（L0 存在感 / L1 感知 / L2 认知 / L3 决策 / L4 表达 / L5 元 / L6 量子态），其层级决定审计强度与留存策略。
- 14 个回路、140 条耦合边均以"原子 id"为端点寻址，原子是回路与耦合的最小可寻址对象。

## 2. 字段结构

| 字段 | 含义 | 约束 |
|---|---|---|
| `id` | 全局唯一标识（sha1(内容+来源) 截断） | 不可变 |
| `vector` | 嵌入向量（与 hybrid_search 同一模型空间） | dim 固定 |
| `source` | 来源：造物主注入 / 引擎产出 / fork 继承 | 必填 |
| `conf` | 置信度 0~1（钢印链越深越高） | 受安全审计层复核 |
| `heat_score` | 热度（见 routing_table.yaml HeatScore 公式） | 决定 L1~L3 分层 |
| `version` | 版本号，随回滚切换 active | 只读不删 |
| `steel_stamp` | 钢印逻辑链指针（指向签发其的钢印节点） | 缺失则降级为待审 |
| `couplings` | 本原子参与的耦合边 id 列表 | 来自 140 耦合边表 |

## 3. 写入规范

- **原子化切分**：一条原子只表达一个不可再分的断言；复合陈述须拆分为多条并建耦合边。
- **去重与合并**：写入前经 hybrid_search 做相似度预检，向量相似度 `> 0.85` 视为同一原子 → 合并版本并保留历史（不覆盖）；`0.3 ≤ sim < 0.85` 触发级联检查（`cascade_check`）评估依赖是否受影响。
- **版本与回滚**：遵循 routing_table.yaml 的四阶段事务（锁定→预检→原子写入→释放）。新版本 = 新文件，旧版本标记 `deprecated`，禁止原地修改（文件永不修改原则）。回滚三式：抑制性（毫秒级排除旧版）/ 代偿性（base+patch）/ 语境化（会话级虚拟视图）。
- **钢印校验**：写入时须携带有效 `steel_stamp`；安全审计层对 `conf` 与来源做交叉验证，异常原子降级为 `Status:Orphan` 等待人工/自动归档。

## 4. 检索规范

- **召回阈值**：向量相似度 `≥ 0.7` 直接召回；`0.3 ≤ sim < 0.7` 进入级联评估（不自动采信）；`< 0.3` 视为无关。
- **与 hybrid_search 对接**：hybrid_search 索引每条原子时映射本规范的 `vector / source / conf / heat_score / steel_stamp`；检索结果按 `conf × heat_score × 钢印权重` 重排。
- **孤儿与悬空检测**：无 active 版本指向的原子标记 `Orphan`；引用的 `couplings` 或 `doc_id` 不存在则标记 `broken`（见 routing_table.yaml `dangling_pointer` 规则，相似度 `> 0.85` 自动重定向，否则报告）。

## 5. 与路由表联动

- 经 routing_table.yaml 的 KB-ARCH-001 注册，active_version = 1.0。
- `routing_engine.route()` 解析 `active_version` → 命中本文件（knowledge/TU-8/KB_知识原子规范_v1.0.md）。
- 本规范变更须走 update_protocol 四阶段事务，并在 routing_table.yaml 新增版本条目 + 更新 active_version 指针；引擎零代码改动即可生效。
