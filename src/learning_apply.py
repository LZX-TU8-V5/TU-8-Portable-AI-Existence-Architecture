"""
learning_apply.py - Phase 5: 双轨应用

按产物类型和轨道归属执行写入:
  - 图书馆轨道(RULE/ALERT)→ TOOLS.md / 通知队列
  - 宫殿轨道(PREFERENCE/INTUITION/MEMO)→ USER.md / 直觉引擎 / MEMORY.md
"""

import json
import os
import time
from pathlib import Path
from typing import Any

# T5→T4 适配器
from learning_to_gc_adapter import on_apply as gc_on_apply
from learning_to_seal_adapter import on_apply as seal_on_apply

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.path.expanduser("~/.qclaw/workspace")))


class LearningApplicator:
    """Phase 5: 执行学习结果"""

    # 动作映射
    ACTION_MAP = {
        "append_to_tools": "_write_tools",
        "notify_creator": "_write_alert",
        "inject_intuition": "_update_intuition",
        "update_profile": "_update_profile",
        "append_memory": "_write_memo",
    }

    def __init__(self):
        self._applied: list[dict] = []
        self._errors: list[tuple[str, str]] = []

    def apply(self, results: list[dict]) -> dict:
        """
        批量执行产物应用。
        输入:Phase 4 校验结果列表(仅处理 decision="accept" 的)
        返回:{"applied": int, "errors": int, "details": [...]}
        """
        accepted = [r["product"] for r in results if r.get("decision") == "accept"]
        if not accepted:
            return {"applied": 0, "errors": 0, "details": []}

        details = []
        for product in accepted:
            action = product.get("action", "append_memory")
            method_name = self.ACTION_MAP.get(action, "_write_memo")
            method = getattr(self, method_name, self._write_memo)
            try:
                method(product)
                self._applied.append(product)

                # T5→T4: 自动注册保护
                try:
                    gc_on_apply(product)
                except Exception:
                    pass

                # T5→T2: 置信产物铸印
                try:
                    seal_on_apply(product)
                except Exception:
                    pass

                details.append({"id": product.get("id", "?"), "action": action, "status": "ok"})
            except Exception as e:
                self._errors.append((product.get("id", "?"), str(e)))
                details.append({"id": product.get("id", "?"), "action": action, "status": f"error: {e}"})

        return {
            "applied": len(self._applied),
            "errors": len(self._errors),
            "details": details,
        }

    # ── 写入方法 ────────────────────────────

    def _write_tools(self, product: dict):
        """图书馆轨道:追加规则到 TOOLS.md"""
        tools_path = WORKSPACE / "TOOLS.md"
        content = product.get("content", "")

        if not tools_path.exists():
            tools_path.write_text(f"# TOOLS.md\n\n## 学习链自动追加规则\n\n", encoding="utf-8")

        existing_text = tools_path.read_text(encoding="utf-8")

        # 检查是否已存在相同规则
        if content.strip() in existing_text:
            return  # 已存在,跳过

        with open(tools_path, "a", encoding="utf-8") as f:
            f.write(f"\n### 学习链规则 ({time.strftime('%Y-%m-%d')})\n")
            f.write(f"- {content}\n")
            f.write(f"  - 置信度:{product.get('confidence', 0):.2f}\n")
            f.write(f"  - 来源:{product.get('source_pattern', '未知')}\n")

    def _write_alert(self, product: dict):
        """图书馆轨道:写入告警队列(供下次心跳读取)"""
        alert_path = WORKSPACE / "memory" / "_learning_alerts.jsonl"
        alert_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": time.time(),
            "type": "learning_alert",
            "content": product.get("content", ""),
            "source": product.get("source_pattern", ""),
            "confidence": product.get("confidence", 0),
            "read": False,
        }
        with open(alert_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _update_intuition(self, product: dict):
        """宫殿轨道:注入直觉引擎匹配库"""
        intuition_path = WORKSPACE / "src" / "intuition_engine.py"
        content = product.get("content", "")

        if not intuition_path.exists():
            return

        # 追加到直觉引擎的匹配库尾部
        existing_text = intuition_path.read_text(encoding="utf-8")
        marker = "# === 学习链自动注入 ===\n"

        if marker not in existing_text:
            existing_text += f"\n\n{marker}"
            intuition_path.write_text(existing_text, encoding="utf-8")

        # 添加注释标记
        # 注意:实际注入需要直觉引擎支持运行时热加载
        # 这里先写入注释,后续设计会实现动态注入
        inject_line = f"# LEARNED: {content} (conf={product.get('confidence', 0):.2f}, {time.strftime('%Y-%m-%d')})\n"
        with open(intuition_path, "a", encoding="utf-8") as f:
            f.write(inject_line)

    def _update_profile(self, product: dict):
        """宫殿轨道:通过 profile_update_loop 更新 USER.md"""
        # 写入 user_state_changes.md,由 profile_update_loop 消化
        state_path = WORKSPACE / "memory" / "user_state_changes.md"
        content = product.get("content", "")
        now_str = time.strftime("%Y-%m-%d %H:%M")
        line = f"\n- [{now_str}] 学习链检测:{content}"

        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "a", encoding="utf-8") as f:
            f.write(line)

    def _write_memo(self, product: dict):
        """宫殿轨道:追加到 MEMORY.md 底部"""
        memo_path = WORKSPACE / "MEMORY.md"
        content = product.get("content", "")
        now_str = time.strftime("%Y-%m-%d")

        if not memo_path.exists():
            memo_path.write_text("# MEMORY.md\n\n", encoding="utf-8")

        existing = memo_path.read_text(encoding="utf-8")
        # 简单去重
        if content.strip() in existing:
            return

        section = f"\n## {now_str} (学习链)\n- {content}\n"
        with open(memo_path, "a", encoding="utf-8") as f:
            f.write(section)

    # ── 反馈 ──────────────────────────────

    def report(self) -> str:
        pieces = [f"Applied: {len(self._applied)}, Errors: {len(self._errors)}"]
        for e in self._errors:
            pieces.append(f"  ERROR [{e[0]}]: {e[1]}")
        return "\n".join(pieces)


if __name__ == "__main__":
    # 简单测试
    test_results = [
        {
            "decision": "accept",
            "product": {
                "id": "lp_test01",
                "content": "用户在说'重做'时优先回滚而非从头开始",
                "confidence": 0.85,
                "support": 3,
                "track": "library",
                "action": "append_to_tools",
                "source_pattern": "causal_chain: TOPIC_JUMP→DISSATISFACTION",
            },
        },
        {
            "decision": "accept",
            "product": {
                "id": "lp_test02",
                "content": "用户对深夜话题的响应模式",
                "confidence": 0.75,
                "support": 5,
                "track": "palace",
                "action": "update_profile",
                "source_pattern": "topic_cluster: 深夜话题",
            },
        },
        {
            "decision": "accept",
            "product": {
                "id": "lp_test03",
                "content": "异常集中在22点(5/10)",
                "confidence": 0.9,
                "support": 5,
                "track": "library",
                "action": "notify_creator",
                "source_pattern": "time_pattern",
            },
        },
    ]

    applicator = LearningApplicator()
    result = applicator.apply(test_results)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n{applicator.report()}")
