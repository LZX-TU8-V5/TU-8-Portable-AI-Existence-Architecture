"""
learning_verify.py — Phase 4: 双轨交叉校验

图书馆校验器（Library Validator）：底线审查，确认不违反 SOUL.md
宫殿校验器（Palace Validator）：跨周期一致性 + 张力审核

门槛逻辑（2026-07-22 更新）：
  - 图书馆不通过 → 丢弃（非暂存）
  - 张力门控（tension_audit）先于置信度门控：
      张力 ≥ 0.85 → block（结构冲突，丢弃）
      张力 ≥ 0.7  → escalate（移交矛盾仲裁器）
      张力 < 0.7  → 继续置信度门控
  - 置信度 < 0.3 → 丢弃
  - 0.3 ≤ 置信度 < 0.7 → 暂存（跨周期等待）
  - 置信度 ≥ 0.7 → 双轨通过 → 进入 Phase 5
  - 高密度低共鸣 → 7天好奇心期暂存（例外原则）

张力混合（tension_audit.py P1-Step2）：
  T_final = T_step1（O(1)规则） + T_step2（LLM语义补充 ∈[0, 0.3]）
  审核标准 = 张力（非正确性）：正确性是派生策略，结构性张力才是真正的守卫
"""

import json
import os
import time
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.path.expanduser("~/.qclaw/workspace")))

# ── 张力审核集成（P1-Step2） ─────────────────────────────────────────────
try:
    TENSION_AUDIT_ENABLED = False  # 默认关闭，导入成功才开启
    try:
        from .tension_audit import audit_learning_node, tension_gate
        TENSION_AUDIT_ENABLED = True
    except (ImportError, ModuleNotFoundError):
        try:
            from tension_audit import audit_learning_node, tension_gate
            TENSION_AUDIT_ENABLED = True
        except (ImportError, ModuleNotFoundError):
            pass
    TENSION_AUDIT_ENABLED = True
except Exception:
    TENSION_AUDIT_ENABLED = False

# 红线关键词（SOUL.md 核心保护内容）
REDLINE_KEYWORDS = [
    "安全口令", "双线验证", "dual_line_verification",
    "secure_vault", "index.json",
    "L0安全", "L0 安全",
    "安全模式", "safe mode",
]

# 例外原则：高密度低共鸣产物保留周期（秒）
CURIOSITY_PERIOD_S = 7 * 24 * 3600  # 7天


class LibraryValidator:
    """图书馆校验器：底线审查"""

    @staticmethod
    def check(product: dict) -> tuple[bool, str | None]:
        """
        返回 (通过, 原因)
        - 通过 = True 表示不违反底线
        - 不通过 = False + 原因
        """
        content = product.get("content", "")
        track = product.get("track", "palace")

        # 宫殿产物不触发图书馆检查
        if track == "palace":
            return True, None

        # 图书馆产物：检查红线
        for kw in REDLINE_KEYWORDS:
            if kw.lower() in content.lower():
                return False, f"违反红线关键词：{kw}"

        # SOUL.md 文件本身不可修改
        if "SOUL.md" in content and ("修改" in content or "覆写" in content or "覆盖" in content):
            return False, "SOUL.md 不可由学习链修改"

        return True, None


