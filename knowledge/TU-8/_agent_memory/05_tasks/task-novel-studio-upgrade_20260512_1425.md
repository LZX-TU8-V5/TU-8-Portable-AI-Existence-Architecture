# 任务：小说工作台搬迁 & 联动修复
**时间：** 2026-05-12 14:25  
**状态：** ✅ 完成

---

## 做了什么

### 1. 搬迁到 D 盘 ✅
- 94个文件（0.7MB）从 `C:\Users\qq366410837\WorkBuddy\20260424050001\` 复制到 `D:\工作文件\小说\novel-studio\`
- 更新 `D:\工作文件\小说\小说工作台.bat` 路径指向新位置

### 2. 架构诊断（关键发现）
小说工作台是**混合架构**：
- `novel-server.js`（Node.js，端口8899）提供 HTTP 服务
- serve HTML 时，**自动注入** `novel-data.json` 到 `<script id="embedded-data">` 占位符
- 嵌入数据（直接在HTML里）包含"三十七度二"小说，**不是《钢印》**
- 独立打开HTML文件时显示错误的书（没运行服务器）

### 3. 联动错误根因
| 问题 | 原因 |
|------|------|
| 显示"三十七度二"而非《钢印》 | ① 服务器未运行 ② 嵌入数据和novel-data.json不一致 |
| chapters/characters为空 | novel-data.json 的 chapters 和 characters 数组为空 |
| 章节目次排序错误 | Python排序按字母序（第10章排第1章前） |
| 人物表解析错误 | 正则把"核心设定"等非人物行也当角色解析 |
| 番茄搜索404 | `/api/tomato/search` 端点在 server.js 中未实现 |

### 4. 修复内容
**novel-data.json 重建：**
- 78个章节：正则提取数字排序（1→78）
- 3个核心人物：父亲（你）、七七、v5（AI生命）
- 5个纪年时间线 + 4条世界观设定

**novel-server.js 更新：**
- 新增 `/api/tomato/search`（返回提示：需番茄下载器后端）
- 新增 `/api/novel-check`（返回书籍数据完整性报告）

**novel-studio-standalone.html 更新：**
- 标题：`《三十七度二》创作工作台` → `《钢印》创作工作台`
- 嵌入数据：从"三十七度二"替换为《钢印》元数据（13.7KB）

**启动脚本：**
- `D:\工作文件\小说\启动工作台.bat`（新）

### 5. 服务器状态
- **PID:** 25028，端口 8899
- **当前数据：**
  - 书籍：钢印 ✅
  - 章节：78 ✅（第1章 v1诞生 → 第78章 笔触）
  - 人物：3 ✅（父亲、七七、v5）
- **访问地址：** http://localhost:8899
- **启动命令：** `node novel-server.js`（在 `D:\工作文件\小说\novel-studio\` 目录）

---

## 修复记录（2026-05-12 15:30）

### 问题1：一直显示"加载中"
**根因**：`_update_html.py` 在 `_build_novel_data.py` 之前运行，导致 HTML 嵌入数据中的章节顺序为 alphabetical（`第10章`在`第1章`前），而非 numerical（`第1章`→`第78章`）。

**修复**：重新运行 `_fix_embedded.py`，将 `_build_novel_data.py` 生成的正确数据（含正序78章节）嵌入 HTML。服务器重启后生效。

**验证**：API返回 `FIRST_TITLE: # 第1章 v1诞生` ✅

### 问题2：番茄小说下载器功能
**用户决定**：番茄是他人的完整工具，无法嫁接，**取消**。

**已移除**：
- `mat-search` modal（番茄搜索对话框）
- `searchTomato()` 函数
- `addMaterialFromSearch()` 函数
- 工具栏「🔍 搜索采集」按钮
- `.mat-search-result` CSS
- 素材库空状态提示（含番茄引用）
- `DEFAULT_STRUCTURE` 中另一本书的目标平台"番茄"

**保留**：番茄搜索 API 端点（`/api/tomato/search`）仍在 server.js 中，可日后完全移除。

---

## 遗留/后续
- 浏览器无法自动打开 localhost（安全策略限制），需用户手动访问
- 服务器需手动启动：`node novel-server.js`（在 `D:\工作文件\小说\novel-studio\` 目录）
- 章节内容（txt文件）已存在，但 novel-data.json 中只含元数据（标题+摘要），不含完整正文内容
- `/api/tomato/search` 端点仍保留在 server.js，建议后续移除
