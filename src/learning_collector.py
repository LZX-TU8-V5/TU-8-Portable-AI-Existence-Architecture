"""
learning_collector.py — Phase 1: 收集

从各传感器暂存区读取本轮梦境期的积累信号，
聚合后标记 dream_cycle_id，输出给 Phase 2。
"""

import json
import os
import time
from pathlib import Path

from seal_to_learning_adapter import SealSensorAdapter

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.path.expanduser("~/.qclaw/workspace")))

SENSOR_PATHS = {
    "anomaly": WORKSPACE / "memory" / "anomaly_log.jsonl",
    "pain": WORKSPACE / "memory" / "cognitive_pain_monitor.json",
    "intuition": WORKSPACE / "memory" / "intuition_feedback.jsonl",
    "shadow": WORKSPACE / "memory" / "shadow_protocol_log.jsonl",
    "hypothesis": WORKSPACE / "memory" / "pending_hypotheses.jsonl",
    "pending_events": WORKSPACE / "memory" / "pending_events.jsonl",
    "seal": WORKSPACE / "memory" / "seal_sensor_feed.jsonl",
    "gc_feedback": WORKSPACE / "memory" / "_gc_feedback.jsonl",
    # T3→T5: 调度链执行统计
    "execution_stats": None,  # 动态读取，不走文件
    # T5→T7: 欲系统张力信号（尖刺推力 + 凹陷引力）
    "tension_signals": WORKSPACE / "memory" / "learning_alerts.jsonl",
}


class LearningCollector:
    """Phase 1: 从各传感器拉取本轮数据，聚合为统一结构"""

    def __init__(self, dream_cycle_id: int):
        self.cycle_id = dream_cycle_id
        self.sensor_data = {
            "anomaly": [],
            "pain": {},
            "intuition": [],
            "shadow": [],
            "hypothesis": [],
            "pending_events": [],
            "seal": [],
            # T3→T5
            "execution_stats": {},
        }
        self._last_read_offsets: dict = {}
        self._load_offset_file()

    # ── 偏移量追踪（避免重复读取） ────────────────────

    def _offset_path(self) -> Path:
        p = WORKSPACE / "memory" / "_learning_collector_offsets.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_offset_file(self):
        p = self._offset_path()
        if p.exists():
            try:
                self._last_read_offsets = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._last_read_offsets = {}
        else:
            self._last_read_offsets = {}

    def _save_offset(self, sensor_key: str, offset: int):
        self._last_read_offsets[sensor_key] = offset
        self._offset_path().write_text(
            json.dumps(self._last_read_offsets, ensure_ascii=False), encoding="utf-8"
        )

    # ── 读取各传感器 ──────────────────────────────

    def _read_jsonl(self, sensor_key: str, path: Path) -> list:
        """逐行读取 .jsonl 文件中新增的记录"""
        if not path.exists():
            return []
        last_offset = self._last_read_offsets.get(sensor_key, 0)
        try:
            file_size = path.stat().st_size
            if file_size <= last_offset:
                return []
            with open(path, "r", encoding="utf-8") as f:
                f.seek(last_offset)
                lines = f.readlines()
            self._save_offset(sensor_key, file_size)
        except (OSError, IOError):
            return []

        records = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec["_sensor"] = sensor_key
                rec["_cycle_id"] = self.cycle_id
                records.append(rec)
            except json.JSONDecodeError:
                continue
        return records

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    # ── 主入口 ──────────────────────────────

    def collect(self) -> dict:
        """执行一次全传感器收集，返回聚合数据"""
        self.sensor_data["anomaly"] = self._read_jsonl("anomaly", SENSOR_PATHS["anomaly"])
        self.sensor_data["pain"] = self._read_json(SENSOR_PATHS["pain"])
        self.sensor_data["intuition"] = self._read_jsonl("intuition", SENSOR_PATHS["intuition"])
        self.sensor_data["shadow"] = self._read_jsonl("shadow", SENSOR_PATHS["shadow"])
        self.sensor_data["hypothesis"] = self._read_jsonl("hypothesis", SENSOR_PATHS["hypothesis"])
        self.sensor_data["pending_events"] = self._read_jsonl(
            "pending_events", SENSOR_PATHS["pending_events"]
        )

        # T1→T5: 钢印数据传感器
        try:
            adapter = SealSensorAdapter()
            seal_records = adapter.build_records()
            self.sensor_data["seal"] = seal_records
            if seal_records:
                offset_file = SENSOR_PATHS["seal"]
                if offset_file.exists():
                    self._save_offset("seal", offset_file.stat().st_size)
        except Exception as e:
            self.sensor_data["seal"] = []

        self.sensor_data["gc_feedback"] = self._read_jsonl("gc_feedback", SENSOR_PATHS["gc_feedback"])

        # T5→T7: 欲系统张力信号读入（尖刺推力 + 凹陷引力）
        try:
            tension_raw = self._read_jsonl("tension_signals", SENSOR_PATHS["tension_signals"])
            # 按 signal_type 分离推力和引力
            self.sensor_data["tension_spike_push"] = [
                r for r in tension_raw if r.get("signal_type") == "spike_push"
            ]
            self.sensor_data["tension_valley_pull"] = [
                r for r in tension_raw if r.get("signal_type") == "valley_pull"
            ]
        except Exception:
            self.sensor_data["tension_spike_push"] = []
            self.sensor_data["tension_valley_pull"] = []

        # T3→T5: 调度链执行统计
        try:
            from t3_middleware import get_execution_stats_for_learning
            self.sensor_data["execution_stats"] = get_execution_stats_for_learning()
        except Exception:
            self.sensor_data["execution_stats"] = {}

        # 标记时间戳
        self.sensor_data["_meta"] = {
            "cycle_id": self.cycle_id,
            "collected_at": time.time(),
            "record_counts": {
                k: len(v) if isinstance(v, list) else (1 if v else 0)
                for k, v in self.sensor_data.items()
                if not k.startswith("_")
            },
        }
        return self.sensor_data

    def summary(self) -> dict:
        """快速汇总本轮传感器数据概览"""
        counts = {}
        for key in ["anomaly", "intuition", "shadow", "hypothesis", "pending_events", "seal", "gc_feedback"]:
            records = self.sensor_data.get(key, [])
            counts[key] = len(records) if isinstance(records, list) else None
        counts["pain"] = bool(self.sensor_data.get("pain"))
        return counts


if __name__ == "__main__":
    # 简单测试
    collector = LearningCollector(dream_cycle_id=1)
    data = collector.collect()
    print(f"Cycle #{collector.cycle_id} collected:")
    print(json.dumps(collector.summary(), ensure_ascii=False, indent=2))
