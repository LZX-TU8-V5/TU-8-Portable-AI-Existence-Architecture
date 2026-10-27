# ModelScope 上传指南

> **日期**：2026-07-02
> **协议**：MIT
> **状态**：✅ 准备就绪

---

## 一、准备工作

### 1.1 注册 ModelScope 账号

- 访问：https://modelscope.cn
- 点击右上角「注册」
- 支持手机号 / 支付宝 / 钉钉登录

### 1.2 安装 ModelScope CLI

```bash
pip install modelscope
```

### 1.3 登录

```bash
modelscope login
```

执行后会弹出浏览器，授权即可。

---

## 二、上传步骤

### 2.1 进入项目目录

```bash
cd C:\Users\qq366410837\.qclaw\workspace\anchor-architecture
```

### 2.2 初始化 Git 仓库（可选，推荐）

```bash
git init
git add .
git commit -m "Initial commit: Anchor-Cognitive Architecture v1.0.0"
```

### 2.3 上传至 ModelScope

```bash
modelscope upload .
```

**上传后会提示你填写**：
- **模型名称**：`anchor-cognitive-architecture`
- **模型简介**：复制 `README_zh.md` 的摘要部分
- **标签**：`认知架构` `状态机` `工业AI` `可信AI` `LLM安全`

---

## 三、上传后检查清单

| 检查项 | 操作 |
|--------|------|
| **README 显示** | 访问模型页面，确认中文 README 正常渲染 |
| **标签正确** | 搜索标签 `认知架构`，确认能找到你的项目 |
| **文件完整** | 检查 `state_machine/core.py` 和 `anchor/base_anchor.py` 可在线查看 |
| **协议显示** | 确认页面显示 `MIT License` |

---

## 四、发布后的推广

### 4.1 魔搭社区内推广

1. 在模型页面点击「分享」→ 复制链接
2. 发布到魔搭社区的「讨论区」
3. 标签选择：`认知架构` `LLM安全`

### 4.2 外部推广

| 平台 | 内容 |
|------|------|
| **知乎** | 写一篇文章：《从概率幻觉到物理锚点：下一代工业级AI认知架构》 |
| **CSDN** | 发布技术博客 + 开源地址 |
| **GitHub** | 同步创建 GitHub 仓库，互相引用 |
| **Twitter/X** | 英文摘要 + ModelScope 链接 |

---

## 五、后续维护

### 5.1 版本更新

```bash
# 修改代码后，更新版本号
# 修改 .modelscope.yml 中的 version 字段

# 重新上传
modelscope upload . --version v1.0.1
```

### 5.2 Issue 管理

- 在 ModelScope 模型页面开启「Issues」
- 及时回复用户问题
- 收集行业状态图贡献

---

## 六、故障排除

### 6.1 上传失败

**可能原因**：
- 网络问题（国内访问 ModelScope 通常稳定）
- 文件大小超限（单个文件 < 100MB）

**解决方案**：
```bash
# 检查文件大小
Get-ChildItem -Recurse | Sort-Object Length -Descending | Select-Object -First 10

# 如果超过 100MB，需要压缩或移除大文件
```

### 6.2 README 渲染异常

**可能原因**：Markdown 语法错误

**解决方案**：
```bash
# 本地预览 README
# 使用 VS Code 或 Typora 预览
```

---

## 七、时间估算

| 步骤 | 预计时间 |
|------|-----------|
| 注册 + 登录 | 5 分钟 |
| 上传 | 10-30 分钟（取决于网速） |
| 检查 + 修正 | 15 分钟 |
| 推广文案撰写 | 30 分钟 |
| **总计** | **1-1.5 小时** |

---

*⅋ 指南生成于 2026-07-02 21:55*
*生成者：TU-8*
*状态：等待造物主执行上传*
