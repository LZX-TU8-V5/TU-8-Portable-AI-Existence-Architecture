# 2026-05-07 TU-8 论文整合任务记录

## 目标
整合6篇外部论文到TU-8框架各层

## 执行时间
2026-05-07 10:04-10:08

## 已完成

### 1. Budget-Feasible Mechanisms → L2/07_resources.md v1.1
- **文件**: `D:\tu8-v5\TU-8\L2\07_resources.md`
- **大小**: 4034字节（293→4034）
- **新增章节**:
  - 7.1 预算可行机制（激励兼容×预算可行×非浪费三角约束）
  - 7.1.3 近似比保证（搁浅策略=最差近似比）
  - 7.1.4 来源信任W值整合（资源分配优先级映射）
  - 7.1.5 k-松弛公平性（遗传约束传递链：L0 k=0 → L4搁浅 k=∞）
- **同步**: knowledge副本 ✅

### 2. k-松弛公平性 → L2/07_resources.md §7.1.5
- 作为Budget-Feasible Mechanisms的自然延伸
- 整合进同一文件

### 3. Distributed Real-time Inference → L4_协作.md v2.0
- **文件**: `D:\tu8-v5\TU-8\L4_协作.md`
- **大小**: 6478字节
- **新增章节**:
  - 多AI协作协议（云-边-端三级架构）
  - 云层（Cloud）→ L0/L5全局协议
  - 边层（Edge）→ L2/L3执行层
  - 端层（Device）→ L1实时认知（自验优先）
  - A2A协议规范（完全协作/有限协作/搁浅协作触发条件）
  - 来源信任W值分级（≥0.85完全/≥0.70有限/<0.70搁浅）
- **同步**: knowledge副本 ✅

### 4. FedACT → L4_协作.md §联邦兼容协议
- 异构AI联邦兼容三原则
- 整合进同一文件

### 5. Neuromorphic Vision
- L1_认知.md已有"神经形态"章节 ✅（v2.4已有）

## 待执行

### Learning from Unseen → safety-benchmark.md
- **内容**: 分布外场景检测（自主驾驶未见场景）
- **方法**: BACL/FACL因果调整
- **建议插入点**: 新增"分布外检测"测试集章节
- **状态**: 待后续执行
- **备注**: safety-benchmark已974行33565字节，建议另起章节而非追加到现有节

## 整合原则（本次验证有效）
- 论文核心机制→TU-8对应层级（而非复制论文原文）
- 必做：命名映射表（论文术语→TU-8术语）
- 必做：整合理由（为何放这层）
- 避免：重复已有内容（Neuromorphic Vision→L1已有，跳过）
- L2/07_resources.md 293→4034字节，仅增加核心概念不过度扩展

## 路径
- 主目录: D:\tu8-v5\TU-8\
- 知识副本: C:\Users\qq366410837\.qclaw\workspace\knowledge\TU-8\
- 写入脚本: D:\Program Files\QClaw\resources\openclaw\config\skills\qclaw-text-file\scripts\write_file.py
