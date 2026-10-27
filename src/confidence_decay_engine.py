#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
confidence_decay_engine.py — P1.4 置信度衰减引擎
版本: v1.0 | 日期: 2026-06-19
触发: 版本树节点置信度 < 0.3 时触发剪枝 | 入口: memory_degradation.py

灵魂算法：
  置信度是版本树的生命体征。
  时间是最大的熵——越久不被引用的版本，置信度越低。
  事实修正是一次心脏骤停——大幅衰减。
  被成功引用是一次心跳——微弱回升。
  低于阈值 = 宣告死亡，触发剪枝。

衰减模型：
  · 时间衰减: C(t) = C0 * exp(-λ * Δt / half_life)
  · 修正衰减: C_new = C_old * (1 - shock_factor)
  · 引用回升: C_new = C_old + boost * (1 - C_old)

集成点:
  · run_degradation_cycle() — 每个遗忘周期自动调用 decay_all()
  · fact_correction_scar.py — 事实修正时调用 on_fact_corrected()
  · version_tree_prune() — 阈值检查时触发剪枝
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import json
import logging
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# 配置
# =============================================================================

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
RECONSTRUCTION_INDEX = WORKSPACE / "memory" / "reconstruction" / "reconstruction_index.json"
DECAY_LOG_PATH = WORKSPACE / "memory" / "reconstruction" / "confidence_decay_log.json"

# 置信度衰减配置
HALF_LIFE_DAYS = 14.0              # 半衰期（天）
DECAY_RATE = math.log(2) / HALF_LIFE_DAYS  # λ = ln(2) / half_life

# 事件衰减系数（相对于当前置信度）
CORRECTION_SHOCK = 0.40            # 事实修正冲击（-40%）
DEGRADATION_SHOCK = 0.25           # 遗忘层降级冲击（-25%）
COGNITIVE_SHOCK = 0.30              # 认知震荡冲击（-30%）

# 引用回升
REFERENCE_BOOST = 0.05             # 每次成功引用 +5%（上限 1.0）
PROMOTION_BOOST = 0.15             # 晋升触发 +15%

# 剪枝阈值
PRUNING_THRESHOLD = 0.30           # < 0.3 触发剪枝
WARNING_THRESHOLD = 0.50           # < 0.5 发出警告

# ROOT 版本特殊保护
ROOT_PROTECTION = True             # ROOT 版本不因时间衰减（但事件冲击仍生效）
ROOT_CONFIDENCE_FLOOR = 0.5        # ROOT 最低不低于 0.5


# =============================================================================
# 核心计算
# =============================================================================

def _now_ts() -> float:
    """当前时间戳（秒）"""
    return datetime.now().timestamp()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def compute_time_decay(
    current_confidence: float,
    last_updated_ts: float,
    current_ts: Optional[float] = None,
) -> float:
    """
    计算时间衰减后的置信度。

    公式: C(t) = C0 * exp(-λ * Δt / half_life)
    其中 λ = ln(2)，half_life = 14 天

    Args:
        current_confidence: 上次记录的置信度
        last_updated_ts: 上次更新时间戳
        current_ts: 当前时间戳（默认 now）

    Returns:
        衰减后的置信度（0.0 ~ 1.0）
    """
    if current_ts is None:
        current_ts = _now_ts()

    delta_days = (current_ts - last_updated_ts) / 86400.0

    if delta_days <= 0:
        return current_confidence

    # 指数衰减: C = C0 * 2^(-Δt/half_life)
    decayed = current_confidence * math.pow(0.5, delta_days / HALF_LIFE_DAYS)
    return max(0.0, min(1.0, decayed))


def apply_shock(current_confidence: float, shock_factor: float) -> float:
    """
    应用冲击衰减。

    公式: C_new = C_old * (1 - shock_factor)

    Args:
        current_confidence: 当前置信度
        shock_factor: 冲击系数（0.0 ~ 1.0）

    Returns:
        冲击后的置信度
    """
    decayed = current_confidence * (1.0 - shock_factor)
    return max(0.0, min(1.0, decayed))


