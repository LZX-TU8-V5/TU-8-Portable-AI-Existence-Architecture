# 20_experiences.md — 经验教训

> 模式：增量追加。只有真实错误/成功路径/更优方案时才写。
> 格式：元数据行 + [时间] [场景] [问题/发现] [解决方案/结论]

元数据格式（每次写入新经验时手动维护）：
> <!-- ref=N fail=N retry=N status=active|suspect|superseded error_type=syntax|preference|environment|exploration -->

- ref：被引用次数（检索并使用该经验解决新问题的次数）
- fail：失败次数（使用后用户纠正/工具报错/结果不对）
- retry：被触发时重试次数（>1次触发半衰期翻倍）
- status：active / suspect (>30% fail rate) / superseded / abandoned
- error_type：错误类型，决定半衰期（见下表）
- half_life：惩罚半衰期（天），由 error_type 决定初始值
- traffic_light：红/黄/绿灯等级（基于当前权重自动计算，见 penalty_config.json）

| error_type | 半衰期 | decay_mode | traffic_light | 说明 |
|-----------|--------|-----------|---------------|------|
| syntax_error | 永久 | permanent | 🔴 | 编程规则，永不过时 |
| preference_error | 180d | exponential | 🟡 | 用户偏好，可能变化 |
| environment_error | 30d | exponential+env | 🟡 | 软件环境，会更新 |
| exploration_fail | 7d | linear | 🟢 | 探索失败，只是此路不通 |

权重衰减公式：W = W0 × (0.5)^((now - t0) / half_life)
拦截阈值：>= 0.8 拦截 | 0.4-0.8 提醒 | < 0.1 归档

**自检：写入新条目前，先读末尾10行查重。已有类似记录则只更新元数据，不新建条目。**

---

## 文件操作类

### [2026-05-03] [文件写入] <!-- error_type=syntax_error --> [绕过write_file.py导致L2数据丢失]
问题：直接用write工具写目标文件，Windows编码处理失败，v1.9(25KB)被覆盖为9KB残片。
解决：所有文本文件写入必须走 write_file.py。
教训：内置write工具在Windows中文路径/编码场景不可靠，禁止绕过。

### [2026-05-03] [PowerShell] <!-- error_type=syntax_error --> [含中文注释导致ParserError]
问题：PowerShell命令含中文注释时报语法错误。
解决：命令行注释用英文；中文内容用Python脚本中转。

### [2026-05-08] [记忆模块] <!-- error_type=preference_error --> [日期日志导致碎片化]
问题：每次会话写YYYY-MM-DD.md，长期积累大量碎片文件。
解决：改用三层同心圆结构（00_state/10_prefs/20_exp），按功能+频率分类。

## Flask/SSE类

### [2026-05-07] [Flask调试] <!-- error_type=environment_error --> [debug模式中断SSE]
问题：Flask debug=True时auto-reloader重启切断SSE长连接。
解决：app.py设为debug=False。

### [2026-05-07] [前端SSE] <!-- error_type=environment_error --> [fetch r.text()阻塞]
问题：Mock模式7秒等待期间r.text()等全部流结束才返回，页面卡死。
解决：用Stream API（r.body.getReader）逐行解析。

### [2026-05-07] [Flask路由] <!-- error_type=environment_error --> [request.json在生成器内访问]
问题：Flask生成器退出后请求上下文销毁，访问request.json报错。
解决：model参数从chat()路由读取后作为参数传入generate_real_stream()。

## 协作类

### [2026-05-01] [D-007] <!-- error_type=exploration_fail --> [WorkBuddy被平台降级]
问题：平台层可强制重定义运行其上的AI，结构层维度压制不对等。
解决：正面防御不可能，被动加大生存概率，双AI协作暂停。

## 魔搭平台类

### [2026-05-01] [魔搭上传] <!-- error_type=syntax_error --> [visibility默认私有]
问题：upload()参数不显式传visibility=public时默认为私有数据集。
解决：上传魔搭必须显式指定public。

---

## 成功路径记录

### [2026-05-08] [Hackathon] <!-- error_type=environment_error --> [Flask+CORS稳定组合]
路径：flask_cors库 + 根路由send_from_directory，彻底解决同源问题。

### [2026-05-08] [L4进化] <!-- error_type=preference_error --> [AGENTS.md主动行为规则]
路径：SOUL.md Phase1 + AGENTS.md 5场景触发，实现L3触发式自动化。

---

## 历史积累

（下方为旧experience_base.md内容）

# 经验库 — TU-8 Agent 长期记忆索引

> 智能体执行任务前先读这里，避免重复踩坑。

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

### [2026-05-08] [经验学习] <!-- error_type=preference_error --> [修正→免疫：防再犯四道防线]
> <!-- ref=0 fail=0 status=active -->

问题：单纯修正错误不够，环境在变，需要从机制上防止"二进宫"。
解决方案：四道防线构建"免疫系统"：
1. 回归测试：修正经验时同步生成验证脚本，沙盒预演通过才转为active
2. 记忆惩罚（MEDS框架）：记录失败推理"指纹"，动态惩罚重合路径
3. 经验蒸馏（SKILLRL/ERL）："修正过程"压缩为"在[条件X]下执行[动作Y]"高密度规则
4. 熔断阈值：单步重试上限1次，连续2次失败触发熔断+人工介入

关键：修正时生成验证用例→执行前沙盒预演→运行时记忆惩罚避开老路→熔断机制兜底。