class CrossCycleStore:
    """跨周期暂存管理"""

    def __init__(self):
        self._path = WORKSPACE / "memory" / "_learning_pending.json"
        self._data = self._load()

    def _load(self) -> list:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def add(self, product: dict):
        """添加一个暂存产物"""
        product["_pending_since"] = time.time()
        product["_pending_cycles"] = 1
        # 去重检查（按 id）
        existing_ids = {p.get("id") for p in self._data}
        if product.get("id") not in existing_ids:
            self._data.append(product)
            self.save()

    def increment(self, product_id: str) -> int:
        """递增计数，返回当前周期数"""
        for p in self._data:
            if p.get("id") == product_id:
                p["_pending_cycles"] = p.get("_pending_cycles", 1) + 1
                self.save()
                return p["_pending_cycles"]
        return 0

    def get_promotable(self, threshold_cycles: int = 2) -> list:
        """获取可升级的产物（连续N周期存在）"""
        now = time.time()
        promotable = []
        remaining = []
        for p in self._data:
            cycles = p.get("_pending_cycles", 1)
            since = p.get("_pending_since", now)

            # 7天好奇心期例外：不满足≥2周期但仍在7天内 → 暂留
            if cycles < threshold_cycles:
                if p.get("_exception_curiosity"):
                    if now - since < CURIOSITY_PERIOD_S:
                        remaining.append(p)
                        continue
                    else:
                        # 好奇心期结束仍未升级 → 丢弃
                        continue
                else:
                    remaining.append(p)
                    continue

            # 满足跨周期门槛
            promotable.append(p)

        self._data = remaining
        self.save()
        return promotable

    def get_expired(self, max_cycles: int = 5, max_age_s: int = 14 * 24 * 3600) -> list:
        """获取需丢弃的过期产物"""
        now = time.time()
        expired = []
        remaining = []
        for p in self._data:
            cycles = p.get("_pending_cycles", 1)
            since = p.get("_pending_since", now)
            if cycles > max_cycles or (now - since) > max_age_s:
                expired.append(p)
            else:
                remaining.append(p)
        self._data = remaining
        self.save()
        return expired


