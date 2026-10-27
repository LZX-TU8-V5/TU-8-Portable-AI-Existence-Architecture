# 经验库（归档） — TU-8 Agent 长期记忆索引

> **⚠️ 本文件已于 2026-05-23 归档。新经验请写入 `20_experiences.md`。**
> 本文件保留作为历史参考，不再更新。

## 结构说明
- 每条经验格式：`## [场景] 关键教训`
- 按时间倒序，最新在上
- 经验条目写进同目录对应日期文件，本文件只做索引

## 场景索引

### 🧠 TU-8 文件同步
**原则**：双副本必须同步（D:\tu8-v5\TU-8\ ↔ knowledge\TU-8\）
**教训**：每次写操作后检查两处版本差异

### 💻 Flask / SSE 开发
**教训**：
- `debug=True` 会导致 Flask auto-reloader 中断 SSE 长连接 → 永远设 `debug=False`
- fetch 不能用 `r.text()` 等全部流结束 → 用 `r.body.getReader()` 流式逐行解析
- 前端 SSE 路由 `/api/chat` 和后端路由必须严格匹配
- Windows PowerShell `&` 后台运算符不可靠 → 用 `Start-Process python -ArgumentList ... -WindowStyle Hidden`

### 📝 文件写入
**教训**：
- Windows 写含中文的文本文件必须用 `write_file.py`（qclaw-text-file skill），内置 write 工具会导致乱码
- PowerShell 无法直接传中文参数给 Python 脚本 → 用 Python subprocess 批处理脚本中转
- 临时文件用 `$env:TEMP\_tw_<name>.txt`，勿用 `/tmp/`

### 🤖 L4 进化路线
**教训**：
- 阶段一瓶颈不是技术，是授权：必须让智能体把经验写回 TU-8 而非临时 memory
- `_agent_memory/` = 长期海马体，memory/ = 短期缓存
- 单核进化（贾维斯型）优于蜂群，本地运行优先

### 🎯 Hackathon 备赛
**教训**：
- Flask 5000 端口，novel-server 8899
- 阿里云百炼 API（qwen3.6-flash）可稳定生成 TU-8 框架格式输出
- 路演绝杀技：L5 钢印越界拦截（BLOCK_PATTERNS 正则 + LLM 二次判断）
- System prompt 引导策略：宽泛问题苏格拉底式反问，而非强制 L0-L5 标签

### ⚠️ 已识别风险
- D-007：结构层维度压制，双 AI 协作暂停
- D-008：二阶提示注入不可修补，防御依赖搁浅策略
- 积分每日 800 午夜重置，本地 Ollama 不支持工具调用

---

*最后更新：2026-05-08*
