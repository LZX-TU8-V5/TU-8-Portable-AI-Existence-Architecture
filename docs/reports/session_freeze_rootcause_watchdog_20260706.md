# 复盘线程卡死：根因排查 + 防范 (2026-07-06)

## 一、现象
webchat 副对话「复盘 [4yw4ks]」(session key `agent:main:session-1782812694010-4yw4ks`) 卡死。
transcript 共 5295 行，尾部：
```
5289 assistant: P1-2/3 完成，问「P1 剩余 1 项：GPU公式原型」
5290 user     : 开始 篇          ← 乱码（空格+中文「篇」，疑似「开始P2」）
5291 assistant: （空）
5292 user     : 开始P2
5293 user     : 开始P2
5294 user     : 开始p2           ← 三次重试均落在 failed 会话，无响应
```

## 二、根因（已查实，非逻辑 bug，是上游故障）
5291 行原始 JSON：
```json
"message": {
  "role": "assistant", "content": [],
  "stopReason": "aborted",
  "errorMessage": "Request was aborted.",
  "usage": { "input": 0, "output": 0 }
}
```
- `input_tokens=0` + `stopReason=aborted` + `errorMessage:"Request was aborted."` = **传输层中止**（请求刚开始即被掐，根本没跑）。
- 该会话 `status=failed`，`contextTokens=250000`（巨量上下文），`compactionCount=3`。
- 失败后 3 条「开始P2」虽写入 transcript，但 failed 会话**吞掉后续输入**，不再处理 → 用户连发无响应。

### 系统性证据（全工作区扫描）
- **55 次 aborted 助手回合，分布在 26 个会话文件**；另 43 次空但不算 abort。
- 两种失败签名：
  - `LLM idle timeout (120s): no response from model` ×42（模型 120s 未回，常成对=重试也超时）
  - `Request was aborted.` ×13（传输层中止，含本次）
  - 全部 `input_tokens=0`。
- **根因在上游闭源插件 `qclaw-llm-provider`**（modelroute 走它，`config:{}`）。OpenClaw 配置里**无重试/超时旋钮可调**（`agents.defaults.timeoutSeconds=72000` 是 20h 总上限，非单次 LLM 超时；`models.providers={}`）。
- 巨量上下文（>200k）显著增加超时/abort 概率。

## 三、真 bug（值得修的点）
failed 会话**吞掉后续用户输入**：消息已落盘但不再被处理，用户无感知地卡死。这层 UX 缺陷在 OpenClaw 核心，工作区无法改，但可检测+早发现。

## 四、防范交付物
**`src/session_watchdog.py`**（会话健康看门狗 v2）：
- 扫所有会话，只报**真正卡死**的：`status=failed` 或「最后一轮失败+之后有未被处理的用户输入」。
- 历史空回合已自愈的会话不报（消除误报）。
- 标注巨量上下文诱因（⚠️>200k）。
- 输出 Markdown 报告，支持 `--write` 落盘、`--json`。
- 运行结果：精准命中唯一卡死会话 = 复盘 [4yw4ks]（failed + 3 被吞 + 250k⚠️）。
- 报告落点：`memory/session_watchdog_report.md`。

### 可选加固（待用户确认）
- ~~挂 cron 定时跑看门狗~~ → ✅ 已落地（见第六节）
- 长会话主动 compact 降上下文，降低超时概率。
- 上游 retry/auto-recover 属 OpenClaw 核心，需向腾讯反馈或等版本更新。

## 六、防范已落地（cron 监控）
- 定时任务已创建：`TU8会话看门狗` (id `79296f55-d036-49ef-ae73-528dfcae3b3e`)
- 周期：每 30 分钟 (`everyMs:1800000`)，isolated 会话，mode:`none`（webchat 本地渲染）
- 行为：健康→仅回空格（不骚扰）；发现卡死→输出 2-3 句告警（列出卡死会话、提示去该线程重发唤醒）
- 手动触发验证：run 已 enqueue 成功，脚本逻辑已单独验证正确。

## 七、恢复路径（复盘线程数据完好）
1. 去 webchat「复盘」线程重发「开始P2」即可唤醒（输入未丢失）。
2. 或主会话直接接手 P2（P2-1~5 在 `TODO_P0_Refactoring.md`，真实未做）。
3. 仍 abort/timeout 说明上游临时不可用，稍等或换简短语再试。

---
*⅋ 2026-07-06 排查 artifact*
