# -*- coding: utf-8 -*-
"""
dispatch_cocoon_router.py — B6 茧房防御接入 ContextAssembler

把 EntropyAwareRouter.route_with_defense() 接入 assemble() 末尾。
茧房状态注入 assembly 元数据，供 LLM prompt 感知 + 后续硬路由。

数据流：
  ContextAssembler.assemble()
    → EntropyAwareRouter.route_with_defense(candidates)
      → EntropyGuard.check()
      → FORCED/WARNING 时返回茧房链优先
    → assembly.metadata["cocoon"] = {status, injected_chain, activation_triggered}
    → assembly.metadata["routed_chain"] = selected_chain_id
"""
from __future__ import annotations

import sys
import logging
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

logger = logging.getLogger("cocoon_router")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径 ──────────────────────────────────────────────────────
def _ws() -> Path:
    import os
    return Path(os.environ.get("QCLAW_WORKSPACE",
                              r"C:\Users\qq366410837\.qclaw\workspace"))

SRC = lambda: _ws() / "src"


# ── Intent → Chain 候选映射 ──────────────────────────────────────
# 格式：(chain_id, base_confidence)
# base_confidence = 意图与链的自然匹配度，由 assemble() 动态调整
INTENT_CHAIN_CANDIDATES: Dict[str, List[Tuple[str, float]]] = {
    # 钢印相关 → T1
    "QUERY_SELF_IDENTITY": [("T1", 0.9), ("T2", 0.5), ("T3", 0.3)],
    "QUERY_SECURITY":       [("T1", 0.9), ("T2", 0.4), ("T3", 0.3)],
    "CODE_TASK":            [("T3", 0.8), ("T4", 0.7), ("T5", 0.6)],
    "TASK_PLANNING":        [("T4", 0.9), ("T3", 0.6), ("T5", 0.5)],
    "REFLECTION":           [("T1", 0.7), ("T2", 0.9), ("T6", 0.5)],
    "RECALL_PERSONAL_HISTORY": [("T2", 0.9), ("T1", 0.5), ("T3", 0.3)],
    "QUERY_LOCAL_KNOWLEDGE": [("T3", 0.7), ("T2", 0.6), ("T6", 0.4)],
    "CREATIVE_WRITING":     [("T7", 0.8), ("T1", 0.5), ("T6", 0.4)],
    "UNKNOWN":             [("T1", 0.5), ("T2", 0.5), ("T3", 0.5),
                            ("T4", 0.4), ("T5", 0.3), ("T6", 0.3), ("T7", 0.3)],
}


# ── 茧房感知路由 ─────────────────────────────────────────────────
class CocoonAwareRouter:
    """
    感知茧房状态的上下文路由增强器。
    
    接法：在 ContextAssembler.assemble() 末尾调用 route()。
    返回：(selected_chain, cocoon_report, candidates)
    """

    def __init__(self, entropy_guard=None):
        self._guard = entropy_guard
        self._router = None
        if entropy_guard is not None:
            try:
                from entropy_guard import EntropyAwareRouter
                self._router = EntropyAwareRouter(entropy_guard)
            except ImportError:
                logger.warning("[CocoonRouter] EntropyAwareRouter import failed")

    def route(
        self,
        intent_tag: str,
        context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any], List[Tuple[str, float]]]:
        """
        主入口：茧房感知链路由。
        
        Args:
            intent_tag: IntentTag enum value 或字符串
            context_snapshot: 可选快照（目前未用，备扩展）
            
        Returns:
            (selected_chain, cocoon_report, candidates)
        """
        # 1. 构建候选链
        candidates = self._build_candidates(intent_tag)
        
        # 2. 茧房检查
        cocoon_report = self._check_cocoon()
        
        # 3. 路由
        selected = self._do_route(candidates)
        
        return selected, cocoon_report, candidates

    def _build_candidates(self, intent_tag: str) -> List[Tuple[str, float]]:
        """从 intent 推断候选链"""
        tag_str = str(intent_tag).split(".")[-1]  # "IntentTag.REFLECTION" → "REFLECTION"
        if tag_str in INTENT_CHAIN_CANDIDATES:
            return list(INTENT_CHAIN_CANDIDATES[tag_str])
        # 回退：尝 intent_tag 字符串本身
        for key in INTENT_CHAIN_CANDIDATES:
            if key in tag_str.upper():
                return list(INTENT_CHAIN_CANDIDATES[key])
        return list(INTENT_CHAIN_CANDIDATES["UNKNOWN"])

    def _check_cocoon(self) -> Dict[str, Any]:
        """检查茧房状态"""
        if self._guard is None:
            return {"status": "NO_GUARD", "injection_triggered": False}
        
        try:
            report = self._guard.check()
            return {
                "status": report.status,
                "injection_triggered": report.injection_triggered,
                "injected_chain": report.injected_chain,
                "n_chains": report.n_chains,
                "dormant_chains": report.dormant_chains,
                "entropy": round(report.entropy, 4),
                "normalized_entropy": round(report.normalized_entropy, 4),
            }
        except Exception as e:
            logger.warning(f"[CocoonRouter] guard.check() failed: {e}")
            return {"status": "CHECK_FAILED", "error": str(e)}

    def _do_route(self, candidates: List[Tuple[str, float]]) -> str:
        """实际路由：优先用 EntropyAwareRouter，否则用置信度排序"""
        if self._router is not None and candidates:
            try:
                return self._router.route_with_defense(candidates)
            except Exception as e:
                logger.warning(f"[CocoonRouter] route_with_defense failed: {e}")
        
        # 回退：直接选置信度最高
        if candidates:
            return max(candidates, key=lambda x: x[1])[0]
        return "T1"  # 安全默认值


# ── 独立 CLI ────────────────────────────────────────────────────
def main():
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", default="UNKNOWN")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # 尝试加载真实 EntropyGuard
    guard = None
    try:
        sys.path.insert(0, str(SRC()))
        from entropy_guard import EntropyGuard
        guard = EntropyGuard()
    except Exception as e:
        print(f"[WARN] EntropyGuard load failed: {e}", file=sys.stderr)

    router = CocoonAwareRouter(guard)
    selected, report, candidates = router.route(args.intent)
    
    if args.json:
        print(json.dumps({
            "selected_chain": selected,
            "cocoon_report": report,
            "candidates": [{"chain": c, "confidence": round(conf, 3)} for c, conf in candidates],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Intent: {args.intent}")
        print(f"Candidates: {candidates}")
        print(f"Cocoon: {report}")
        print(f"Selected: {selected}")


if __name__ == "__main__":
    main()