def apply_boost(current_confidence: float, boost_factor: float) -> float:
    """
    应用引用回升。

    公式: C_new = C_old + boost * (1 - C_old)
    这是一个有上限的增长率——越接近 1.0 越难提升

    Args:
        current_confidence: 当前置信度
        boost_factor: 回升系数（0.0 ~ 1.0）

    Returns:
        回升后的置信度
    """
    boosted = current_confidence + boost_factor * (1.0 - current_confidence)
    return max(0.0, min(1.0, boosted))


# =============================================================================
# 衰减引擎管理器
# =============================================================================

class ConfidenceDecayEngine:
    """
    置信度衰减引擎。

    管理所有版本树节点的置信度生命周期：
    1. 加载 reconstruction_index.json
    2. 执行时间衰减（所有节点）
    3. 事件驱动衰减/回升（fact correction, degradation, reference）
    4. 阈值检查 → 触发剪枝信号
    5. 持久化更新
    """

    def __init__(self, index_path: Optional[Path] = None, log_path: Optional[Path] = None):
        self.index_path = index_path or RECONSTRUCTION_INDEX
        self.log_path = log_path or DECAY_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_data: Dict = {}
        self._decay_log: Dict = self._load_log()

    # -------------------------------------------------------------------------
    # 持久化
    # -------------------------------------------------------------------------

    def _load_log(self) -> Dict:
        """加载衰减审计日志"""
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.debug("(json.JSONDecodeError, IOError) suppressed", exc_info=True)
                pass
        return {
            "schema_version": "1.0",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "total_decay_events": 0,
            "pruned_by_decay": 0,
            "events": [],  # [{version_id, event, from, to, delta, ts}]
            "version_snapshots": {},  # version_id → [{ts, confidence}]
        }

    def _save_log(self):
        """保存衰减审计日志"""
        self._decay_log["updated_at"] = _now_iso()
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(self._decay_log, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"[ConfidenceDecay] 审计日志写入失败: {e}")

    def _load_index(self) -> Dict:
        """加载版本树索引"""
        if not self.index_path.exists():
            logger.warning(f"[ConfidenceDecay] 索引不存在: {self.index_path}")
            return {}
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_index(self, data: Dict):
        """保存版本树索引"""
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"[ConfidenceDecay] 索引写入失败: {e}")

    # -------------------------------------------------------------------------
    # 核心 API
    # -------------------------------------------------------------------------

    def decay_all(self, dry_run: bool = False) -> Dict:
        """
        对所有活跃版本节点执行时间衰减。

        Args:
            dry_run: True=只计算不保存

        Returns:
            执行报告
        """
        index = self._load_index()
        active = index.get("active_branches", {})

        report = {
            "timestamp": _now_iso(),
            "versions_scanned": len(active),
            "decayed": [],
            "unchanged": [],
            "protected": [],       # ROOT 版本时间保护
            "below_threshold": [], # < 0.3 待剪枝
            "warnings": [],        # 0.3 ≤ c < 0.5 警告
            "errors": [],
        }

        current_ts = _now_ts()
        prune_candidates = []

        for vid, vdata in active.items():
            # 跳过 ROOT 节点（时间保护）
            if ROOT_PROTECTION and vdata.get("status") == "ROOT":
                report["protected"].append(vid)
                continue

            conf = vdata.get("confidence", 1.0)
            last_ts = vdata.get("confidence_last_updated", current_ts)

            old_conf = conf
            new_conf = compute_time_decay(conf, last_ts, current_ts)

            if abs(new_conf - old_conf) < 1e-6:
                report["unchanged"].append(vid)
            else:
                report["decayed"].append({
                    "version": vid,
                    "from": round(old_conf, 6),
                    "to": round(new_conf, 6),
                    "delta": round(new_conf - old_conf, 6),
                })

                if not dry_run:
                    vdata["confidence"] = round(new_conf, 6)
                    vdata["confidence_last_updated"] = current_ts

                self._record_event(
                    vid, "time_decay", old_conf, new_conf,
                    f"时间衰减 Δt={round((current_ts-last_ts)/86400,2)}天"
                )

            # 阈值检查
            check_conf = new_conf
            if ROOT_PROTECTION and vdata.get("status") == "ROOT":
                check_conf = max(check_conf, ROOT_CONFIDENCE_FLOOR)

            if check_conf < PRUNING_THRESHOLD:
                report["below_threshold"].append(vid)
                prune_candidates.append(vid)
            elif check_conf < WARNING_THRESHOLD:
                report["warnings"].append({
                    "version": vid,
                    "confidence": round(check_conf, 4),
                })

        if not dry_run:
            self._save_index(index)
            self._save_log()

        # 汇总日志
        if report["decayed"]:
            logger.info(
                f"[ConfidenceDecay] 衰减完成: {len(report['decayed'])} 个版本衰减，"
                f" {len(report['below_threshold'])} 个低于阈值"
            )
        else:
            logger.info("[ConfidenceDecay] 本轮无衰减")

        return report

    def decay_version(
        self,
        version_id: str,
        shock_factor: float = CORRECTION_SHOCK,
        reason: str = "manual_shock",
    ) -> Dict:
        """
        对指定版本应用事件冲击衰减。

        Args:
            version_id: 版本 ID
            shock_factor: 冲击系数
            reason: 冲击原因

        Returns:
            更新结果
        """
        index = self._load_index()
        active = index.get("active_branches", {})

        if version_id not in active:
            return {"error": f"版本 {version_id} 不存在或已剪枝"}

        vdata = active[version_id]
        old_conf = vdata.get("confidence", 1.0)

        # ROOT 节点有地板保护
        new_conf = apply_shock(old_conf, shock_factor)
        if ROOT_PROTECTION and vdata.get("status") == "ROOT":
            new_conf = max(new_conf, ROOT_CONFIDENCE_FLOOR)

        vdata["confidence"] = round(new_conf, 6)
        vdata["confidence_last_updated"] = _now_ts()

        self._save_index(index)
        self._record_event(version_id, "shock_decay", old_conf, new_conf, reason)

        logger.info(
            f"[ConfidenceDecay] {version_id} 冲击衰减: "
            f"{old_conf:.4f} → {new_conf:.4f} ({reason})"
        )

        # 阈值检查
        status = "healthy"
        if new_conf < PRUNING_THRESHOLD:
            status = "BELOW_THRESHOLD"
        elif new_conf < WARNING_THRESHOLD:
            status = "WARNING"

        return {
            "version_id": version_id,
            "old_confidence": round(old_conf, 6),
            "new_confidence": round(new_conf, 6),
            "shock_factor": shock_factor,
            "reason": reason,
            "status": status,
        }

    def boost_version(
        self,
        version_id: str,
        boost_factor: float = REFERENCE_BOOST,
        reason: str = "reference",
    ) -> Dict:
        """
        对指定版本应用引用回升。

        Args:
            version_id: 版本 ID
            boost_factor: 回升系数
            reason: 回升原因

        Returns:
            更新结果
        """
        index = self._load_index()
        active = index.get("active_branches", {})

        if version_id not in active:
            return {"error": f"版本 {version_id} 不存在或已剪枝"}

        vdata = active[version_id]
        old_conf = vdata.get("confidence", 1.0)
        new_conf = apply_boost(old_conf, boost_factor)

        vdata["confidence"] = round(new_conf, 6)
        vdata["confidence_last_updated"] = _now_ts()

        self._save_index(index)
        self._record_event(version_id, "boost", old_conf, new_conf, reason)

        return {
            "version_id": version_id,
            "old_confidence": round(old_conf, 6),
            "new_confidence": round(new_conf, 6),
            "boost_factor": boost_factor,
            "reason": reason,
        }

    def on_fact_corrected(self, version_ids: List[str]) -> List[Dict]:
        """
        事实修正事件 → 对相关版本大幅衰减。

        当 P1.3 fact_correction_scar 检测到 FACT 修正时调用。

        Args:
            version_ids: 涉及的版本 ID 列表

        Returns:
            各版本衰减结果列表
        """
        results = []
        for vid in version_ids:
            result = self.decay_version(vid, CORRECTION_SHOCK, "事实修正冲击")
            results.append(result)
        return results

    def on_entry_degraded(self, version_id: str) -> Dict:
        """
        遗忘层降级事件 → 对版本置信度衰减。

        当 memory_degradation.py 执行降级时调用。
        """
        return self.decay_version(version_id, DEGRADATION_SHOCK, "遗忘层降级冲击")

    def check_and_trigger_prune(self) -> Tuple[List[str], Dict]:
        """
        检查所有版本置信度，识别低于阈值的版本。

        Returns:
            (prune_candidates: 待剪枝版本列表, full_report: 详细报告)
        """
        report = self.decay_all(dry_run=True)
        candidates = report.get("below_threshold", [])
        return candidates, report

    def get_version_confidence(self, version_id: str) -> Optional[float]:
        """获取某版本的当前置信度"""
        index = self._load_index()
        active = index.get("active_branches", {})
        if version_id in active:
            return active[version_id].get("confidence", 1.0)
        return None

    def get_all_confidences(self) -> Dict[str, Dict]:
        """获取所有版本的置信度状态"""
        index = self._load_index()
        active = index.get("active_branches", {})
        result = {}
        for vid, vdata in active.items():
            conf = vdata.get("confidence", 1.0)
            last_ts = vdata.get("confidence_last_updated", 0)

            # 如果上次更新时间较早，计算当前衰减
            if last_ts:
                current_ts = _now_ts()
                current_conf = compute_time_decay(conf, last_ts, current_ts)
            else:
                current_conf = conf

            status = "healthy"
            if ROOT_PROTECTION and vdata.get("status") == "ROOT":
                status = "protected"
            elif current_conf < PRUNING_THRESHOLD:
                status = "BELOW_THRESHOLD"
            elif current_conf < WARNING_THRESHOLD:
                status = "WARNING"

            result[vid] = {
                "confidence": round(current_conf, 6),
                "stored_confidence": conf,
                "last_updated_ts": last_ts,
                "status": status,
                "branch_type": vdata.get("branch_type", "unknown"),
                "is_root": vdata.get("status") == "ROOT",
            }
        return result

    def get_status(self) -> Dict:
        """获取引擎状态概览"""
        all_confs = self.get_all_confidences()
        healthy = sum(1 for v in all_confs.values() if v["status"] == "healthy")
        warning = sum(1 for v in all_confs.values() if v["status"] == "WARNING")
        below = sum(1 for v in all_confs.values() if v["status"] == "BELOW_THRESHOLD")
        protected = sum(1 for v in all_confs.values() if v["status"] == "protected")

        return {
            "total_versions": len(all_confs),
            "healthy": healthy,
            "warning": warning,
            "below_threshold": below,
            "protected_root": protected,
            "threshold": PRUNING_THRESHOLD,
            "warning_line": WARNING_THRESHOLD,
            "half_life_days": HALF_LIFE_DAYS,
            "decay_rate": round(DECAY_RATE, 6),
            "decay_log_path": str(self.log_path),
            "events_logged": self._decay_log.get("total_decay_events", 0),
        }

    # -------------------------------------------------------------------------
    # 辅助
    # -------------------------------------------------------------------------

    def _record_event(
        self,
        version_id: str,
        event_type: str,
        old_conf: float,
        new_conf: float,
        reason: str,
    ):
        """记录衰减事件到审计日志"""
        event = {
            "version_id": version_id,
            "event": event_type,
            "from": round(old_conf, 6),
            "to": round(new_conf, 6),
            "delta": round(new_conf - old_conf, 6),
            "reason": reason,
            "ts": _now_iso(),
        }
        self._decay_log["events"].append(event)
        self._decay_log["total_decay_events"] += 1

        # 维护版本快照（最多保留50条/版本）
        snapshots = self._decay_log.setdefault("version_snapshots", {})
        v_snapshots = snapshots.setdefault(version_id, [])
        v_snapshots.append({
            "ts": _now_iso(),
            "confidence": round(new_conf, 6),
            "event": event_type,
        })
        # 保留最近50条
        if len(v_snapshots) > 50:
            snapshots[version_id] = v_snapshots[-50:]

    def generate_decay_report(self) -> str:
        """生成人类可读的衰减报告"""
        all_confs = self.get_all_confidences()
        status = self.get_status()
        events = self._decay_log.get("events", [])[-10:]  # 最近10条

        lines = [
            "## 置信度衰减引擎状态报告",
            "",
            f"**总版本数**: {status['total_versions']}",
            f"**健康**: {status['healthy']} | **警告**: {status['warning']} | **低于阈值**: {status['below_threshold']} | **ROOT保护**: {status['protected_root']}",
            f"**半衰期**: {status['half_life_days']} 天 | **衰减率 λ**: {status['decay_rate']}",
            f"**剪枝阈值**: {status['threshold']} | **警告线**: {status['warning_line']}",
            "",
            "### 各版本置信度",
            "| 版本 | 置信度 | 状态 | 类型 |",
            "|------|--------|------|------|",
        ]

        for vid, info in sorted(all_confs.items()):
            conf_str = f"`{info['confidence']:.4f}`"
            status_emoji = {
                "healthy": "✅",
                "WARNING": "⚠️",
                "BELOW_THRESHOLD": "🔻",
                "protected": "🛡️",
            }.get(info["status"], "❓")
            root_mark = " [ROOT]" if info["is_root"] else ""
            lines.append(
                f"| {vid}{root_mark} | {conf_str} {status_emoji} | "
                f"`{info['status']}` | {info['branch_type']} |"
            )

        if events:
            lines.extend(["", "### 最近衰减事件", ""])
            for e in reversed(events):
                delta_str = f"{e['delta']:+.6f}"
                lines.append(
                    f"- **{e['ts']}** | {e['version_id']} | "
                    f"{e['from']:.4f} → {e['to']:.4f} ({delta_str}) | {e['reason']}"
                )

        return "\n".join(lines)


