# Neural Benders论文精度修正→TU-8吸收

## 目标
将Neural Benders Decomposition (MIT CSAIL, ICLR 2026)论文详细解读中发现的精度修正写入TU-8文档。

## 核心修正

1. **SL→RL两阶段 → SL+RL双引擎并行**
   - 旧模型：SL(显式规则)阶段结束后进入RL(隐式优化)阶段——串行
   - 新模型：SL持续提供热启动基准+RL持续做实时修正——双引擎始终并行
   - 论文证据：SL(模仿者)利用专家数据提供Warm Start，RL(修正者)同时微调决策弥补SL泛化不足，收敛加速30-50%

2. **可行性保证**
   - Neural Benders核心发现：纯ML无法保证解的可行性
   - TU-8映射：纯L3代理决策器无法保证L0合规判断
   - L0-A1校验不是"偶尔复查"/"质量抽检"，而是**保证可行性的必要条件**

## 执行结果

| 文件 | 版本 | 修改内容 |
|------|------|---------|
| **L2_方法论** | v1.8→v1.9 | SL→RL两阶段→SL+RL双引擎并行，转化机制→双引擎协同机制，与Benders对应表更新为Neural Benders精确版 |
| **L3_架构** | v1.8→v1.9 | 新增"可行性保证"章节，代理可信度表后补充可行性保证论述+对照表 |

## 论文引用
Neural Benders Decomposition: Learning to Optimize via Reinforcement and Supervision, MIT CSAIL, ICLR 2026
