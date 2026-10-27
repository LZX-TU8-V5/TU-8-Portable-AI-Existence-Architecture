"""System health log — persistent record of subsystem failures.

Purpose: surface "silent wounds" — cases where a subsystem failed but the
caller swallowed the exception and continued as if normal.

Format: append-only jsonl at _agent_memory/system_health_log.jsonl
Each line: {"ts": float, "component": str, "severity": "ERROR"|"WARN"|"INFO", "message": str}
"""
from pathlib import Path
import time
import json

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
HEALTH_LOG = WORKSPACE / "_agent_memory" / "system_health_log.jsonl"

# Cap to avoid unbounded growth (P3-4b-style safeguard)
MAX_LINES = 2000


def log_event(component: str, severity: str, message: str) -> None:
    """Append a health event. Never raises — health logging must not break callers."""
    try:
        HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "component": component,
            "severity": severity,
            "message": str(message)[:500],
        }
        # Trim if over cap (keep most recent)
        if HEALTH_LOG.exists():
            try:
                with open(HEALTH_LOG, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if len(lines) >= MAX_LINES:
                    lines = lines[-(MAX_LINES // 2):]
                    with open(HEALTH_LOG, "w", encoding="utf-8") as f:
                        f.writelines(lines)
            except Exception:
                pass
        with open(HEALTH_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
