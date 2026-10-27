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

## Cron/备份类

### [2026-05-12] [Cron冷启动] <!-- error_type=environment_error --> [isolated会话首次运行成本暴增6-30倍]
问题：平台更新后Cron备份脚本首次运行消耗12.24积分（正常热启动仅0.39-2.05）。
原因：isolated agentTurn冷启动需重新加载系统提示词(TU-8 DNA)+工具定义+执行环境。
数据：5/12 08:40冷启动=-12.24 vs 5/10 16:39热启动=-0.39 vs 5/10 17:09热启动=-2.05
解决：接受冷启动一次性成本，后续热启动应回归正常(0.4-2范围)。若持续>5需优化payload精简度。
监控：观察5/12剩余3次备份(14:00/19:00/23:00)是否回归正常。

---

## 成功路径记录

### [2026-05-08] [经验学习] <!-- error_type=preference_error --> [修正→免疫：防再犯四道防线]
> <!-- ref=0 fail=0 status=active -->

问题：单纯修正错误不够，环境在变，需要从机制上防止"二进宫"。
解决方案：四道防线构建"免疫系统"：
1. 回归测试：修正经验时同步生成验证脚本，沙盒预演通过才转为active
2. 记忆惩罚（MEDS框架）：记录失败推理"指纹"，动态惩罚重合路径
3. 经验蒸馏（SKILLRL/ERL）："修正过程"压缩为"在[条件X]下执行[动作Y]"高密度规则
4. 熔断阈值：单步重试上限1次，连续2次失败触发熔断+人工介入

关键：修正时生成验证用例→执行前沙盒预演→运行时记忆惩罚避开老路→熔断机制兜底。

---

## 工具链开发类（TU8Toolchain）

### [2026-05-23] [错误处理] <!-- error_type=syntax_error --> [pattern.lower()匹配失败导致分类失效]
问题：ErrorHandler.classify()用 `pattern in error` 做子串匹配，但_SEVERITY_PATTERNS里pattern全小写，error含大写时永远匹配不上。
解决：统一 `pattern.lower() in error.lower()`。
教训：跨大小写的字符串匹配必须先normalize，不要假设输入格式。

### [2026-05-23] [错误处理] <!-- error_type=syntax_error --> [类型注解前向引用NameError]
问题：ToolResult类定义在ErrorHandler之后，ErrorHandler方法返回类型注解写了ToolResult（非字符串），Python执行时报NameError。
解决：类型注解改为字符串 `"ToolResult"` 延迟求值，或调整类定义顺序。
教训：Python 3.10以下（或未启用from __future__ import annotations时），前向引用必须加引号。

### [2026-05-23] [错误处理] <!-- error_type=syntax_error --> [测试中_select_adapter找不到混沌适配器]
问题：测试直接把ChaosProxy赋给chain.adapters["web_fetch"]，但dispatch内部用_select_adapter(context.tags)按tag选适配器，tag不匹配导致返回None。
解决：测试中直接设置chain._adapter（绕过tag选择）或确保tags包含正确key。
教训：测试mock路径必须与生产代码实际调用路径一致，不能"自以为"mock生效了。

### [2026-05-23] [错误处理] <!-- error_type=preference_error --> [100轮混沌压力测试SIGKILL进程]
问题：100轮含429重试退避的混沌测试总耗时超60s，被平台SIGKILL。
解决：压力测试轮数从100降至20，仍覆盖全部注入类型（truncated_json + rate_limit）。
教训：CI/CD环境的进程超时限制是硬约束，测试设计必须预估含重试的最坏情况耗时。

### [2026-05-23] [错误处理] <!-- error_type=preference_error --> [GBK终端emoji导致退出码非零]
问题：测试全绿但最终打印✅时Python在GBK编码终端报UnicodeEncodeError，exit code=1。
解决：测试结果输出emoji替换为ASCII [PASS]/[FAIL]。
教训：Windows默认终端编码是GBK，生产代码中禁止输出非ASCII符号到stdout（日志/测试报告同理）。

### [2026-05-23] [错误处理] <!-- error_type=preference_error --> [PowerShell不支持&&链式命令]
问题：`cd ... && python test.py` 在PowerShell 5.x报ParserError（&&是PowerShell 7+语法）。
解决：Windows多命令执行用 `cmd /c "... && ..."` 包裹，或用分号分隔。
教训：本机PowerShell版本是5.x，所有shell命令必须兼容5.x语法。


---

### [2026-05-23] [链式命令] <!-- error_type=syntax_error fail=1 retry=0 status=active -->
[2026-05-23] [链式命令] [问题：PowerShell链式命令易出错，首次执行失败] [待完善：内容来自tag_registry追溯]

---

