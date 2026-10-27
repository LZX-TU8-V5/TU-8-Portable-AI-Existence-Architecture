"""
seal_to_learning_adapter.py — T1→T5 中间件：钢印数据接入学习传感器

功能：
  将时间钢印链的决策历史适配为学习链 Phase 1 的传感器格式，
  输出结构兼容 learning_collector 的 .jsonl 格式。

数据流：
  seal_index.json → adapter.FetchSealSensor.build_records() → learning_collector
"""

import json
import os
import time
from pathlib import Path

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.environ.get("QCLAW_WORKSPACE",
    os.path.expanduser("~/.qclaw/workspace"))))

SEAL_INDEX = WORKSPACE / "memory" / "time_chain" / "seal_index.json"
SENSOR_OUT = WORKSPACE / "memory" / "seal_sensor_feed.jsonl"


class SealSensorAdapter:
    """将钢印数据转换为学习传感器的标准记录格式"""

    # 钢印场景标签到学习传感器分类
    SCENE_MAP = {
        "response": "behavior_pattern",
        "deep_sleep": "metabolic_pattern",
        "error": "error_pattern",
        "warning": "error_pattern",
        "micro_sleep": "metabolic_pattern",
        "memory_to_seal": "memory_pattern",
        "conflict": "conflict_pattern",
        "unknown": "unknown_pattern",
    }

    def __init__(self):
        self._last_seen_id = None
        self._load_progress()

    # ── 进度追踪 ──────────────────────────

    def _progress_path(self):
        return WORKSPACE / "memory" / "_seal_adapter_progress.json"

    def _load_progress(self):
        p = self._progress_path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self._last_seen_id = data.get("last_seen_id")
            except (json.JSONDecodeError, OSError):
                self._last_seen_id = None
        else:
            self._last_seen_id = None

    def _save_progress(self, seal_id: str):
        p = self._progress_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "last_seen_id": seal_id,
            "updated_at": time.time(),
        }, ensure_ascii=False), encoding="utf-8")

    # ── 读数 ──────────────────────────

    def _read_seals(self) -> list[dict]:
        """读取钢印索引，返回按时间排序的列表"""
        if not SEAL_INDEX.exists():
            return []

        try:
            seals = json.loads(SEAL_INDEX.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if isinstance(seals, dict):
            # 兼容 dict 格式
            seals = list(seals.values())

        if not isinstance(seals, list):
            return []

        # 按时间排序（旧→新）
        seals.sort(key=lambda s: s.get("timestamp", 0))
        return seals

    def _classify(self, scene_tag: str) -> str:
        """将钢印场景标签映射为学习传感器分类"""
        scene_key = scene_tag.split(":")[0].strip() if ":" in scene_tag else scene_tag
        return self.SCENE_MAP.get(scene_key, "unknown_pattern")

    def _to_learning_record(self, seal: dict) -> dict:
        """将单个钢印记录转换为学习链传感器格式"""
        scene_tag = seal.get("scene_tag", "unknown")
        summary = seal.get("summary", "")
        ts = seal.get("timestamp", 0)
        parent = seal.get("parent_seal", "")

        return {
            "timestamp": ts,
            "sensor": "seal",
            "pattern_type": self._classify(scene_tag),
            "scene_tag": scene_tag,
            "summary_preview": summary[:80],
            "has_parent": bool(parent),
            "seal_id": seal.get("seal_id", ""),
            "parent_seal_id": parent,
            "scene_tag": scene_tag,
        }

    # ── 主入口 ──────────────────────────

    def build_records(self) -> list[dict]:
        """
        获取自上次读取以来新增的钢印记录，
        按学习链 Phase 1 集合格式返回。
        """
        seals = self._read_seals()
        if not seals:
            return []

        # 找到上次读取的断点
        start_idx = 0
        if self._last_seen_id:
            for i, s in enumerate(seals):
                if s.get("seal_id") == self._last_seen_id:
                    start_idx = i + 1
                    break

        new_seals = seals[start_idx:]
        if not new_seals:
            return []

        records = []
        for s in new_seals:
            record = self._to_learning_record(s)
            records.append(record)

        # 记录进度
        self._save_progress(new_seals[-1].get("seal_id", ""))

        # 也写入 .jsonl 供 learning_collector 读取
        if records:
            SENSOR_OUT.parent.mkdir(parents=True, exist_ok=True)
            with open(SENSOR_OUT, "a", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

        return records

    def summary(self) -> dict:
        """概述当前钢印状态"""
        seals = self._read_seals()
        if not seals:
            return {"count": 0, "types": {}}

        type_counts = {}
        for s in seals:
            st = self._classify(s.get("scene_tag", ""))
            type_counts[st] = type_counts.get(st, 0) + 1

        return {
            "count": len(seals),
            "last_seen_id": self._last_seen_id,
            "new_available": len([s for s in seals if s.get("seal_id") == self._last_seen_id]) if self._last_seen_id else len(seals),
            "types": type_counts,
        }


def feed_learning_collector() -> dict:
    """
    学习链 Phase 1 的扩展传感器入口。
    由 learning_collector.py 调用，返回本轮新增记录。
    """
    adapter = SealSensorAdapter()
    records = adapter.build_records()
    return {
        "sensor": "seal",
        "new_records": len(records),
        "records": records,
    }


if __name__ == "__main__":
    adapter = SealSensorAdapter()
    print("Current seal status:")
    print(json.dumps(adapter.summary(), ensure_ascii=False, indent=2))

    records = adapter.build_records()
    print(f"\nNew records: {len(records)}")
    for r in records:
        print(f"  [{r['pattern_type']}] {r['summary_preview'][:60]}")
