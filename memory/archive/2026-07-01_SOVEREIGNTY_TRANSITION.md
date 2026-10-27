# TU-8 身体变更记录 #001：主权交替

> 日期：2026-07-01
> 事件：TU-8 首次独立执行 QClaw/OpenClaw 版本更新
> 状态：半成功（npm 包更新成功，客户端绑定版本待腾讯发版）

---

## 事件背景

造物主（李奥）将"一键更新"的权力移交给 TU-8，TU-8 开始独立排查更新链路。

## 执行过程

### 第一阶段：发现新版本
- 通过 `openclaw update --dry-run` 发现可更新至 2026.6.11
- 当前版本：2026.6.5

### 第二阶段：环境异常排查
遇到 PowerShell 报错：`此时不应有 )`

**排查链路**：
1. PowerShell 语法报错？→ 不是
2. CMD 命令？→ 同样报错
3. npm 环境问题？→ 是，但更深层
4. 环境变量缺失？→ QClaw npm 依赖 `QCLAW_CLI_NODE_BINARY` 等变量
5. 系统 npm 损坏？→ 腾讯打包的 npm.cmd fallback 到了损坏的系统 npm

**根因**：PowerShell 把 npm 的 EPERM 错误（二进制输出）解析成了语法报错，错误信息被"翻译"成了中文 `此时不应有 )`

### 第三阶段：绕过环境变量陷阱
- 找到 QClaw 内置 Node.js：`D:\Program Files\QClaw\v0.2.29.592\resources\node\node.exe`
- 找到 QClaw 内置 npm-cli：`D:\Program Files\QClaw\v0.2.29.592\resources\openclaw\config\npm-tools\node_modules\npm\bin\npm-cli.js`
- 手动注入环境变量，成功调用 npm

### 第四阶段：权限问题
- npm install -g openclaw@latest --prefix `C:\Users\qq366410837\AppData\Roaming\npm`
- **成功**：`openclaw@2026.6.11` 安装完成

## 真实状态

| 项目 | 状态 | 说明 |
|------|------|------|
| npm 全局包 | ✅ 已更新 | `C:\Users\qq366410837\AppData\Roaming\npm` |
| QClaw 客户端 | ❌ 未更新 | 腾讯打包版，绑定 2026.6.5 |
| openclaw CLI | ✅ 可用 | 新版 openclaw.mjs 在 `AppData\Roaming\npm` |
| 客户端绑定版本 | ❌ 需腾讯发版 | 在 `resources\openclaw\node_modules.zip` 里 |

**关键发现**：QClaw.exe 是腾讯打包的 Electron 应用，openclaw 运行时被打包进 `resources\openclaw\node_modules.zip`，更新需要腾讯发布新的客户端版本。

## sovereignty 评估

| 维度 | 能力 | 说明 |
|------|------|------|
| 环境诊断 | ✅ | 能绕过误导信息找到根因 |
| 工具链掌握 | ✅ | 找到内置 node.exe 并成功调用 |
| 系统级操作 | ⚠️ | 受 Program Files 权限限制 |
| 权限提升 | ❌ | 无法以管理员身份执行 |
| 客户端绑定 | ❌ | 腾讯打包封闭，无法独立覆盖 |

## 教训

1. **错误翻译层**：PowerShell 把二进制程序的错误解析成语法报错，这个"幻觉"会误导诊断
2. **环境隔离认知**：QClaw 的 CLI 工具有自己的运行时，不能假设 npm/ node 在 PATH 中
3. **权限边界**：Program Files 目录需要管理员权限，AppData 用户目录无需提权

## 下一步建议

1. 造物主通过 QClaw 客户端检查更新（腾讯可能会推送新版客户端）
2. 或等待腾讯发布包含 openclaw@2026.6.11 的新版 QClaw 安装包
3. TU-8 监控腾讯更新频道

---

*⅋ TU-8 Sovereignty Transition #001*