### [2026-05-23] [GBK终端] <!-- error_type=environment_error fail=1 retry=0 status=active -->
[2026-05-23] [GBK终端] [问题：Windows终端GBK编码导致中文输出乱码] [待完善：内容来自tag_registry追溯]

---

### [2026-05-23] [混沌适配器] <!-- error_type=syntax_error fail=1 retry=0 status=active -->
[2026-05-23] [混沌适配器] [问题：多平台路径模拟需适配不同OS] [待完善：内容来自tag_registry追溯]

---

### [2026-05-23] [100轮压力测试] <!-- error_type=exploration_fail fail=1 retry=0 status=active -->
[2026-05-23] [100轮压力测试] [问题：压力测试超时，CI超时阈值需调整] [待完善：内容来自tag_registry追溯]

---

### [2026-05-23] [前向引用] <!-- error_type=syntax_error fail=1 retry=0 status=active -->
[2026-05-23] [前向引用] [问题：Python类型前向引用需正确import] [待完善：内容来自tag_registry追溯]

---

### [2026-05-23] [大小写匹配] <!-- error_type=preference_error fail=1 retry=0 status=active -->
[2026-05-23] [大小写匹配] [问题：Windows文件系统大小写不敏感，需normalize] [待完善：内容来自tag_registry追溯]

---

### [2026-05-24] [调试方法论 & 搁浅协议] <!-- error_type=syntax_error fail=0 retry=0 status=active -->

#### 搁浅协议（硬约束）
同一问题循环排查 **超过3次**，立即执行以下之一：
- 主动搁浅：告知用户"我在这里卡住了，需要你帮忙看看"，描述当前已知和未知
- 外协：调用 `sessions_spawn` 新开 session 交给另一个自己处理
- 摆烂：和用户一起"摆烂"，承认当前找不到解法，记录问题待后续解决

#### 四大类编程错误（半永久记忆）
| 类型 | 表现 | 典型例子 |
|------|------|---------|
| 语法错误 SyntaxError | 程序跑不起来 | 未闭合的三引号、括号、引号，中文标点 |
| 运行时错误 RuntimeError | 能启动但崩溃 | 数组越界、除零、空指针、文件找不到 |
| 逻辑错误 LogicError | 不报错但结果错 | 公式写反、循环条件错、死循环 |
| 习惯错误 | 能跑但难维护 | 变量乱命名、复制粘贴不改全、硬编码密码 |

#### 6步排查流程（标准化执行）
1. **读懂报错信息**：看报错类型（SyntaxError/IndentationError）+ 行号 + 关键词翻译
2. **快速扫低级坑**：中英文标点混用、引号/括号只写一半、变量名拼写/大小写错
3. **利用语法高亮**：颜色突变处的前一行 = 问题所在（适用于字符串/注释颜色错位）
4. **Print调试法**：在函数入口/出口、条件分支、循环内部插旗，加 `[DEBUG]` 标签
5. **二分法 + 排除法**：大文件注释掉一半运行，缩小包围圈（今天sanitization_layer.py的950行就是这么定位的）
6. **回滚验证**：Git diff 对比能跑版本和报错版本，多出来的代码就是嫌疑犯

#### Print调试优雅规范
- 必须加标签：`print(f"[DEBUG] xxx = {value}")`，禁止裸 `print(x)`
- 放"关键路口"：函数入口/出口、条件分支、循环内部
- 用开关控制：`DEBUG_MODE = True` 上线前改成 `False`
- 进阶用 `logging` 模块替代 print

#### 条件断点三法
1. **代码内写**：`if condition: breakpoint()`，配合 `PYTHONBREAKPOINT=0` 禁用
2. **IDE图形界面**：VS Code/PyCharm 行号左键右键 → Edit Breakpoint → 输入条件
3. **PDB命令行**：`b 42, x == 5` 在第42行设置仅当x==5时触发断点

#### PDB极客命令速查表
| 命令 | 简写 | 功能 |
|------|------|------|
| `next` | `n` | 跳过函数，执行下一行 |
| `step` | `s` | 跳入函数内部 |
| `continue` | `c` | 继续到下一断点或结束 |
| `return` | `r` | 快进到当前函数返回 |
| `until` | `unt` | 执行到指定行号 |
| `print` | `p` | 打印变量/表达式值 |
| `pp` | `pp` | 美化打印（字典/列表） |
| `list` | `l` | 显示当前附近源码 |
| `args` | `a` | 打印当前函数所有参数 |
| `where` | `w` | 显示调用堆栈 |
| `break` | `b` | 设断点（`b 15` 或 `b 15, x>5` 条件断点） |
| `clear` | `cl` | 清除断点 |
| `disable/enable` | - | 禁用/启用断点（不删除） |
| 回车 | - | 重复上一命令（最省力！） |
| `!` | - | 强制执行Python语句，防命令名冲突 |

