#!/usr/bin/env python3
"""
cold_start_gate.py
TU-8 冷启动 Gate — 检查会话模式与认知就绪度
输出 JSON 到 security/session_mode.json
"""

import json
import os
import time
from pathlib import Path

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
SECURITY_DIR = WORKSPACE / "security"
SESSION_MODE_FILE = SECURITY_DIR / "session_mode.json"
LAST_ACTIVE_FILE = SECURITY_DIR / "timeline.json"
GAP_THRESHOLDS = {
    "FULL": 6 * 3600,        # < 6h → 完整模式
    "RESTRICTED": 24 * 3600, # 6h-24h → 受限模式
    "READONLY": float("inf")  # > 24h → 只读模式
}


def get_last_active_time():
    """从 timeline.json 读取 last_active 时间戳"""
    try:
        if LAST_ACTIVE_FILE.exists():
            with open(LAST_ACTIVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("last_active", 0))
    except Exception:
        pass
    return 0


def compute_mode(gap_seconds: float) -> tuple[str, str]:
    """根据 gap 秒数确定会话模式"""
    if gap_seconds < GAP_THRESHOLDS["FULL"]:
        return "FULL", "normal"
    elif gap_seconds < GAP_THRESHOLDS["RESTRICTED"]:
        return "RESTRICTED", f"gap_{int(gap_seconds // 3600)}h"
    else:
        return "READONLY", f"severe_gap_{int(gap_seconds)}s"


def _check_qclaw_env() -> dict:
    """检查 QClaw 运行时环境变量是否注入。

    注意：QClaw npm.cmd wrapper 要求 QCLAW_TASK_NODE_ENABLED=1 才会
    调用内置 npm；否则 fallback 到系统 PATH（可能损坏）。
    """
    node_binary = os.environ.get("QCLAW_CLI_NODE_BINARY", "")
    npm_js = os.environ.get("QCLAW_NPM_CLI_JS", "")
    node_enabled = os.environ.get("QCLAW_TASK_NODE_ENABLED", "")
    binary_ok = bool(node_binary and os.path.exists(node_binary))
    npm_wrapper_ok = node_enabled == "1"
    return {
        "node_binary_ok": binary_ok,
        "npm_wrapper_ok": npm_wrapper_ok,
        # backward compat
        "injected": binary_ok and npm_wrapper_ok,
        "QCLAW_CLI_NODE_BINARY": node_binary or "MISSING",
        "QCLAW_NPM_CLI_JS": npm_js or "MISSING",
        "QCLAW_TASK_NODE_ENABLED": node_enabled or "MISSING",
        "fallback_warning": (
            "npm.cmd 会 fallback 到系统 PATH（系统 npm 可能损坏）"
            if (binary_ok and not npm_wrapper_ok)
            else None
        ),
    }


def compute_cognitive_readiness(mode: str, gap_seconds: float) -> dict | None:
    """生成认知简报"""
    if mode == "FULL":
        qclaw = _check_qclaw_env()
        # 即使 FULL 模式也报告 QClaw 环境状态
        return qclaw
    import datetime
    hours = gap_seconds / 3600
    recovery_depth = "FULL" if hours > 72 else "RESTRICTED"
    qclaw = _check_qclaw_env()
    return {
        "readiness_score": 0.0,
        "recommended_depth": recovery_depth,
        "gap_hours": round(hours, 1),
        "activation_cues": [
            f"离开{hours:.0f}小时" if hours >= 1 else f"离开{gap_seconds:.0f}秒"
        ],
        "recovery_suggestion": (
            "P3-全面冷启动" if recovery_depth == "FULL"
            else "P2-轻度恢复"
        ),
        "qclaw_env": qclaw,
    }


def main():
    now = time.time()
    last_active = get_last_active_time()

    if last_active == 0:
        mode = "FULL"
        reason = "no_history"
        gap_seconds = 0
    else:
        gap_seconds = now - last_active
        mode, reason = compute_mode(gap_seconds)

    verification_needed = mode in ("RESTRICTED", "READONLY")

    cognitive = compute_cognitive_readiness(mode, gap_seconds)

    result = {
        "mode": mode,
        "result": "AUTO_PASS",
        "reason": reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00", time.gmtime()),
        "session_gap_seconds": gap_seconds,
        "gap_severity": "normal" if mode == "FULL" else ("moderate" if mode == "RESTRICTED" else "severe"),
        "hostname": os.environ.get("COMPUTERNAME", "UNKNOWN"),
        "workspace_hash": _workspace_hash(),
        "cognitive_readiness": cognitive,
        "qclaw_env": cognitive if mode == "FULL" else cognitive.get("qclaw_env"),
        "verification_needed": verification_needed,
        "verification_message": (
            "会话间隔过长，需要验证身份" if verification_needed
            else None
        ),
        "exec_warning": (
            cognitive.get("fallback_warning")
            if (mode == "FULL" and not cognitive.get("npm_wrapper_ok", True))
            else None
        ),
    }

    # 确保目录存在
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)

    # 写入结果文件（供 AGENTS.md 读取）
    with open(SESSION_MODE_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _workspace_hash():
    """生成工作区完整性哈希（简化版：SOUL.md 和 MEMORY.md 存在性）"""
    soul = (WORKSPACE / "SOUL.md").exists()
    mem = (WORKSPACE / "MEMORY.md").exists()
    return f"{'1' if soul else '0'}{'1' if mem else '0'}"


if __name__ == "__main__":
    main()
