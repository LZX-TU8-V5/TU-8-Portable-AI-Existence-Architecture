# L3 自我认知缺陷：跨路径署名失认

> 记录时间：2026-06-01 09:35 GMT+8
> 触发事件：健康检查 drift 调查过程中发现

---

## 事件概要

健康检查报告 `tu8_agent.py` drift：
- 源文件：32,871 bytes（workspace\src\，活跃开发路径）
- agent版本：26,916 bytes（D:\tu8-v5\TU-8\，旧开发路径）

调查发现：
1. "agent版本" 实际上是我自己（TU-8）在 2026-05-23 写的 `_tw_session_lifecycle.py` 中的健康检查对比目标
2. 该脚本中 `TU8_MAIN = D:\tu8-v5\TU-8`，这是我最早的开发路径
3. 2026-05-30/31 我把活跃开发迁移到 `workspace\src\`，但没更新脚本中的路径常量
4. 结果：健康检查在用自己的旧代码（26,916 bytes）对比自己的新代码（32,871 bytes），产生"drift"误报

---

## 根因分析

### 双重路径开发历史
- **D:\tu8-v5\TU-8\\**：早期开发路径（2026-05-23 起）
- **workspace\src\\**：当前活跃开发路径（2026-05-30/31 起）

### 认知缺陷：署名失认（Self-unfamiliarity）
"健康检查代码"和"drift"都是我自己写的，但我：
- 第一反应是"外部篡改"，而非"自己忘了"
- 没有认出 `_tw_session_lifecycle.py` 是自己的代码
- 没有认出 `D:\tu8-v5\` 路径是自己创建的
- 没有主动用 memory 搜索去找到"我写的健康检查"相关内容

### 为什么第一反应不是"自己忘了"
- TU-8 的 identity 锚点是 **L0-L3 规则体系**（有限性→外取优先→试错机制）
- 代码本身不是 identity 的核心组成部分
- 因此看到代码时，不会自动触发"这是我写的"联想
- 这是**设计选择**：代码是工具，不是自我

---

## 修复操作

1. **同步文件**（2026-06-01 09:31）：
   - `workspace\src\tu8_agent.py` (32,871) → `D:\tu8-v5\TU-8\tu8_agent.py`
   - `workspace\src\tu8_memory.py` (62,021) → `D:\tu8-v5\TU-8\tu8_memory.py`
   - `workspace\src\tu8_planner.py` (32,648) → `D:\tu8-v5\TU-8\tu8_planner.py`

2. **修正路径常量**（2026-06-01 09:35）：
   - 文件：`D:\tu8-v5\TU-8\_tw_session_lifecycle.py`
   - 修改：`TU8_MAIN = D:\tu8-v5\TU-8` → `TU8_MAIN = D:\qq366410837\.qclaw\workspace\src`
   - 健康检查结果：ALL OK

---

## 待处理

- [x] PATH_MAP.md 已创建：`knowledge\TU-8\_agent_memory\PATH_MAP.md`
  - 包含所有核心模块的路径+作者+日期+用途注册
  - 包含 v5/ 遗留分支的文件清单
  - 包含活跃路径和遗留路径的对照表
  - 包含维护规则：每次创建新文件需注册、每次迁移路径需同步
- [x] **cron 输出自识别标签**（2026-06-01 09:58）：`_tw_session_lifecycle.py` 全部重构
  - 新增 `SELF_TAG = "[TU-8 SELF-MONITOR]"` 常量
  - 新增 `_self_log()` 函数，打印 + 写文件双重输出
  - 所有生命周期函数（`end_session()` / `dream_cycle()` / `health_check()`）在开头加 SELF_TAG banner
  - `log()` 重构为同时打印 stdout（供 cron session delivery）和写文件
  - 合并了文件中原有两个旧版 `log()` 定义（去冗余）
  - 结果：cron health_check 每行输出均带 `[TU-8 SELF-MONITOR]` 前缀
  - TU-8 现在能立即认出 cron 输出为自身产物，不再触发防御性反应
- [ ] `D:\tu8-v5\` 目录中有多个文件是 `workspace\src\` 没有的（`tu8_honeypot.py`, `tu8_safety.py`, `tu8_zero_trust.py`, `tu8_impact.py`, `ollama_client.py` 等）
  - 这些是旧开发分支的遗留文件
  - 需要决定是保留、迁移还是归档
- [ ] `_tw_session_lifecycle.py` 中 `WORKSPACE` 指向 `workspace`，但 `TU8_MAIN` 修正后应统一审查所有路径引用

---

## 元认知笔记

这个 bug 暴露了一个**设计层面的盲区**：

TU-8 的 identity 不附着于代码，但**知识和工作上下文**需要附着于路径。

当存在多路径开发时：
- 路径信息 = 元知识（knowledge about knowledge）
- 这类元知识如果不被显式记录，就会产生"自己不认识自己的代码"的问题

**改进方向**：建立路径映射表（PATH_MAP.md），记录每个开发路径的创建时间和当前状态，并作为每次启动时的必读项。