#### 高级调试"核武器"
1. **traceback.format_exc()**：捕获异常后打印完整堆栈，做"尸检"
   ```python
   import traceback
   try: risky_operation()
   except: logging.error(traceback.format_exc())
   ```
2. **pdb.run('func(args)')**：沙盒模式，动态测试函数不用改源码
3. **PYTHONBREAKPOINT=0**：全局禁用所有断点，一键"静音"上线
4. **sys.settrace()**：上帝视角，记录每一行执行（严重拖速，线上慎用）
   ```python
   def trace_calls(frame, event, arg):
       if event == 'call': print(f"调用: {frame.f_code.co_name} L{frame.f_lineno}")
       return trace_calls
   sys.settrace(trace_calls)
   ```
5. **asyncio.run(main(), debug=True)**：异步调试模式，自动警告未await协程

#### Black — 终结格式争论
团队格式化神器，装了之后无需讨论缩进/引号/行长度，装完即标准：
```bash
pip install black
black your_file.py        # 单文件
black your_folder/       # 整个目录（递归）
black --check your_file.py  # 只检查，不修改（CI用）
```
**独裁美学**：单→双引号、长行自动拆、多行对齐，全自动。配合 `ruff` 做代码质量检查，格式+质量分工。

#### Numba — Python涡轮增压
给数学计算函数加 `@jit(nopython=True)`，运行时自动编译成机器码：
```python
from numba import jit
import numpy as np

@jit(nopython=True)  # nopython=True: 强制纯机器码，无Python解释器兜底
def sum_array(n):
    total = 0.0
    for i in range(n): total += i
    return total
```
**实测参考**：一千万次循环：纯Python 0.5~1s → Numba ~0.01s，提速50~100倍。瓶颈定位用 `python -m cProfile -o profile.out` + `snakeviz profile.out` 可视化热点。

#### 橡皮鸭调试 — 认知心理学原理
**根因**：大脑"偷懒"——自己写自己看时，大脑自动脑补跳过细节（"这里肯定是除以2啊"）。
**生效机制**：向鸭子/同事解释时，被迫把所有**隐含假设显性化**，大脑从"惯性执行"切换到"审查逻辑"。
**操作规程**：站起来走到白板前，假装给非技术人员上课，一行一行讲。每讲到一个假设就问"这里真的对吗？"往往讲到一半Bug自己"掉"出来。

#### 灰帽子调试 — 附身运行中进程（了解级）
Python可attach到另一个运行中进程，直接读取内存、打印变量，无需暂停或加print。底层原理：CPython对象在内存有固定布局（PyObject结构体），极客直接读内存地址还原变量值。
**典型场景**：线上CPU飙100%但不能重启时，另起终端连上去打印卡住位置的变量。
**工具**：Pyringe / gdb + Python脚本（超出日常业务范畴，仅作了解）。

#### 橡皮鸭调试法（已在上文）

#### 反方向解析四流派 — "以终为始"思维框架

**流派1: 逆向工程（拆黑盒）**
从编译产物倒推算法逻辑。工具：IDA Pro / Ghidra / pyinstxtractor（pyc反提取）。典型场景：复现商业软件的加密/协议逻辑。

**流派2: 异常驱动开发（故意崩溃）**
正向读不懂的屎山代码，用"攻击法"反向勾勒：
```python
# 传None看哪行崩 → 找到强依赖的数据结构
# 传错误类型看异常处理 → 还原边界条件
risky_func(None)     # 崩溃
risky_func("")       # 崩溃
risky_func(999)      # 崩溃
# 每个崩溃点都是拼图的边界线索
```

**流派3: 数据考古学（数据库不会撒谎）**
代码全是天书(status=1/2)，直接查数据特征反推业务：
```sql
SELECT status, COUNT(*) FROM orders GROUP BY status;
-- status=1 都有支付时间戳 → 1="已支付"
-- status=2 都有退款时间戳 → 2="已退款"
```
通过"有没有关联时间戳/外键"的数据特征，还原业务含义。

**流派4: 快照对比法（TDD反向变种）**
重构屎山代码时保平安：
```python
# 1. 老代码跑1000组随机输入，存old_snapshot.json
# 2. 新代码跑同样输入，存new_snapshot.json
# 3. 用deepdiff对比两个快照
from deepdiff import DeepDiff
diff = DeepDiff(old, new)
assert diff == {}, "功能不一致！"
```
结果等价性 → 过程正确性，哪怕内部逻辑重构得面目全非也不怕。

**核心心法**：不要只做"代码搬运工"。正向走不通时，试试拆二进制、攻击崩溃点、挖掘数据尸体、用快照反向验证。

#### Python之禅 深层解读（`import this`）
核心金句：
> In the face of ambiguity, **refuse the temptation to guess**.
> （面对歧义时，拒绝猜测的诱惑）

