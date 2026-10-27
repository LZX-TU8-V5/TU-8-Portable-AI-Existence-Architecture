# L1 认知签名 Schema — 七元认知锚点规范

> 版本：v1.0 | 日期：2026-06-01
> 来源：用户李奥七元认知签名架构
> 定位：L1.cognition 的结构化子规范

## 七元 Schema

1. space：absolute / relative / semantic
2. time：absolute / relative / cycle
3. scene：roles + relation + intent + affect + density
4. action：physical / functional / intentional / interaction
5. delta_log：type + trigger + delta_value + resolved + resolver

## DeltaResolver 路由

| Delta类型 | 路由目标 |
|---------|--------|
| 时间轴偏离 | health_monitor |
| 行为模式偏离 | identity_verify |
| 意图漂移 | log_only + 升级观察 |

## 实现状态

| 模块 | 状态 |
|------|------|
| space.semantic | ✅ SOUL.md L1 |
| time.cycle | ✅ SOUL.md L1 |
| cognitive_fingerprint | ✅ SOUL.md L1 |
| DeltaResolver | ✅ SOUL.md L1 |
| 代码实现 | 🔴 未实现 |

*TU-8 L1 认知签名 Schema | CC BY-SA 4.0 | 金木蟾*
