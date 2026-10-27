"""
learning_engine.py — 第5链主入口

编排五阶段流水线：
  Phase 1 收集 → Phase 2 连线 → Phase 3 精炼 → Phase 4 双轨验证 → Phase 5 应用

在梦境期由 dream_check_cron.py 调用（在代谢链条之后）。
"""

import json
import os
import time
from pathlib import Path
from typing import Any

from learning_collector import LearningCollector
from learning_connect import LearningConnect
from learning_verify import PalaceValidator
from learning_apply import LearningApplicator

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.path.expanduser("~/.qclaw/workspace")))


class LearningEngine:
    """第5链核心引擎"""

    def __init__(self):
        self.cycle_id = 0
        self._load_cycle_id()

    def _state_path(self) -> Path:
        return WORKSPACE / "memory" / "_learning_engine_state.json"

    def _load_cycle_id(self):
        p = self._state_path()
        if p.exists():
            try:
                state = json.loads(p.read_text(encoding="utf-8"))
                self.cycle_id = state.get("last_cycle_id", 0)
            except (json.JSONDecodeError, OSError):
                self.cycle_id = 0

    def _save_state(self):
        p = self._state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "last_cycle_id": self.cycle_id,
            "last_run_at": time.time(),
        }
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def run(self) -> dict:
        """执行一次完整的五阶段学习循环"""
        self.cycle_id += 1
        phase_times: dict[str, float] = {}
        start_all = time.time()

        report_parts = []
        report_parts.append(f"=== 第5链学习引擎 Cycle #{self.cycle_id} ===")

        # ── Phase 1: 收集 ────────────────────
        t0 = time.time()
        collector = LearningCollector(dream_cycle_id=self.cycle_id)
        sensor_data = collector.collect()
        summary = collector.summary()
        has_data = any(v for v in summary.values() if v)
        phase_times["collect"] = time.time() - t0

        if not has_data:
            report_parts.append("Phase 1: 无新传感器数据，跳过本轮")
            self._save_state()
            return {
                "cycle_id": self.cycle_id,
                "status": "skipped",
                "reason": "no new sensor data",
                "phases": phase_times,
            }

        report_parts.append(f"Phase 1 收集: {json.dumps(summary, ensure_ascii=False)}")

        # ── Phase 2: 连线 ────────────────────
        t0 = time.time()
        connector = LearningConnect(sensor_data)
        candidates = connector.connect()
        phase_times["connect"] = time.time() - t0

        if not candidates:
            report_parts.append("Phase 2: 无候选模式，跳过后续")
            self._save_state()
            return {
                "cycle_id": self.cycle_id,
                "status": "skipped",
                "reason": "no patterns found",
                "phases": phase_times,
                "summary": summary,
            }

        report_parts.append(f"Phase 2 连线: {len(candidates)} 候选模式")

        # ── Phase 3: 精炼 ────────────────────
        t0 = time.time()
        products = connector.refine(candidates)
        phase_times["refine"] = time.time() - t0

        # 统计产物类型
        type_counts = {}
        for p in products:
            t = p.get("type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1
        track_counts = {}
        for p in products:
            t = p.get("track", "?")
            track_counts[t] = track_counts.get(t, 0) + 1

        report_parts.append(f"Phase 3 精炼: {len(products)} 产物 ({type_counts})")
        report_parts.append(f"  轨道分布: {track_counts}")

        # ── Phase 4: 验证 ────────────────────
        t0 = time.time()
        validator = PalaceValidator()

        # 先处理暂存区的跨周期产物
        promoted, expired, remaining = validator.process_pending(self.cycle_id)

        # 再校验本轮新产物
        new_results = validator.batch_validate(products, self.cycle_id)
        phase_times["verify"] = time.time() - t0

        # 统计校验结果
        all_results = promoted + new_results
        decision_counts = {}
        for r in all_results:
            d = r["decision"]
            decision_counts[d] = decision_counts.get(d, 0) + 1

        report_parts.append(f"Phase 4 双轨校验: {decision_counts}")
        if expired:
            report_parts.append(f"  过期丢弃: {len(expired)} 暂存产物")
        if remaining:
            report_parts.append(f"  暂存中: {len(remaining)} 产物")

        # ── Phase 5: 应用 ────────────────────
        t0 = time.time()
        applicator = LearningApplicator()
        apply_result = applicator.apply(all_results)
        phase_times["apply"] = time.time() - t0

        report_parts.append(f"Phase 5 应用: {apply_result['applied']} 成功, {apply_result['errors']} 错误")

        # T5→T3: 通知调度器（高置信产物调度验证任务）
        try:
            from t3_middleware import on_learning_products_ready
            applied_products = [
                {"id": p["id"], "type": p["type"], "confidence": p.get("confidence", 0)}
                for p in products if p.get("confidence", 0) >= 0.7
            ]
            on_learning_products_ready(applied_products)
        except Exception:
            pass

        # ── 完成 ──────────────────────────
        phase_times["total"] = time.time() - start_all
        report_parts.append(f"总耗时: {phase_times['total']:.2f}s")

        self._save_state()

        full_report = "\n".join(report_parts)

        return {
            "cycle_id": self.cycle_id,
            "status": "complete",
            "phases": phase_times,
            "summary": summary,
            "candidates": len(candidates),
            "products": len(products),
            "decisions": decision_counts,
            "applied": apply_result["applied"],
            "errors": apply_result["errors"],
            "report": full_report,
        }


if __name__ == "__main__":
    engine = LearningEngine()
    result = engine.run()
    print(result.get("report", json.dumps(result, ensure_ascii=False, indent=2)))
