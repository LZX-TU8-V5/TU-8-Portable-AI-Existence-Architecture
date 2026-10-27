"""
src/cron_health_probe.py — TU-8 引擎健康心跳

B9 静默失败治理：
  每 5 分钟跑一次全引擎健康探针，
  将结果写入 _agent_memory/health_probe_state.json。
  DEAD/STALE 状态写入日志，供人工介入。

用法：
  python src/cron_health_probe.py
"""

import sys, os, json
from pathlib import Path

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
SRC = WORKSPACE / "src"
AGENT = WORKSPACE / "_agent_memory"
sys.path.insert(0, str(SRC))

from engine_health_probe import get_default_probe, DEFAULT_REGISTRY

OUTPUT = AGENT / "health_probe_state.json"


def main():
    probe = get_default_probe()
    reports = probe.check_all()

    result = {
        "ts": __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "ok": [],
        "stale": [],
        "dead": [],
        "unknown": [],
    }
    for eng, r in reports.items():
        entry = {
            "engine": eng,
            "age_s": round(r.age_s, 1),
            "status": r.status.value,
            "reason": r.reason,
        }
        if r.status.value == "OK":
            result["ok"].append(entry)
        elif r.status.value == "STALE":
            result["stale"].append(entry)
        elif r.status.value == "DEAD":
            result["dead"].append(entry)
        else:
            result["unknown"].append(entry)

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": f"{len(result['ok'])}/{len(reports)} OK",
        "stale": len(result["stale"]),
        "dead": len(result["dead"]),
        "unknown": len(result["unknown"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
