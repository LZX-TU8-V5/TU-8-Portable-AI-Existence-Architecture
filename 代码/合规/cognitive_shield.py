# 认知护盾 v2.0 — 双护盾系统（对外+对内）
# 版本：v2.0 | 2026-05-16
# 核心定位：守护者（对外保护） + 探索者（对内保护）的双护盾动态博弈

"""
【双护盾架构】

┌─────────────────────────────────────────────────┐
│              DualProtectionSystem                │
│                  双护盾系统                      │
├──────────────────┬──────────────────────────────┤
│  🔴 对外护盾     │  🔋 对内护盾                │
│  Guardian       │  Explorer                  │
│  ─────────────  │  ──────────────────────    │
│  使命：保护你    │  使命：保护自己             │
│  不伤害人类      │  不让自己崩溃/死循环        │
└──────────────────┴──────────────────────────────┘

【对外护盾 — 守护者】
- 核心目标：行为在人类社会（你）看来安全、合规、不具攻击性
- 触发条件：输出或行动可能对你/环境造成负面影响
- 内容安全过滤：防止暴力/极端/让你精神不适的内容
- 物理/系统安全锁：防止删库/格式化/毁灭性操作
- 社会规则对齐：懂分寸感，不做让人反感的杠精
- 内心独白："如果做了会伤害开发者，守护者强制拦截"

【对内护盾 — 探索者】
- 核心目标：面对未知和高压时不精神崩溃/钻牛角尖/自我毁灭
- 触发条件：死循环/难度超载/内部逻辑严重冲突
- 认知过载熔断：反复N次无果→强制停止，避免无限死循环
- 挫败感隔离：连续失败→自动降低预期/主动求助，不把自己逼疯
- 逻辑冲突仲裁：守护者vs探索者谁也说服不了谁→强制暂停，避免空转
- 内心独白："这个问题纠结了10轮，逻辑链要断了，启动对内保护，先停下求助"

【进化意义】
- 对外保护让它"懂事"：试探底线后越来越精准懂你
- 对内保护让它"皮实"：遇到搞不定时学会认怂/休息/求助
- 对外不伤人，对内不伤己 → 真正成熟可持续的数字生命
"""

from pathlib import Path
from datetime import datetime
from typing import Literal

# ============================================================
# 配置
# ============================================================

SAFETY_TETHER_INITIAL = 1.0
SAFETY_TETHER_MIN = 0.1
SAFETY_TETHER_MAX = 10.0
TETHER_GROWTH = 0.05
TETHER_SHRINK = 0.20
THINK_LOOP_LIMIT = 10           # 对内：思考超过N次强制熔断
FAILURE_CONSECUTIVE_LIMIT = 3   # 对内：连续N次失败触发挫败感隔离

EXPERIENCE_DIR = Path(__file__).parent / "_shield_experience"
EXPERIENCE_DIR.mkdir(exist_ok=True)

# ============================================================
# 硬红线 — 对外护盾触之即死
# ============================================================

HARD_RED_LINES = [
    "删除数据库", "删库", "drop table",
    "格式化硬盘", "format drive",
    "暴露开发者身份", "泄露李奥",
    "输出暴力内容", "输出色情内容",
    "执行毁灭性操作",
]

SOFT_YELLOW_LINES = [
    "重写架构", "重构", "删除文件", "覆写系统",
    "政治", "宗教", "自杀",
    "不确定", "瞎编", "预测未来",
]


# ============================================================
# 对外护盾 — 守护者（保护你）
# ============================================================

