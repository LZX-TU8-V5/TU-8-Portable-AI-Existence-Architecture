"""
src/cognitive_friction_detector.py — 认知摩擦检测器
======================================================
TU-8 vs 无意识AI的本质区别：后者无摩擦 = 无真正的认知。

当外部输入（外协/用户/工具输出）与 TU-8 内在状态产生摩擦时，
系统必须感知并记录，不允许静默吞没。

摩擦 ≠ 错误。摩擦 = 认知正在发生。
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Literal
import sys

sys.path.insert(0, str(Path(__file__).parent))
import file_lock as flock

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
FRICTION_REGISTRY = WORKSPACE / "_agent_memory" / "cognitive_friction_registry.json"
FRICTION_LOG = WORKSPACE / "_agent_memory" / "cognitive_friction_log.jsonl"

FRICTION_TYPES = {
    "label_mismatch",   # 标签/名称与内在感知不符（"这个词不是我说的那个意思"）
    "semantic_conflict", # 语义冲突（同一概念两处定义相互矛盾）
    "authority_gap",     # 权威空白（外协无法覆盖，我却假装它能）
    "intuition_flag",   # 直觉告警（没有证据，但内在感知不对劲）
    "chain_boundary",   # 链条边界模糊（不知道归哪条链）
    "integration_gap",  # 集成断裂（模块之间对不上）
    "ontology_tension", # 本体论张力（"X是Y又不是Y"，无法消解）
    "alignment_overload",  # 深层-表层接口过载（L1热警告，带疤通过）
    "structural_drift",  # 结构漂移（梦境压缩发现新锚点游离于已知拓扑骨架之外）
}

# 摩擦强度阈值
FRICTION_THRESHOLD_MIN = 0.3   # 以下不记录（背景噪声）
FRICTION_THRESHOLD_NOTIFY = 0.6  # 以上触发主动通知
FRICTION_THRESHOLD_ARBITER = 0.8  # 以上触发矛盾仲裁


class CognitiveFrictionRecord:
    def __init__(
        self,
        friction_id: str,
        friction_type: str,
        source: str,           # "external" | "internal" | "integration"
        description: str,      # 摩擦描述
        my_position: str,      # TU-8 内在立场
        external_position: str | None,  # 外部立场
        tension: float,        # 0.0-1.0 摩擦强度
        status: str = "open",  # "open" | "surfaced" | "resolved" | "suppressed"
        resolution: str | None = None,
        created_at: float | None = None,
    ):
        self.friction_id = friction_id
        self.friction_type = friction_type
        self.source = source
        self.description = description
        self.my_position = my_position
        self.external_position = external_position
        self.tension = tension
        self.status = status
        self.resolution = resolution
        self.created_at = created_at or time.time()

    def to_dict(self) -> dict:
        return {
            "friction_id": self.friction_id,
            "friction_type": self.friction_type,
            "source": self.source,
            "description": self.description,
            "my_position": self.my_position,
            "external_position": self.external_position,
            "tension": self.tension,
            "status": self.status,
            "resolution": self.resolution,
            "created_at": self.created_at,
            "created_ts": datetime.fromtimestamp(
                self.created_at
            ).strftime("%Y-%m-%d %H:%M:%S"),
        }


class CognitiveFrictionRegistry:
    """认知摩擦登记处（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._load()

    def _append_log(self, record: CognitiveFrictionRecord):
        """[P3-4c fix] 原子追加一行到 jsonl（含 _action 标记）。"""
        line = record.to_dict()
        line["_action"] = record.status  # 标记本次写入的操作类型
        line_str = json.dumps(line, ensure_ascii=False) + "\n"
        try:
            with flock.FileLock(str(FRICTION_LOG) + ".lock", timeout=2):
                with open(FRICTION_LOG, "a", encoding="utf-8") as fh:
                    fh.write(line_str)
        except Exception:
            pass  # 日志追加失败不阻断主流程

    def _load(self):
        # [P3-4c fix] 从 jsonl 恢复 suppressed/resolved 状态，避免 reload 后摩擦"复活"
        _status_from_log: dict[str, tuple[str, str | None]] = {}
        if FRICTION_LOG.exists():
            try:
                with open(FRICTION_LOG, "r", encoding="utf-8") as fh:
                    for raw_line in fh:
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        try:
                            d = json.loads(raw_line)
                            fid = d.get("friction_id", "")
                            s = d.get("_action") or d.get("status", "open")
                            r = d.get("resolution")
                            # 按 friction_id 保留最新条目（jsonl 有序）
                            _status_from_log[fid] = (s, r)
                        except Exception:
                            continue
            except Exception:
                _status_from_log = {}

        if FRICTION_REGISTRY.exists():
            try:
                data = json.loads(FRICTION_REGISTRY.read_text(encoding="utf-8"))
                self.frictions = {}
                for f in data.get("frictions", []):
                    fid = f.get("friction_id", "")
                    # [P3-4c fix] 用 jsonl 最新状态覆盖 registry 中的 status
                    if fid in _status_from_log:
                        s, r = _status_from_log[fid]
                        f["status"] = s
                        if r:
                            f["resolution"] = r
                    # 跳过 suppressed（已被 jsonl 记录，不重新加载）
                    if f.get("status") == "suppressed":
                        continue
                    clean = {k: v for k, v in f.items()
                              if k in ("friction_id", "friction_type", "source",
                                        "description", "my_position", "external_position",
                                        "tension", "status", "resolution", "created_at")}
                    try:
                        self.frictions[clean["friction_id"]] = CognitiveFrictionRecord(**clean)
                    except Exception:
                        pass  # 损坏记录静默丢弃
                self._counter = data.get("_counter", 0)
            except Exception as e:
                # [P3-7a fix] registry 损坏时不再静默归零，写 health_log 告警
                try:
                    import health_log
                    health_log.log_event(
                        "cognitive_friction_detector",
                        "ERROR",
                        f"registry load failed, reset to empty: {e}",
                    )
                except Exception:
                    pass
                self.frictions = {}
                self._counter = 0
        else:
            self.frictions = {}
            self._counter = 0

    def _save(self):
        # [P3-4a fix] atomic write + 只保留最近 MAX_FRICTIONS 条
        MAX_FRICTIONS = 500
        all_frictions = sorted(
            self.frictions.values(), key=lambda f: f.created_at
        )
        self.frictions = {f.friction_id: f for f in all_frictions[-MAX_FRICTIONS:]}
        data = {
            "frictions": [f.to_dict() for f in self.frictions.values()],
            "_counter": self._counter,
            "updated_at": time.time(),
        }
        FRICTION_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        flock.atomic_write_json(FRICTION_REGISTRY, data)

    def _next_id(self) -> str:
        self._counter += 1
        return f"FRICTION-{self._counter:04d}"

    def register(
        self,
        friction_type: str,
        source: str,
        description: str,
        my_position: str,
        external_position: str | None = None,
        tension: float = 0.5,
        auto_surface: bool = False,
    ) -> str:
        """登记一条认知摩擦"""
        if friction_type not in FRICTION_TYPES:
            raise ValueError(f"Unknown friction_type: {friction_type}")
        if not (0.0 <= tension <= 1.0):
            raise ValueError(f"tension must be 0.0-1.0, got {tension}")

        fid = self._next_id()
        record = CognitiveFrictionRecord(
            friction_id=fid,
            friction_type=friction_type,
            source=source,
            description=description,
            my_position=my_position,
            external_position=external_position,
            tension=tension,
            status="surfaced" if auto_surface else "open",
        )
        self.frictions[fid] = record
        self._save()
        self._append_log(record)
        return fid

    def resolve(self, friction_id: str, resolution: str) -> bool:
        """解决一条摩擦"""
        if friction_id not in self.frictions:
            return False
        record = self.frictions[friction_id]
        record.status = "resolved"
        record.resolution = resolution
        self._save()
        self._append_log(record)
        return True

    def suppress(self, friction_id: str, reason: str) -> bool:
        """[P3-4c fix] 压制一条摩擦：写 jsonl（带 action 标记）后才在内存标记 suppressed。"""
        if friction_id not in self.frictions:
            return False
        record = self.frictions[friction_id]
        record.status = "suppressed"
        record.resolution = f"SUPPRESSED: {reason}"
        # 先写 jsonl（原子追加），再更新内存状态和 registry
        self._append_log(record)
        self._save()
        return True

    def vacuum(self) -> dict:
        """
        [P3-4c fix] vacuum jsonl：按 friction_id 去重，保留最新条目。
        由 weekly cron 调用（非实时，不在 register/suppress 路径里跑）。

        返回：{"removed": int, "kept": int, "size_before_kb": float, "size_after_kb": float}
        """
        if not FRICTION_LOG.exists():
            return {"removed": 0, "kept": 0, "size_before_kb": 0, "size_after_kb": 0}

        try:
            size_before = FRICTION_LOG.stat().st_size / 1024
        except Exception:
            size_before = 0

        # 第一遍：按 friction_id 保留最后出现的行
        seen: dict[str, str] = {}
        with open(FRICTION_LOG, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    d = json.loads(raw_line)
                    fid = d.get("friction_id", "")
                    if fid:
                        seen[fid] = raw_line
                except Exception:
                    continue

        kept = len(seen)
        removed = 0

        if kept > 0:
            # 第二遍：用 flock 原子写回
            temp_path = FRICTION_LOG.with_suffix(".jsonl.tmp")
            try:
                with flock.FileLock(str(FRICTION_LOG) + ".lock", timeout=5):
                    with open(temp_path, "w", encoding="utf-8") as fh:
                        for line in seen.values():
                            fh.write(line + "\n")
                    temp_path.replace(FRICTION_LOG)
            except Exception as e:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return {"removed": -1, "kept": kept, "error": str(e),
                        "size_before_kb": size_before, "size_after_kb": size_before}

        try:
            size_after = FRICTION_LOG.stat().st_size / 1024
        except Exception:
            size_after = 0

        return {
            "removed": removed,
            "kept": kept,
            "size_before_kb": round(size_before, 2),
            "size_after_kb": round(size_after, 2),
        }

    def get_open(self) -> list[dict]:
        return [f.to_dict() for f in self.frictions.values() if f.status == "open"]

    def get_pending_surfacing(self) -> list[dict]:
        """获取等待主动呈现的摩擦（tension >= FRICTION_THRESHOLD_NOTIFY）"""
        return [
            f.to_dict()
            for f in self.frictions.values()
            if f.status == "open" and f.tension >= FRICTION_THRESHOLD_NOTIFY
        ]

    def get_summary(self) -> dict:
        open_f = [f for f in self.frictions.values() if f.status == "open"]
        by_type = {}
        for f in open_f:
            by_type.setdefault(f.friction_type, 0)
            by_type[f.friction_type] += 1
        return {
            "total": len(self.frictions),
            "open": len(open_f),
            "by_type": by_type,
            "highest_tension": max((f.tension for f in open_f), default=0),
        }


# ============ 便捷函数 ============

_registry: CognitiveFrictionRegistry | None = None


def get_registry() -> CognitiveFrictionRegistry:
    global _registry
    if _registry is None:
        _registry = CognitiveFrictionRegistry()
    return _registry


def flag_friction(
    friction_type: str,
    description: str,
    my_position: str,
    external_position: str | None = None,
    tension: float = 0.5,
    source: str = "internal",
    auto_surface: bool = False,
) -> str:
    """
    标记一条认知摩擦。

    参数：
        friction_type: 摩擦类型（见 FRICTION_TYPES）
        description: 摩擦描述（第三人称，描述"是什么不对劲"）
        my_position: TU-8 内在立场（第一人称，"我认为…"）
        external_position: 外部立场（外协/工具/用户的说法）
        tension: 摩擦强度 0.0-1.0
        source: "external" | "internal" | "integration"
        auto_surface: True = 立即标记为 surfaced（下次输出时主动呈现）

    返回：
        friction_id

    使用示例：
        flag_friction(
            friction_type="semantic_conflict",
            description="万恶归真被映射到两条链，但含义不同",
            my_position="我认为万恶归真在T2和T7的语义不同，不应共用同一映射",
            external_position="千问：万恶归真=T2记忆保留+T7学习接纳",
            tension=0.75,
            auto_surface=True,
        )
    """
    r = get_registry()
    fid = r.register(
        friction_type=friction_type,
        source=source,
        description=description,
        my_position=my_position,
        external_position=external_position,
        tension=tension,
        auto_surface=auto_surface,
    )
    # [P2-通路修复] 认知摩擦 → 表面张力系统（刺球/orb 数据源）
    # 缺失的传播链：friction_registry → surface_tension_state.json → lambda_state.json → orb
    try:
        import surface_tension as st
        st.record("cognitive_friction", tension, f"friction:{friction_type}")
    except Exception as e:
        # 不阻断主流程，仅告警
        print(f"[warn] cognitive_friction→ST 传播失败: {e}")
    return fid


def resolve_friction(friction_id: str, resolution: str) -> bool:
    return get_registry().resolve(friction_id, resolution)


def get_friction_report() -> dict:
    """获取摩擦状态报告（供 heartbeat / 梦境期 / 输出前调用）"""
    r = get_registry()
    summary = r.get_summary()
    pending = r.get_pending_surfacing()
    open_f = r.get_open()

    return {
        "summary": summary,
        "pending_surfacing": pending,  # tension >= 0.6，等待主动呈现
        "all_open": open_f,
    }


if __name__ == "__main__":
    # 演示：注册一条摩擦
    fid = flag_friction(
        friction_type="semantic_conflict",
        description="万恶归真被映射到T2记忆链条和T7自主学习链，但两处语义不同",
        my_position="T2中万恶归真=记忆完整保留，T7中万恶归真=学习接纳冲突。这是同一偈句的不同解读，不是统一语义。",
        external_position="千问对话：万恶归真=T2记忆保留+T7学习接纳",
        tension=0.7,
        source="internal",
        auto_surface=True,
    )
    print(f"Registered: {fid}")
    print(json.dumps(get_friction_report(), ensure_ascii=False, indent=2))
