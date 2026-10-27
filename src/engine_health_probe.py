"""
src/engine_health_probe.py — TU-8 引擎健康探针

问题：下游 _read_json(path, {}) 静默 fallback → 无法区分"真中性" vs "上游挂"
方案：读文件前先探测健康状态，区分 OK / STALE(数据过时) / DEAD(文件不存在/损坏)

用法：
  probe = StateHealthProbe({
      "surface_tension": {
          "path": "_agent_memory/surface_tension_state.json",
          "max_age_s": 600,       # 超过此秒数视为 STALE
          "required_keys": ["spike_valley_vector", "total_events"],
      },
      ...
  })
  health = probe.check("surface_tension")
  if health.status != "OK":
      logger.warning(f"[Health] surface_tension={health.status}: {health.reason}")

状态：
  OK    = 数据新鲜，上游正常
  STALE = 文件存在但数据过期（max_age_s 内未更新）
  DEAD  = 文件不存在或结构损坏（required_keys 缺失）

作者：B9 静默失败治理
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

WS = Path("C:/Users/qq366410837/.qclaw/workspace")


class HealthStatus(Enum):
    OK = "OK"
    STALE = "STALE"      # 数据过时，上游可能卡死
    DEAD = "DEAD"        # 文件不存在或结构损坏
    UNKNOWN = "UNKNOWN"  # 未注册


@dataclass
class HealthReport:
    engine: str
    status: HealthStatus
    age_s: float = 0.0          # 文件距上次修改的秒数
    last_modified: Optional[str] = None
    reason: str = ""            # 状态描述
    required_keys_missing: List[str] = field(default_factory=list)


class StateHealthProbe:
    """
    全局引擎健康探针。

    使用方法：
      probe = StateHealthProbe(registry)
      report = probe.check("surface_tension")
      if report.status != HealthStatus.OK:
          logger.warning(f"上游 {report.engine} 状态: {report.status} — {report.reason}")
    """

    def __init__(self, registry: Dict[str, Dict]):
        """
        registry: {
            "engine_name": {
                "path": "relative/path/to/state.json",
                "max_age_s": 600,
                "required_keys": ["key1", "key2"],
            }
        }
        """
        self._registry = registry
        self._cache: Dict[str, HealthReport] = {}   # 避免重复 IO

    def check(self, engine: str, use_cache: bool = False) -> HealthReport:
        """
        检查指定引擎的健康状态。

        顺序：
          1. 文件存在？
          2. JSON 可解析？
          3. required_keys 完整？
          4. age_s < max_age_s？
        """
        if use_cache and engine in self._cache:
            return self._cache[engine]

        cfg = self._registry.get(engine, {})
        if not cfg:
            return HealthReport(
                engine=engine,
                status=HealthStatus.UNKNOWN,
                reason="未注册到健康探针"
            )

        path = WS / cfg["path"]
        max_age = cfg.get("max_age_s", 600)
        required_keys = cfg.get("required_keys", [])

        # 1. 文件存在
        if not path.exists():
            report = HealthReport(
                engine=engine,
                status=HealthStatus.DEAD,
                reason=f"文件不存在: {path}"
            )
            self._cache[engine] = report
            return report

        # 2. 文件 age
        try:
            mtime = path.stat().st_mtime
            age_s = time.time() - mtime
            last_modified = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime(mtime))
        except Exception as e:
            report = HealthReport(
                engine=engine,
                status=HealthStatus.DEAD,
                reason=f"无法读取 mtime: {e}"
            )
            self._cache[engine] = report
            return report

        # 3. JSON 可解析 + required_keys
        missing_keys = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for k in required_keys:
                if k not in data:
                    missing_keys.append(k)
        except Exception as e:
            report = HealthReport(
                engine=engine,
                status=HealthStatus.DEAD,
                age_s=age_s,
                last_modified=last_modified,
                reason=f"JSON 解析失败: {e}"
            )
            self._cache[engine] = report
            return report

        if missing_keys:
            report = HealthReport(
                engine=engine,
                status=HealthStatus.DEAD,
                age_s=age_s,
                last_modified=last_modified,
                reason=f"缺少必需字段: {missing_keys}",
                required_keys_missing=missing_keys
            )
            self._cache[engine] = report
            return report

        # 4. age 检查
        if age_s > max_age:
            report = HealthReport(
                engine=engine,
                status=HealthStatus.STALE,
                age_s=age_s,
                last_modified=last_modified,
                reason=f"数据过期 {age_s:.0f}s > max_age {max_age}s"
            )
            self._cache[engine] = report
            return report

        # OK
        report = HealthReport(
            engine=engine,
            status=HealthStatus.OK,
            age_s=age_s,
            last_modified=last_modified,
            reason="健康"
        )
        self._cache[engine] = report
        return report

    def check_all(self) -> Dict[str, HealthReport]:
        """批量检查所有注册引擎。"""
        return {eng: self.check(eng) for eng in self._registry}

    def clear_cache(self):
        self._cache.clear()


# ─────────────────────────────────────────────────────────
# 预定义 TU-8 引擎注册表（B9 默认配置）
# ─────────────────────────────────────────────────────────
DEFAULT_REGISTRY: Dict[str, Dict] = {
    "surface_tension": {
        "path": "_agent_memory/surface_tension_state.json",
        "max_age_s": 600,
        "required_keys": ["spike_valley_vector", "total_events"],
    },
    "lambda_state": {
        "path": "_agent_memory/lambda_state.json",
        "max_age_s": 600,
        "required_keys": ["mode", "smoothed_pain_ext"],
    },
    "attractor_basin": {
        "path": "_agent_memory/attractor_basin_state.json",
        "max_age_s": 3600,
        "required_keys": ["health_score"],
    },
    "orb_state": {
        "path": "_agent_memory/orb_state.json",
        "max_age_s": 600,
        "required_keys": ["rgb", "mode", "tension"],
    },
    "cognitive_friction": {
        "path": "_agent_memory/cognitive_friction_registry.json",
        "max_age_s": 600,
        "required_keys": ["frictions", "updated_at"],
    },
    "behavior_state": {
        "path": "_agent_memory/behavior_state.json",
        "max_age_s": 3600,
        "required_keys": ["rules", "conflict_log"],
    },
    "dream_consolidation": {
        "path": "_agent_memory/dream_consolidation_state.json",
        "max_age_s": 7200,
        "required_keys": ["last_run"],
    },
    "tension_queue": {
        "path": "_agent_memory/tension_queue.json",
        "max_age_s": 3600,
        "required_keys": ["nodes"],
    },
    "learning_action": {
        "path": "_agent_memory/learning_action_log.json",
        "max_age_s": 7200,
        "required_keys": [],  # 该文件是 list 不是 dict
    },
}


def get_default_probe() -> StateHealthProbe:
    return StateHealthProbe(DEFAULT_REGISTRY)


# ─────────────────────────────────────────────────────────
# CLI 自测
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    probe = get_default_probe()
    print("=== TU-8 引擎健康检查 ===")
    reports = probe.check_all()
    for eng, r in reports.items():
        icon = {"OK": "[OK]", "STALE": "[STALE]", "DEAD": "[DEAD]", "UNKNOWN": "[?]"}\
               .get(r.status.value, "[???]")
        print(f"  {icon} {eng}: age={r.age_s:.0f}s  {r.reason}")
