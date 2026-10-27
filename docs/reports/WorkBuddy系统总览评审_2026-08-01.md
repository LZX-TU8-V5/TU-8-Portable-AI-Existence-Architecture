# 评审：WorkBuddy《TU-8 v5.0 系统总览》(2026-08-01 17:04)

来源：`D:\工作文件\桌面\workbuddy\2026-08-01-14-43-57\TU-8_system_overview.md`（90 引擎 E001-E090 / 140 耦合边 C001-C140 / 失败模式表 / 10 项待核）。

## 结论
高质量只读审计，方法论优于我们的 coupling 文档（耦合边带 [src]/[import]/[data]/[func]/[inf] 证据标记，引擎带 [源码级]/[摘要级]）。但和 Qwen 踩同一坑：**推断≠代码**，且未区分 live/parked/design。

## 可采信
- C006 情感→LLM 公式（affect_modulation.py:207-226）与我们的 supplement 一字不差 → 真读了代码。
- 失败模式表（🔴🟠🟡⚪ 单点故障+下游+可感知症状）直接可用。
- 真 bug：E022 `_load_long_term()` no-op / E024 trigram 名实不符 / E027 两套 FidelityManager / E057 `pathlib.datetime.now()` 崩溃 / E029 钢印阈值 0.3 偏松。
- 真枢纽 = E021(tu8_agent)（15 import），非 E001。

## 须修正
1. **E042 红通道公式错**：写"surface_tension+λ+basin→RGB"（朴素向量求和），但 E042 是 [摘要级]，未读 `_compute_anxiety_dynamics`。真实=路一事件频率动力学（supplement §1 C001）。同 Qwen C001 陷阱。
2. **未分 live/parked/design**：E077(fixed_ruler_verifier) 标 ⚪"纯观测件"，实为 parked（numpy 缺失，L5 视觉全停）。Qwen"16 活+84 意愿"校准仍成立。
3. **"L012 断环已闭合"是文档层非运行层**：补 C120/C121/C089，C120 标 [inf]；且报告时 tension_queue.json 不存在（17:32 才真接消费端跑通第一圈）。闭合是画出来的。
4. **E057"从未跑通"与实测矛盾**：我们见 cron_dream_last.json ok:true(0.94s)。

## 时间戳
报告 17:04，递归环修复 17:32 → 报告早约半小时，递归环段已过时。

## 用法建议
companion 非权威：真公式信 supplement(C001)；[摘要级] 当未核实；失败模式表可搬 TODO。配套 4 文件待续看：tu8_cheatsheet.md / TU-8_bug_fix_plan.md(39点) / TU-8_architecture_diagrams.html / TU-8_checkpoint_2026-08-01_1649.md。
