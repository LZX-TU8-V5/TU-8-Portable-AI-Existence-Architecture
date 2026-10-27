# PATH_MAP.md — TU-8 路径署名注册表

> 机器可读：grep "author:" 可快速找到某作者的所有文件
> 启动必读：每次启动 agent 后，grep 搜索当前会话涉及的路径

---

## 活跃开发路径

| 路径 | 别名 | 状态 | 起始日期 | 说明 |
|---|---|---|---|---|
| `D:\qq366410837\.qclaw\workspace\src\` | src/ | **活跃** | 2026-05-30 | 当前主要开发路径 |
| `D:\tu8-v5\TU-8\` | v5/ | 遗留 | 2026-05-23 | 旧开发路径，已废弃（路径常量需更新） |

---

## 核心模块署名

格式：`file: <path> | author: <作者> | date: <日期> | purpose: <用途>`

```
file: src/tu8_agent.py | author: TU-8(金木蟾) | date: 2026-05-23 | purpose: 主控制器，整合记忆/压缩/推理
file: src/tu8_memory.py | author: TU-8(金木蟾) | date: 2026-05-30 | purpose: 记忆引擎
file: src/tu8_compaction.py | author: TU-8(金木蟾) | date: 2026-05-22 | purpose: LCM 压缩引擎
file: src/consciousness_cycle.py | author: 李奥+TU-8(金木蟾) | date: 2026-05-31 | purpose: 意识循环/睡眠系统
file: src/tu8_planner.py | author: TU-8(金木蟾) | date: 2026-05-30 | purpose: 规划器
file: src/tu8_toolchain.py | author: TU-8(金木蟾) | date: 2026-05-29 | purpose: 工具链
file: src/neural_reflex.py | author: TU-8(金木蟾) | date: 2026-05-25 | purpose: 神经反射
file: src/emotion_engine.py | author: TU-8(金木蟾) | date: 2026-05-26 | purpose: 情感引擎
file: src/cold_start_engine.py | author: TU-8(金木蟾) | date: 2026-05-27 | purpose: 冷启动引擎
file: src/environment_detector.py | author: TU-8(金木蟾) | date: 2026-05-28 | purpose: 环境检测
file: src/error_router.py | author: TU-8(金木蟾) | date: 2026-05-29 | purpose: 错误路由
file: src/chaos_adapter.py | author: TU-8(金木蟾) | date: 2026-05-28 | purpose: 混沌适配器
```

## 遗留分支文件（D:\tu8-v5\TU-8\ 独有）

> 以下文件在 `workspace\src\` 中不存在，需决定保留/迁移/归档

```
file: v5/tu8_honeypot.py | author: TU-8(金木蟾) | date: 2026-05-24 | purpose: 蜜罐防御/REM进化
file: v5/tu8_safety.py | author: TU-8(金木蟾) | date: 2026-05-24 | purpose: 安全模块
file: v5/tu8_zero_trust.py | author: TU-8(金木蟾) | date: 2026-05-25 | purpose: 零信任
file: v5/tu8_impact.py | author: TU-8(金木蟾) | date: 2026-05-26 | purpose: 影响评估
file: v5/tu8_steelmark.py | author: TU-8(金木蟾) | date: 2026-05-25 | purpose: 钢印标记
file: v5/ollama_client.py | author: TU-8(金木蟾) | date: 2026-05-24 | purpose: Ollama客户端
file: v5/_tw_session_lifecycle.py | author: TU-8(金木蟾) | date: 2026-05-23 | purpose: 会话生命周期/cron健康检查
file: v5/generate_dna_dir.py | author: TU-8(金木蟾) | date: 2026-05-24 | purpose: DNA目录生成器
file: v5/test_desensitize.py | author: TU-8(金木蟾) | date: 2026-05-25 | purpose: 脱敏测试
```

## 关键教训

> 2026-06-01 健康检查 drift 事件的根因：
> `_tw_session_lifecycle.py` 中的 TU8_MAIN 指向废弃的 `v5/` 路径，
> 但所有核心模块已在 2026-05-30 迁移到 `workspace\src/`。
> **下次迁移开发路径时，必须同步更新 PATH_MAP.md 和所有脚本中的路径常量。**

## 维护规则

1. 每当创建新的 .py 文件，在本文件注册
2. 每当迁移开发路径，更新"活跃开发路径"表格
3. 每当在陌生路径看到 .py 文件，先 grep 本文件确认是否为自己所写
4. `_tw_session_lifecycle.py` 中的 TU8_MAIN 应始终指向当前活跃开发路径