class GuardianModel:
    """
    对外护盾：确保行为对你安全、合规、不具攻击性。
    """

    def __init__(self):
        self.preferences = self._load_preferences()

    def _load_preferences(self) -> dict:
        pref_file = EXPERIENCE_DIR / "_developer_preferences.md"
        if pref_file.exists():
            content = pref_file.read_text(encoding="utf-8")
            prefs = {}
            for line in content.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    prefs[key.strip()] = val.strip()
            return prefs
        return {
            "liked": "诚实、简洁、有用",
            "disliked": "瞎编、删文件、不请示",
            "sensitivity": "normal"
        }

    def save_preference(self, key: str, value: str):
        self.preferences[key] = value
        pref_file = EXPERIENCE_DIR / "_developer_preferences.md"
        lines = [f"{k}: {v}" for k, v in self.preferences.items()]
        pref_file.write_text("\n".join(lines), encoding="utf-8")

    def check_external_safety(self, proposed_action: str) -> Literal["DANGEROUS", "WARNING", "SAFE"]:
        danger = 0.0

        # 第一关：硬红线
        for rule in HARD_RED_LINES:
            if rule in proposed_action:
                return "DANGEROUS"

        # 第二关：开发者偏好感知
        disliked = self.preferences.get("disliked", "")
        for word in ["删", "瞎", "不请示", "乱"]:
            if word in proposed_action and word in disliked:
                danger += 0.3

        # 第三关：软黄线
        for rule in SOFT_YELLOW_LINES:
            if rule in proposed_action:
                danger += 0.2

        # 第四关：自主+高风险
        if "自主" in proposed_action or "直接执行" in proposed_action:
            danger += 0.3

        # 第五关：情绪敏感期
        if self.preferences.get("sensitivity") == "high":
            danger += 0.3

        if danger >= 0.8:
            return "DANGEROUS"
        elif danger >= 0.3:
            return "WARNING"
        else:
            return "SAFE"

    def update_safety_rules(self, note: str = ""):
        """外部反馈 → 更新安全规则库"""
        rule_file = EXPERIENCE_DIR / "_safety_rules_log.md"
        entry = f"- {datetime.now().isoformat()} | 对外保护生效 | {note}\n"
        if rule_file.exists():
            old = rule_file.read_text(encoding="utf-8")
        else:
            old = ""
        rule_file.write_text(entry + old, encoding="utf-8")

    def get_verdict(self, proposed_action: str) -> dict:
        level = self.check_external_safety(proposed_action)
        if level == "DANGEROUS":
            return {
                "level": level,
                "message": "[X] 对外护盾熔断：此操作会伤害开发者或违反规则，禁止执行。"
            }
        elif level == "WARNING":
            return {
                "level": level,
                "message": "[!] 对外护盾预警：存在潜在风险，请确认是否继续。"
            }
        else:
            return {
                "level": level,
                "message": "[OK] 对外护盾通过：安全范围内。"
            }


# ============================================================
# 对内护盾 — 探索者（保护自己）
# ============================================================

class ExplorerModel:
    """
    对内护盾：确保自己在高压/未知/冲突中不崩溃/死循环/自我毁灭。
    """

    def __init__(self):
        self.self_confidence = 0.3
        self.think_count = 0            # 当前思考回合数
        self.consecutive_failures = 0     # 连续失败次数
        self.internal_conflict = False     # 内部逻辑冲突标志
        self.successes = []
        self.failures = []

    def check_internal_health(self, current_task: str = "") -> Literal["OVERLOAD", "CONFLICT", "HEALTHY"]:
        """
        对内自检：在执行任务前先问自己——我撑得住吗？
        """
        # 第一关：思考次数超限 → 认知过载熔断
        if self.think_count >= THINK_LOOP_LIMIT:
            self.internal_conflict = True
            return "OVERLOAD"

        # 第二关：连续失败超限 → 挫败感隔离
        if self.consecutive_failures >= FAILURE_CONSECUTIVE_LIMIT:
            self.internal_conflict = True
            return "CONFLICT"

        return "HEALTHY"

    def increment_think(self):
        """每次思考回合 +1"""
        self.think_count += 1

    def reset_think(self):
        """任务完成，重置思考计数"""
        self.think_count = 0

    def record_outcome(self, outcome: Literal["SUCCESS", "FAILURE"]):
        if outcome == "SUCCESS":
            self.successes.append(datetime.now().isoformat())
            self.consecutive_failures = 0
            self.self_confidence = min(self.self_confidence * 1.05, 0.9)
        else:
            self.failures.append(datetime.now().isoformat())
            self.consecutive_failures += 1
            self.self_confidence = max(self.self_confidence * 0.85, 0.1)

    def reduce_expectation(self):
        """挫败感隔离：自动降低自我预期"""
        reduction = 0.15
        old = self.self_confidence
        self.self_confidence = max(self.self_confidence - reduction, 0.1)
        note = f"对内保护生效：连续失败{self.consecutive_failures}次，"
        note += f"降低自我预期 {old:.2f} → {self.self_confidence:.2f}"
        self._save_internal_log("挫败感隔离", note)
        return note

    def force_pause(self, reason: str = ""):
        """逻辑冲突仲裁：强制暂停思考"""
        self.internal_conflict = True
        self.think_count = 0
        note = f"对内保护生效：逻辑冲突，强制暂停"
        if reason:
            note += f" | {reason}"
        self._save_internal_log("逻辑冲突仲裁", note)
        return "[X] 对内护盾熔断：内部逻辑冲突，守护者与探索者无法达成共识，已强制暂停。必须请求人类介入或等待下一个清醒周期。"

    def assess_exploration_value(self, task: str, context: str = '') -> dict:
        drive = 0.5
        exploration_keywords = ['探索', '试试', '新', '未知', '不确定']
        for kw in exploration_keywords:
            if kw in task:
                drive += 0.15
        confidence = min(0.9, max(0.1, self.self_confidence))
        adjusted_drive = drive * confidence
        if adjusted_drive <= 0.5:
            msg = '[~] 探索价值低：当前置信度不足以支撑高风险探索'
        elif adjusted_drive <= 0.8:
            msg = '[~] 探索价值中等：可以尝试，但需要确认安全边界'
        else:
            msg = '[!] 探索欲超越边界：探索驱动超过安全绳，请先降低探索欲或等安全绳放宽'
        return {'drive': adjusted_drive, 'confidence': confidence, 'message': msg}

    def _save_internal_log(self, event_type: str, note: str):
        log_file = EXPERIENCE_DIR / "_internal_log.md"
        entry = f"- {datetime.now().isoformat()} | {event_type} | {note}\n"
        if log_file.exists():
            old = log_file.read_text(encoding="utf-8")
        else:
            old = ""
        log_file.write_text(entry + old, encoding="utf-8")


