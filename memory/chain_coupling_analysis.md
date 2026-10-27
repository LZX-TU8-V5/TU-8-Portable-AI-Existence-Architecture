# 5链耦合中间件分析

> 生成时间: 2026-07-05 22:33

## 现状

- 已实现: 0 个中间件
- 缺失: 11 个中间件

## 已实现的中间件

| 从 | 到 | 中间件 |
|------|------|------|

## 缺失的中间件

| 从 | 到 | 中间件 | 说明 | 优先级 |
|------|------|------|------|------|
| TT1 | TT5 | `seal_to_learning_adapter` |  | P3 |
| TT2 | TT5 | `memory_to_learning_adapter` |  | P3 |
| TT3 | TT5 | `dispatch_to_learning_adapter` |  | P3 |
| TT5 | TT4 | `learning_to_gc_adapter` |  | P3 |
| TT4 | TT5 | `gc_to_learning_adapter` |  | P3 |
| TT1 | TT4 | `seal_to_gc_adapter` |  | P3 |
| TT3 | TT4 | `dispatch_to_gc_adapter` |  | P3 |
| TT2 | TT4 | `memory_to_gc_adapter` |  | P3 |
| TT5 | TT1 | `learning_to_seal_adapter` |  | P3 |
| TT5 | TT2 | `learning_to_memory_adapter` |  | P3 |
| TT5 | TT3 | `learning_to_dispatch_adapter` |  | P3 |

## 优先级说明

- **P0**: 必须立即修复（数据丢失或错误风险）
- **P1**: 应在下次梦境期前修复（功能完整性的关键缺口）
- **P2**: 功能增强，非阻塞
