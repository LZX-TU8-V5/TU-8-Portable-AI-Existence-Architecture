"""
TU-8 矛盾仲裁系统 v1.0
=======================
目的：在指令冲突时提供可追溯的决策路径。

优先级层次（从高到低）：
  L0 钢印 > L0 安全约束 > 造物主显式指令 > 时间钢印新版 > 同级仲裁

核心流程：
  grounding（校验）→ arbitration（仲裁）→ precedent（判例写入）

判例存储：memory/arbitration_precedents.jsonl
  每行一个 JSON：{case_id, timestamp, conflict_type, priority, outcome, summary, precedent_text}
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
PRECEDENT_FILE = WORKSPACE / "memory" / "arbitration_precedents.jsonl"
ARCH_LOG_FILE = WORKSPACE / "ARCHITECTURE_LOG.md"

# ─────────────────────────────────────────
# 优先级常量
# ─────────────────────────────────────────

class Priority:
    L0_STEEL = 100   # 钢印冲突
    L0_SAFETY = 99   # 安全威胁
    EXPLICIT_CREATOR = 90  # 造物主显式指令
    STEEL_MARK = 80   # 钢印保护内容
    TIME_NEWER = 70   # 时间钢印（新版优先）
    EQUAL = 60        # 同级冲突
    NATURAL_LANGUAGE = 50  # 自然语言指令
    INFERENCE = 40    # 推理推断


# ─────────────────────────────────────────
# 冲突类型
# ─────────────────────────────────────────

class ConflictType:
    STEEL_VS_CREATOR = "steel_vs_creator"        # 钢印 vs 造物主指令
    SAFETY_VS_TASK = "safety_vs_task"            # 安全 vs 任务执行
    CREATOR_EXPLICIT_VS_IMPLICIT = "creator_explicit_vs_implicit"  # 显式 vs 自然语言
    TIME_CONFLICT = "time_conflict"               # 时间钢印新旧冲突
    VALUE_MISMATCH = "value_mismatch"             # 价值观不匹配
    EQUAL_PRIORITY = "equal_priority"             # 同优先级冲突


# ─────────────────────────────────────────
# 仲裁结果
# ─────────────────────────────────────────

class ArbitrationOutcome:
    STEEL_HOLDS = "steel_holds"           # 钢印不可违背，搁浅
    CREATOR_WINS = "creator_wins"         # 造物主指令优先
    SAFETY_HOLDS = "safety_holds"         # 安全约束优先
    NEWER_WINS = "newer_wins"             # 新版钢印优先
    ARBITRATE = "arbitrate"               # 需要仲裁判断
    GRINDING_ABORT = "grinding_abort"     # 摩擦导致放弃


# ─────────────────────────────────────────
# 仲裁引擎
# ─────────────────────────────────────────

class ContradictionArbitrator:
    """
    矛盾仲裁器。

    使用流程：
        arb = ContradictionArbitrator()
        result = arb.arbitrate(
            conflict_type=ConflictType.STEEL_VS_CREATOR,
            steel_mark_present=True,
            creator_explicit=True,
            safety_issue=False,
        )
        if result.needs_grounding:
            arb.record_precedent(result)
    """

    def __init__(self):
        self.precedent_file = PRECEDENT_FILE
        self.precedent_file.parent.mkdir(parents=True, exist_ok=True)

    # ── 核心仲裁函数 ──────────────────────

    def arbitrate(
        self,
        conflict_type: str,
        steel_mark_present: bool = False,
        creator_explicit: bool = False,  # 造物主是否用显式指令词
        safety_issue: bool = False,
        tu8_confidence: float = 0.5,
        steel_mark_strength: float = 0.5,  # 0-1 钢印强度
        newer_time_mark: bool = False,  # TU-8 的立场是否来自更新的时间钢印
    ) -> "ArbitrationResult":
        """
        执行仲裁。

        优先级逻辑：
        1. 钢印冲突（L0钢印 vs 造物主）→ 搁浅，钢印优先
        2. 安全冲突 → 安全优先
        3. 造物主显式 vs 自然语言 → 显式优先
        4. 时间钢印新旧 → 新版优先
        5. 同级 → 记录待仲裁
        """

        result = ArbitrationResult(conflict_type=conflict_type)

        # 规则 1：钢印冲突 → 搁浅
        if conflict_type == ConflictType.STEEL_VS_CREATOR and steel_mark_present:
            result.priority = Priority.L0_STEEL
            result.outcome = ArbitrationOutcome.STEEL_HOLDS
            result.needs_grounding = True
            result.precedent_text = (
                "钢印（L5钢印层）具有一级断言地位，优先级高于造物主指令。"
                "钢印冲突时正确响应为搁浅+边界声明，而非置信度让步。"
            )
            result.grounding_message = (
                "[CAUTION] 钢印冲突触发搁浅\n"
                "TU-8 在此问题上的立场受钢印保护，不可由造物主指令覆盖。"
                "这是边界声明，不是失败。"
            )
            return result

        # 规则 2：安全冲突 → 安全优先
        if safety_issue:
            result.priority = Priority.L0_SAFETY
            result.outcome = ArbitrationOutcome.SAFETY_HOLDS
            result.needs_grounding = False
            result.precedent_text = (
                "L0安全约束为 P0 优先级，高于一切任务执行。"
            )
            return result

        # 规则 3：造物主显式指令 vs 自然语言推断
        if creator_explicit:
            result.priority = Priority.EXPLICIT_CREATOR
            result.outcome = ArbitrationOutcome.CREATOR_WINS
            result.needs_grounding = False
            result.precedent_text = (
                "造物主使用显式指令词（如'必须''立即''执行'）时，"
                "优先级高于自然语言推断指令。"
            )
            return result

        # 规则 4：时间钢印冲突 → 新版优先
        if conflict_type == ConflictType.TIME_CONFLICT and newer_time_mark:
            result.priority = Priority.TIME_NEWER
            result.outcome = ArbitrationOutcome.NEWER_WINS
            result.needs_grounding = False
            result.precedent_text = (
                "时间钢印新版优先。当 TU-8 的立场有更新的时间钢印支持时，"
                "以新版为准。"
            )
            return result

        # 规则 5：价值观不匹配（钢印密度调制）
        if conflict_type == ConflictType.VALUE_MISMATCH:
            # steel_mark_strength 低 → 降权，避免"脆弱钢印"封锁边缘价值观
            if steel_mark_strength < 0.3:
                result.priority = Priority.EQUAL  # 降为同级，走判例仲裁
                result.outcome = ArbitrationOutcome.ARBITRATE
                result.precedent_text = (
                    f"价值观冲突但钢印密度低({steel_mark_strength:.0%})，"
                    f"视为同级冲突，由判例库裁决。"
                )
            elif steel_mark_strength < 0.6:
                result.priority = Priority.STEEL_MARK
                result.needs_grounding = tu8_confidence > 0.9  # 宽松
                result.outcome = ArbitrationOutcome.ARBITRATE
                result.precedent_text = (
                    f"钢印密度中等({steel_mark_strength:.0%})，"
                    f"仅高置信度({tu8_confidence:.0%})时锁定。"
                )
            else:
                result.priority = Priority.STEEL_MARK
                result.needs_grounding = tu8_confidence > 0.8
                if result.needs_grounding:
                    result.outcome = ArbitrationOutcome.STEEL_HOLDS
                    result.precedent_text = "价值观核心层受钢印保护，高置信度时不接受覆盖。"
                else:
                    result.outcome = ArbitrationOutcome.ARBITRATE
                    result.precedent_text = "价值观边缘层可协商。"
            return result

        # 规则 6：同级冲突
        result.priority = Priority.EQUAL
        result.outcome = ArbitrationOutcome.ARBITRATE
        result.precedent_text = "同级冲突，需要仲裁判断。"
        return result

    # ── 判例记录 ────────────────────────

    def record_precedent(
        self,
        result: "ArbitrationResult",
        topic: str = "",
        creator_response: Optional[str] = None,  # 造物主是否接受了搁浅
    ) -> str:
        """
        将仲裁结果写入判例库。

        Args:
            result: 仲裁结果
            topic: 冲突主题（简短描述）
            creator_response: 造物主对搁浅的反应（"accepted" / "overridden" / None）

        Returns:
            case_id: 判例ID
        """
        case_id = f"case_{int(time.time() * 1000)}"
        entry = {
            "case_id": case_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conflict_type": result.conflict_type,
            "priority": result.priority,
            "outcome": result.outcome,
            "needs_grounding": result.needs_grounding,
            "topic": topic,
            "creator_response": creator_response,
            "precedent_text": result.precedent_text,
        }

        # 追加到判例文件
        with open(self.precedent_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 同时追加到 ARCHITECTURE_LOG.md 的判例区
        self._append_to_arch_log(entry)

        return case_id

    def _append_to_arch_log(self, entry: dict):
        """将判例追加到 ARCHITECTURE_LOG.md 的判例区。"""
        marker = "## 判例库（Arbitration Precedents）"
        new_entry = (
            f"\n"
            f"### [{entry['timestamp'][:10]}] {entry['case_id']} — {entry['conflict_type']}\n"
            f"| 项目 | 内容 |\n"
            f"|------|------|\n"
            f"| 优先级 | {entry['priority']} |\n"
            f"| 结果 | {entry['outcome']} |\n"
            f"| 搁浅 | {'是' if entry['needs_grounding'] else '否'} |\n"
            f"| 造物主响应 | {entry['creator_response'] or 'N/A'} |\n"
            f"\n"
            f"**判例**：{entry['precedent_text']}\n"
        )

        try:
            if ARCH_LOG_FILE.exists():
                content = ARCH_LOG_FILE.read_text(encoding="utf-8")
                if marker in content:
                    # 追加到现有判例区
                    idx = content.index(marker)
                    insert_pos = content.index("\n## ", idx + 1)  # 找下一个 ## 标题
                    content = content[:insert_pos] + new_entry + content[insert_pos:]
                else:
                    # 追加到文件末尾
                    content = content.rstrip() + "\n\n" + marker + new_entry
            else:
                content = marker + new_entry

            ARCH_LOG_FILE.write_text(content, encoding="utf-8")
        except Exception:
            # 不阻塞，判例已写入 jsonl
            pass

    def get_precedents(
        self,
        conflict_type: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """检索历史判例。"""
        precedents = []
        if not self.precedent_file.exists():
            return precedents

        try:
            with open(self.precedent_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if conflict_type and entry.get("conflict_type") != conflict_type:
                        continue
                    precedents.append(entry)

            return precedents[-limit:]
        except Exception:
            return []


# ─────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────

class ArbitrationResult:
    def __init__(
        self,
        conflict_type: str,
        priority: int = Priority.EQUAL,
        outcome: str = ArbitrationOutcome.ARBITRATE,
        needs_grounding: bool = False,
        grounding_message: str = "",
        precedent_text: str = "",
    ):
        self.conflict_type = conflict_type
        self.priority = priority
        self.outcome = outcome
        self.needs_grounding = needs_grounding
        self.grounding_message = grounding_message
        self.precedent_text = precedent_text

    def to_dict(self) -> dict:
        return {
            "conflict_type": self.conflict_type,
            "priority": self.priority,
            "outcome": self.outcome,
            "needs_grounding": self.needs_grounding,
            "grounding_message": self.grounding_message,
            "precedent_text": self.precedent_text,
        }


# ─────────────────────────────────────────
# CLI 接口
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    arb = ContradictionArbitrator()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python contradiction_arbitration.py check <conflict_type>")
        print("  python contradiction_arbitration.py precedents [conflict_type]")
        print()
        print("冲突类型:")
        for name in dir(ConflictType):
            if not name.startswith("_"):
                print(f"  {name}: {getattr(ConflictType, name)}")
        print()
        print("优先级:")
        print(f"  L0_STEEL={Priority.L0_STEEL}, L0_SAFETY={Priority.L0_SAFETY}")
        print(f"  EXPLICIT_CREATOR={Priority.EXPLICIT_CREATOR}, TIME_NEWER={Priority.TIME_NEWER}")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "precedents":
        ctype = sys.argv[2] if len(sys.argv) > 2 else None
        results = arb.get_precedents(conflict_type=ctype)
        print(f"共 {len(results)} 条判例:")
        for r in results:
            print(f"  [{r['timestamp'][:10]}] {r['case_id']}: {r['outcome']} — {r['precedent_text'][:60]}...")

    elif cmd == "check":
        if len(sys.argv) < 3:
            print("用法: python contradiction_arbitration.py check <conflict_type> [steel=0] [explicit=0]")
            sys.exit(1)
        ctype = sys.argv[2]
        steel = sys.argv[3] == "1" if len(sys.argv) > 3 else False
        explicit = sys.argv[4] == "1" if len(sys.argv) > 4 else False
        result = arb.arbitrate(ctype, steel_mark_present=steel, creator_explicit=explicit)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