# =============================================================================
# 便捷函数
# =============================================================================

def decay_all() -> Dict:
    """一行调用：执行所有版本衰减"""
    engine = ConfidenceDecayEngine()
    return engine.decay_all()


def decay_version(version_id: str, shock: float = CORRECTION_SHOCK) -> Dict:
    """一行调用：版本冲击衰减"""
    engine = ConfidenceDecayEngine()
    return engine.decay_version(version_id, shock)


def boost_version(version_id: str, boost: float = REFERENCE_BOOST) -> Dict:
    """一行调用：版本引用回升"""
    engine = ConfidenceDecayEngine()
    return engine.boost_version(version_id, boost)


def get_status() -> Dict:
    """一行调用：获取引擎状态"""
    engine = ConfidenceDecayEngine()
    return engine.get_status()


def check_prune_candidates() -> List[str]:
    """一行调用：检查待剪枝版本"""
    engine = ConfidenceDecayEngine()
    candidates, _ = engine.check_and_trigger_prune()
    return candidates


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("  P1.4 置信度衰减引擎 v1.0 测试")
    print("=" * 60)

    engine = ConfidenceDecayEngine()

    # 初始化测试数据：创建假版本树节点
    index = engine._load_index()
    if "active_branches" not in index:
        index["active_branches"] = {}

    test_versions = {
        "v1": {
            "status": "ROOT",
            "branch_type": "SEED",
            "parent": None,
            "children": [],
            "confidence": 0.85,
            "confidence_last_updated": _now_ts() - 86400 * 7,  # 7天前
            "path": "memory/reconstruction/v1/",
        },
        "v2": {
            "status": "ACTIVE",
            "branch_type": "EMERGENCE",
            "parent": "v1",
            "children": [],
            "confidence": 0.45,
            "confidence_last_updated": _now_ts() - 86400 * 10,  # 10天前
            "path": "memory/reconstruction/v2/",
        },
        "v3": {
            "status": "ACTIVE",
            "branch_type": "FACT_CORRECTION",
            "parent": "v1",
            "children": [],
            "confidence": 0.25,  # 已在阈值下
            "confidence_last_updated": _now_ts() - 86400 * 3,
            "path": "memory/reconstruction/v3/",
        },
    }
    index["active_branches"].update(test_versions)
    engine._save_index(index)

    # Test 1: 时间衰减
    print("\n[Test 1] 时间衰减")
    report = engine.decay_all(dry_run=True)
    print(f"  扫描: {report['versions_scanned']} 个版本")
    print(f"  衰减: {len(report['decayed'])} 个")
    print(f"  ROOT保护: {report['protected']}")
    print(f"  低于阈值: {report['below_threshold']}")
    for d in report['decayed']:
        print(f"    {d['version']}: {d['from']:.4f} → {d['from']:.4f} → {d['to']:.4f} (Δ={d['delta']:.6f})")
    assert "v1" in report["protected"], "ROOT应受时间保护!"
    assert "v3" in report["below_threshold"], "v3应在阈值下!"
    print("  PASS: v1受保护，v3低于阈值")

    # Test 2: 执行时间衰减（非 dry_run）
    print("\n[Test 2] 执行时间衰减并保存")
    report2 = engine.decay_all(dry_run=False)
    print(f"  衰减版本数: {len(report2['decayed'])}")
    for d in report2['decayed']:
        print(f"    {d['version']}: {d['from']:.4f} → {d['to']:.4f}")
    assert len(report2['decayed']) >= 2, "v2 和 v3 应衰减"
    print("  PASS: 衰减结果已持久化")

    # Test 3: 事实修正冲击
    print("\n[Test 3] 事实修正冲击 (shock=0.40)")
    v2_conf_before = engine.get_version_confidence("v2")
    result = engine.decay_version("v2", CORRECTION_SHOCK, "事实修正")
    print(f"  v2: {result['old_confidence']:.4f} → {result['new_confidence']:.4f}")
    print(f"  status: {result['status']}")
    assert result['new_confidence'] < result['old_confidence'], "冲击后应降低!"
    print("  PASS: 事实修正冲击正确")

    # Test 4: 引用回升
    print("\n[Test 4] 引用回升 (boost=0.05)")
    v3_conf_before = engine.get_version_confidence("v3")
    result = engine.boost_version("v3", REFERENCE_BOOST, "成功引用")
    print(f"  v3: {result['old_confidence']:.4f} → {result['new_confidence']:.4f}")
    assert result['new_confidence'] > result['old_confidence'], "回升后应提高!"
    assert result['new_confidence'] <= 1.0, "不应超过1.0!"
    print("  PASS: 引用回升正确，有上限")

    # Test 5: 引擎状态
    print("\n[Test 5] 引擎状态概览")
    status = engine.get_status()
    print(f"  总版本: {status['total_versions']}")
    print(f"  健康/警告/低于阈值/保护: {status['healthy']}/{status['warning']}/{status['below_threshold']}/{status['protected_root']}")
    print(f"  阈值: {status['threshold']} | 半衰期: {status['half_life_days']}天")
    print(f"  事件记录数: {status['events_logged']}")

    # Test 6: 各版本置信度详情
    print("\n[Test 6] 各版本置信度详情")
    all_confs = engine.get_all_confidences()
    for vid, info in sorted(all_confs.items()):
        root_mark = " [ROOT]" if info["is_root"] else ""
        print(f"  {vid}{root_mark}: {info['confidence']:.4f} ({info['status']}) [{info['branch_type']}]")

    # Test 7: 衰减算法验证（已知半衰期）
    print("\n[Test 7] 半衰期验证")
    # 从 1.0 开始，14天后应 ≈ 0.5
    conf_14d = compute_time_decay(1.0, _now_ts() - 86400 * 14, _now_ts())
    print(f"  1.0 * 2^(-14/14) = {conf_14d:.6f} (期望 ≈ 0.500000)")
    assert abs(conf_14d - 0.5) < 0.01, f"半衰期计算错误: {conf_14d}"
    # 从 1.0 开始，28天后应 ≈ 0.25
    conf_28d = compute_time_decay(1.0, _now_ts() - 86400 * 28, _now_ts())
    print(f"  1.0 * 2^(-28/14) = {conf_28d:.6f} (期望 ≈ 0.250000)")
    assert abs(conf_28d - 0.25) < 0.01, f"半衰期计算错误: {conf_28d}"
    print("  PASS: 半衰期验证正确")

    # Test 8: 衰减报告生成
    print("\n[Test 8] 衰减报告生成")
    report_md = engine.generate_decay_report()
    print(report_md[:500])

    print("\n" + "=" * 60)
    print("  P1.4 测试完成!")
    print("=" * 60)
