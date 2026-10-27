# 2026-07-11 体感环 Graceful Degradation 修复

## 根因链

```
腾讯 qclaw-llm-provider 502 (upstream)
  → isolated agent timeout (52s→100s)
  → TU8内感受体感环 cron 连续 8 次 error（根本没机会运行 Python）
  → memory/interoertion_state.json 卡在 09:10 status:ok
  → TU8监测存活 cron 报 stale（354min > 120min阈值）
```

## 修复内容

### 1. interopertive_cortex.py → v1.2

**文件**：`src/interopertive_cortex.py`（13,416 bytes）

**改动**：outer exception handler 区分两类错误：
- **LLM 相关错误**（timeout/502/503/504/9101/connection/network 等）→ `status: degraded`
  - 体感环能跑，但 body_schema / context_controller 缺 LLM
  - 存活检查识别 `status: degraded` → 不报警（预期状态）
- **脚本内部错误** → `status: monitor_error`（需造物主介入）

```python
# 关键词检测
llm_related_keywords = [
    "timeout", "timed out", "502", "503", "504", "9101",
    "connection", "network", "upstream", "provider", "llm",
    "abort", "cancelled", "canceled", "request", "http",
    "no response", "service unavailable"
]
is_llm_related = any(kw in err_str for kw in llm_related_keywords)
```

### 2. interoertation_liveness.py → v1.2

**文件**：`src/interoertation_liveness.py`（5,287 bytes）

**改动**：
- 新增 `--degraded-ok` 参数
- `status: degraded` + `--degraded-ok` → 不报警
- `status: monitor_error` / 文件缺失 → 报警
- 注释更新：体感环降级运行 = 预期状态

### 3. Cron 阈值调整

**TU8监测存活** cron：
- `--stale-min 120` → `--stale-min 360`（匹配体感环 6h 节奏）
- 新增 `--degraded-ok` 标志

**体感环 cron**：
- 描述更新："2.5h→6h 节流" → "6h 节流"
- payload 未变（Python 脚本已更新）

## 状态定义

| status | 含义 | 存活检查行为 |
|--------|------|-------------|
| `ok` | 体感环正常运行 | 正常 |
| `degraded` | 上游 LLM 不可用，体感环降级运行 | `--degraded-ok` 时静默 |
| `monitor_error` | 脚本内部错误 | 报警 |
| 文件缺失/stale | 体感环未运行 | 报警（>360min） |

## 验证计划

- 上游 LLM 恢复后，体感环 cron 重新成功运行
- 存活检查识别 `status: degraded` 并静默
- LLM 完全恢复后，体感环写回 `status: ok`