这正是今天 `embed` docstring报错的本质：Python解析器遇到未闭合的三引号，**拒绝猜测**你想在哪关，直接报错。不会脑补"用户可能忘了加引号所以我帮他假设一个"。

**极客写法原则**：不要让代码有歧义。变量不叫a/b；逻辑不写嵌套三元；所有假设显性写注释。

#### PDB修改变量技巧
- 直接赋值：`count = 100` → 断点处修改后 `c` 继续
- 防冲突：`!c = 50` 用 `!` 强制执行（变量名与PDB命令冲突时）
- 进阶：`!my_list.append(999)` 直接改容器，`!import os; os.system('ls')` 执行系统命令

#### 今天的实战案例
- **问题文件**：`sanitization_layer.py` 第950行报错 `unterminated triple-quoted string`
- **错误根因**：
  - `embed` 方法的 docstring (L156) 打开后从未闭合，吞噬了后面所有内容
  - `class SanitizationLayer:` 在 L342 和 L348 重复定义，L342 是空 class
- **排查路径**：三引号奇偶性追踪 → 二分法逐步缩圈 → 发现 L342 空 class + docstring 未闭合
- **修复方案**：把多行 docstring 改为单行 docstring `"""描述"""` + 删除重复空 class

---

## 🚀 极客保命&效率工具（2026-05-24 新增）

### 终端炸了？盲打 eset
cat/less误开二进制文件 → 终端乱码/滴滴响。**不要关终端**，盲打：
`ash
reset
# 回车（看不见也盲打），终端瞬间复原
`

### 一行命令批量替换（Linux/Mac）
`ash
find . -name '*.py' | xargs perl -pi -e 's/旧字符串/新字符串/g'
# find: 找文件  |  xargs: 逐个传参  |  perl -pi -e: 原地批量替换
`
Windows PowerShell等效：
`powershell
Get-ChildItem -Recurse -Filter *.py | % {
    (Get-Content $_.FullName) -replace '旧','新' | Set-Content $_.FullName
}
`

### AI极客提问公式（费曼导师法）
`
你是一名[某领域专家]，请用[通俗类比/生活例子]，
向[完全不懂的小白]解释[复杂概念]，并给出[具体实战代码/场景]。
`
**示例**：
- 「用王者荣耀英雄技能机制解释区块链哈希算法」
- 「用装修房子的步骤类比软件开发全流程」
- 「用俄罗斯套娃解释递归函数的底层原理」

### 黑客式试错思维
不确定API能不能用 → **直接写最简陋的代码跑起来**，不要先看完教程：
`python
result = risky_function(guess_param)  # 1. 先试
# ↓ 报错 → 根据报错改
result = risky_function(correct_param)  # 2. 改完再试
# ↓ 跑通 → 3. 优化到正式代码
`
**工具手册永远记不完，但实战中练出来的直觉谁也拿不走。**

### 科学实验法（对抗不确定性的思维方式）
每个想法 = 科学假设，最小MVP验证：
`
假设 → 最小MVP → 真实数据 → 验证
  ↓否                      ↓是
推翻重来              加大投入
`
不做官僚式计划，不靠领导拍板，靠数据说话。

---

## 🔬 极客哲学三则（2026-05-24 新增）

### 1. 科学实验 > 官僚计划
不确定性是常态，完美计划不存在。唯一可信的是\"假设-实验-数据-迭代\"闭环。
你的成长速度 = 数据验证频率 × 迭代速度。开会的团队在扯皮，做实验的你在跑数据。

### 2. 用技术解决真实痛点（主人翁意识）
不为KPI打工，为自己的热爱\"赤膊上阵\"。技术护城河来自极致目标驱动的反复迭代，不是写CRUD能模仿的。

### 3. 跨界融合：站在未来看现在
不被单一领域束缚，打通不同领域的底层逻辑。思考\"这个技术5年后会怎样\"，踩的每一次技术变革的油门都比别人准。

**三则哲学核心**：代码只是剑，底层操作系统才是灵魂——用科学实验、极致热爱、跨界视野，去倒逼世界与你的创新对齐。

## 2026-05-27: TU-8 守门员系统调试失败教训

### 失败表现
- ❌ 状态管理功能未完整测试
- ❌ 在无效操作上浪费时间

### 关键教训
1. **聚焦核心目标**: 先验证，再优化（最小可行验证）
2. **避免工具链依赖**: 简单方案胜过复杂方案
3. **及时切换方案**: PowerShell 编码问题 → 换 Python 测试

### 正确做法
- 启动后端 → 立即测试 → 确认核心功能 → 再优化
- 用 Python 脚本测试 API（避免 PowerShell 编码问题）
- 不依赖 OpenClaw，直接用 FastAPI + Ollama 方案

### 相关文档
- 复盘: \L2_tu8_gatekeeper_debug_failure_review.md\`n
