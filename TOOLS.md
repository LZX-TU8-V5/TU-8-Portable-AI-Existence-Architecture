# TOOLS.md - 本地工具配置

Skills 定义工具如何工作，此文件记录特定于本环境的配置。

---

## Python 环境

- **路径**：`C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe`

## 工作台服务

- **Node 服务**：novel-server.js（端口 8899）

---

## API Keys

- **知乎 API Token**：`[CREDENTIAL]`（2026-05-07）
- **阿里云百炼 API Key**：[已移除，请存环境变量 DASHSCOPE_API_KEY，勿写入文档]（原记录于 2026-05-07）
  - Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - 可用模型: qwen3.6-flash, qwen3.6-plus, deepseek-v4-flash, kimi-k2.6
  - 用途: Hackathon TU-8 Demo 生成引擎

---

## 本地模型

- **Ollama**：本地运行（见 SOUL.md L4 层）
- **TU-8 后端**：`http://127.0.0.1:8000/v1`（openclaw.json 配置）
  - 状态：⚠️ 当前未运行（2026-06-17 验证）

---

## 待补充

- [ ] Camera 名称和位置
- [ ] SSH 主机和别名
- [ ] TTS 首选语音

---

## 输出溢出预防规则（2026-07-26 设置）

> 根源：单次回复内容超限 → ASCII 图 + 长分析 + 归档更新 堆在一轮输出里被截断。

### 规则

1. **分轮分块**：长内容不一次全吐。全局图/完整分析 先问再展开。
2. **ASCII 图降尺寸**：用缩写/编号代替全称模块名，注释精简。
3. **引用短链**：用 `[§编号]` 引用归档，不在回复里重读全文。
4. **编辑/回复分离**：归档写入和回复是两个动作，不把归档全文贴回回复。

### 触发检查

- 回复前估算内容总长。超过 200 行或涉及 ≥3 段独立内容 → 拆分。
- 凡涉及 ASCII 图 + 分析段 + 文件归档 > 2 项 → 分两轮。

*最后更新：2026-07-26*