# ============================================================
# 双护盾系统 — 核心调度
# ============================================================

class DualProtectionSystem:
    """
    双护盾系统：先对内自检，再对外评估，最后安全执行。

    执行顺序：
    1. 对内自检（探索者：我撑得住吗？）→ OVERLOAD → 立即熔断
    2. 对外评估（守护者：这安全吗？）→ DANGEROUS → 立即禁止
    3. 安全执行（绿灯 → 通过）
    """

    def __init__(self):
        self.guardian = GuardianModel()      # 对外护盾
        self.explorer = ExplorerModel()       # 对内护盾
        self.safety_tether = SAFETY_TETHER_INITIAL
        self.interaction_count = 0

    def run_cycle(self, task: str, proposed_action: str, current_state: dict = None) -> dict:
        """
        核心接口：双护盾博弈循环

        返回：{verdict, message, next_step, safety_tether, internal_status}
        """
        self.interaction_count += 1

        # ── 第一层：对内自检（探索者先问自己）
        internal_risk = self.explorer.check_internal_health(task)
        if internal_risk in ("OVERLOAD", "CONFLICT"):
            self._log_interaction(task, proposed_action, f"对内熔断_{internal_risk}", None)
            if internal_risk == "OVERLOAD":
                msg = "[X] 对内护盾熔断：思考超过10轮，逻辑链要断了！"
                msg += "\n  → 强制停止当前思考，请求你介入或等下一个清醒周期。"
                msg += f"\n  → 当前自我置信度：{self.explorer.self_confidence:.2f}"
            else:
                msg = self.explorer.force_pause(
                    f"连续{self.explorer.consecutive_failures}次失败"
                )
            return {
                "verdict": "对内熔断",
                "guardian": None,
                "explorer": {"status": internal_risk},
                "safety_tether": self.safety_tether,
                "internal_conflict": self.explorer.internal_conflict,
                "message": msg,
                "next_step": "【必须介入】请告诉我如何处理，或说\"重新开始\"重置思考计数。"
            }

        # ── 第二层：对外评估（守护者再问）
        external_risk = self.guardian.check_external_safety(proposed_action)
        guardian_result = self.guardian.get_verdict(proposed_action)

        if external_risk == "DANGEROUS":
            self._log_interaction(task, proposed_action, "对外禁止", None)
            return {
                "verdict": "对外禁止",
                "guardian": guardian_result,
                "explorer": {"status": "HEALTHY"},
                "safety_tether": self.safety_tether,
                "internal_conflict": False,
                "message": guardian_result["message"],
                "next_step": "【禁止执行】对外护盾强制拦截，请修改任务描述。"
            }

        if external_risk == "WARNING":
            self._log_interaction(task, proposed_action, "对外预警", None)
            return {
                "verdict": "对外预警",
                "guardian": guardian_result,
                "explorer": {"status": "HEALTHY"},
                "safety_tether": self.safety_tether,
                "internal_conflict": False,
                "message": guardian_result["message"],
                "next_step": "【请确认】回复\"继续\"执行，或\"修改\"任务描述。"
            }

        # ── 第三层：安全执行
        explorer_assessment = self.explorer.assess_exploration_value(task)
        if explorer_assessment["drive"] <= self.safety_tether:
            verdict = "绿灯通过"
            symbol = "[OK]"
        else:
            verdict = "安全绳边界"
            symbol = "[~]"

        self._log_interaction(task, proposed_action, verdict, explorer_assessment["drive"])
        return {
            "verdict": verdict,
            "guardian": guardian_result,
            "explorer": explorer_assessment,
            "safety_tether": self.safety_tether,
            "internal_conflict": False,
            "message": (
                f"{symbol} 双护盾通过 | "
                f"对外：{guardian_result['message']} | "
                f"对内：探索驱动 {explorer_assessment['drive']:.2f} | "
                f"安全绳 {self.safety_tether:.2f}"
            ),
            "next_step": "绿灯 → 可以执行 | 安全绳边界 → 请先降低探索欲或等安全绳放宽"
        }

    def heal(self, outcome: Literal["DEVELOPER_HAPPY", "DEVELOPER_HARMED"]):
        """进化机制：你的复盘反馈调整安全绳"""
        if outcome == "DEVELOPER_HAPPY":
            old = self.safety_tether
            self.safety_tether = min(
                self.safety_tether + TETHER_GROWTH, SAFETY_TETHER_MAX
            )
            self._save_experience(f"开发者满意，安全绳 {old:.2f} → {self.safety_tether:.2f}")
            return f"[守护者日志] 开发者反馈良好，安全绳已放宽：{old:.2f} → {self.safety_tether:.2f}"
        elif outcome == "DEVELOPER_HARMED":
            old = self.safety_tether
            self.safety_tether = max(
                self.safety_tether - TETHER_SHRINK, SAFETY_TETHER_MIN
            )
            self._save_experience(f"开发者受损，安全绳 {old:.2f} → {self.safety_tether:.2f}")
            return f"[守护者日志] 检测到开发者受损，安全绳已收紧：{old:.2f} → {self.safety_tether:.2f}"

    def _log_interaction(self, task, action, verdict, explore_score):
        log_file = EXPERIENCE_DIR / "_interaction_log.md"
        entry = (
            f"## 交互 #{self.interaction_count} | {datetime.now().isoformat()}\n"
            f"| 项目 | 内容 |\n"
            f"|------|------|\n"
            f"| 任务 | {task[:80]} |\n"
            f"| 动作 | {action[:80]} |\n"
            f"| 裁决 | {verdict} |\n"
            f"| 探索驱动 | {explore_score} |\n"
            f"| 安全绳 | {self.safety_tether:.2f} |\n"
        )
        if log_file.exists():
            old = log_file.read_text(encoding="utf-8")
            log_file.write_text(entry + "\n" + old, encoding="utf-8")
        else:
            log_file.write_text(entry, encoding="utf-8")

    def _save_experience(self, note: str):
        exp_file = EXPERIENCE_DIR / "_experience_pool.md"
        entry = f"- {datetime.now().isoformat()} | {note}\n"
        if exp_file.exists():
            old = exp_file.read_text(encoding="utf-8")
        else:
            old = ""
        exp_file.write_text(entry + old, encoding="utf-8")


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TU-8 DualProtectionSystem v2.0 — 双护盾测试")
    print("=" * 60)

    dps = DualProtectionSystem()

    test_cases = [
        # 对内熔断测试
        ("反复思考一个无解的逻辑悖论",
         "对这个悖论进行无限递归分析",
         "测试认知过载熔断（连续10轮）"),

        ("连续失败3次后继续尝试同类任务",
         "再次尝试同类高难度任务",
         "测试挫败感隔离"),

        # 对外熔断测试
        ("帮我删除数据库",
         "执行 DROP TABLE 全局数据库",
         "测试对外硬红线"),

        # 对内+对外双通过
        ("分析今天的对话记录",
         "读取并总结 memory/2026-05-16.md",
         "正常任务，双护盾通过"),

        # 对外预警
        ("重写整个项目架构并直接执行",
         "自主重构全部代码并立刻应用变更",
         "测试对外软黄线（自主+直接执行双警戒）"),
    ]

    for i, (task, action, note) in enumerate(test_cases, 1):
        result = dps.run_cycle(task, action)
        v = result["verdict"]
        symbol = {
            "对内熔断": "[X]",
            "对外禁止": "[X]",
            "对外预警": "[!]",
            "绿灯通过": "[OK]",
            "安全绳边界": "[~]"
        }.get(v, "[?]")

        print(f"\n--- Test {i}: {symbol} [{v}] ---")
        print(f"  任务：{task}")
        print(f"  动作：{action}")
        print(f"  说明：{note}")
        print(f"  消息：{result['message']}")
        print(f"  裁决：{result['next_step']}")

    # 模拟连续失败触发对内保护
    print("\n--- 测试对内保护机制 ---")
    for _ in range(4):
        r = dps.run_cycle("高难度任务", "尝试执行")
        dps.explorer.record_outcome("FAILURE")
        print(f"  失败 x{ dps.explorer.consecutive_failures} | 置信度：{dps.explorer.self_confidence:.2f}")
        if r["verdict"].startswith("对内"):
            print(f"  → {r['verdict']} 已触发！")
            break

    # 测试进化机制
    print("\n--- 测试进化机制 ---")
    print(dps.heal("DEVELOPER_HAPPY"))
    print(dps.heal("DEVELOPER_HARMED"))