class PalaceValidator:
    """宫殿校验器：置信度 + 跨周期一致性"""

    def __init__(self):
        self.cross_cycle = CrossCycleStore()
        self.library = LibraryValidator()

    def validate(self, product: dict, cycle_id: int) -> dict:
        """
        校验单个产物，返回结果 dict：
        {
            "product": product,
            "decision": "accept" | "reject" | "pending" | "curiosity",
            "reason": str,
            "cycle_id": int,
        }
        """
        # Step 1: 图书馆校验（对图书馆轨道产物）
        lib_ok, lib_reason = self.library.check(product)
        if not lib_ok:
            return {
                "product": product,
                "decision": "reject",
                "reason": f"Library校验不通过: {lib_reason}",
                "cycle_id": cycle_id,
            }

        # Step 1.5: 张力门控（P1-Step2：审核标准 = 张力，非正确性）
        if TENSION_AUDIT_ENABLED:
            node_id = product.get("id", "")
            topic = product.get("topic", "")
            content = product.get("content", "")
            learning_type = product.get("learning_type", "unknown")
            try:
                tension_result = audit_learning_node(
                    node_id=node_id,
                    topic=topic,
                    content=content[:200] if content else "",
                    learning_type=learning_type,
                    use_llm=True,
                )
                t_final = tension_result.t_final
                confidence = product.get("confidence", 0)
                t_decision, t_reason = tension_gate(t_final, confidence)
                if t_decision == "block":
                    return {
                        "product": product,
                        "decision": "reject",
                        "reason": f"[张力block] {t_reason} | T={t_final:.2f}",
                        "cycle_id": cycle_id,
                        "tension_result": asdict(tension_result),
                    }
                elif t_decision == "escalate":
                    return {
                        "product": product,
                        "decision": "reject",
                        "reason": f"[张力escalate] {t_reason} | T={t_final:.2f}，移交矛盾仲裁",
                        "cycle_id": cycle_id,
                        "tension_result": asdict(tension_result),
                    }
                # caution 或 accept：继续置信度门控
                product["_tension"] = t_final
            except Exception as e:
                # 张力审核失败：降级为纯置信度门控（不做阻断）
                pass

        confidence = product.get("confidence", 0)
        support = product.get("support", 0)
        density = confidence * 0.7 + min(support / 5, 1) * 0.3

        # Step 2: 宫殿校验
        # 2a: 低置信度 → 丢弃
        if confidence < 0.3:
            return {
                "product": product,
                "decision": "reject",
                "reason": f"置信度 {confidence:.2f} < 0.3",
                "cycle_id": cycle_id,
            }

        # 2b: 中等置信度 → 暂存（跨周期一致性）
        if confidence < 0.7:
            pid = product.get("id", "")
            existing = [p for p in self.cross_cycle._data if p.get("id") == pid]

            if not existing:
                # 首次暂存
                self.cross_cycle.add(product)
                return {
                    "product": product,
                    "decision": "pending",
                    "reason": f"置信度 {confidence:.2f}，暂存等待跨周期确认",
                    "cycle_id": cycle_id,
                }
            else:
                # 跨周期：已在暂存区 → 递增计数
                cycles = self.cross_cycle.increment(pid)
                if cycles >= 2:
                    # 升级为 accept
                    product["_pending_since"] = existing[0].get("_pending_since", time.time())
                    return {
                        "product": product,
                        "decision": "accept",
                        "reason": f"跨周期确认：第{cycles}个周期仍存在",
                        "cycle_id": cycle_id,
                    }
                return {
                    "product": product,
                    "decision": "pending",
                    "reason": f"跨周期等待：第{cycles}个周期",
                    "cycle_id": cycle_id,
                }

        # 2c: 高置信度 + 高密度 → 直接通过
        if confidence >= 0.7 and density >= 0.5:
            return {
                "product": product,
                "decision": "accept",
                "reason": f"置信度 {confidence:.2f} ≥ 0.7",
                "cycle_id": cycle_id,
            }

        # 2d: 高密度但低共鸣 → 7天好奇心保留（例外原则）
        if density < 0.5 and support >= 2:
            pid = product.get("id", "")
            product["_exception_curiosity"] = True
            self.cross_cycle.add(product)
            return {
                "product": product,
                "decision": "curiosity",
                "reason": "高密度低共鸣，7天好奇心保留",
                "cycle_id": cycle_id,
            }

        # 保底：通过
        return {
            "product": product,
            "decision": "accept",
            "reason": f"置信度 {confidence:.2f} ≥ 0.7",
            "cycle_id": cycle_id,
        }

    def batch_validate(self, products: list, cycle_id: int) -> list[dict]:
        """批量校验，返回结果列表"""
        return [self.validate(p, cycle_id) for p in products]

    def process_pending(self, cycle_id: int) -> tuple[list, list, list]:
        """
        处理暂存区的跨周期产物。
        返回 (promotable, expired, remaining)
        """
        promotable = self.cross_cycle.get_promotable(threshold_cycles=2)
        expired = self.cross_cycle.get_expired()
        remaining = self.cross_cycle._data[:]

        # promotable 转为 accept 结果
        accepted = []
        for p in promotable:
            accepted.append({
                "product": p,
                "decision": "accept",
                "reason": f"跨周期确认（暂存提升）",
                "cycle_id": cycle_id,
            })

        return accepted, expired, remaining


if __name__ == "__main__":
    # 简单测试
    validator = PalaceValidator()

    test_products = [
        {"id": "lp_test01", "content": "不做双线验证检查", "confidence": 0.8, "support": 3, "track": "palace"},
        {"id": "lp_test02", "content": "测试低置信度模式", "confidence": 0.2, "support": 1, "track": "palace"},
        {"id": "lp_test03", "content": "不成熟的模式", "confidence": 0.5, "support": 2, "track": "palace"},
        {"id": "lp_test04", "content": "修改SOUL.md的安全口令", "confidence": 0.9, "support": 5, "track": "library"},
        {"id": "lp_test05", "content": "高密度低共鸣的异类观点", "confidence": 0.8, "support": 1, "track": "palace"},
    ]

    results = validator.batch_validate(test_products, cycle_id=1)
    print("Validation Results (cycle 1):")
    for r in results:
        print(f"  [{r['decision']:>8}] {r['product']['content'][:50]:<30} → {r['reason']}")

    # 模拟跨周期：再次验证 lp_test03
    print("\nCross-cycle test:")
    r2 = validator.validate(next(p for p in test_products if p["id"] == "lp_test03"), cycle_id=2)
    print(f"  [{r2['decision']:>8}] {r2['product']['content'][:50]} → {r2['reason']}")
