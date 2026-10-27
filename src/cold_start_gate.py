#!/usr/bin/env python3
"""
cold_start_gate.py
TU-8 冷启动 Gate — 检查会话模式与认知就绪度
输出 JSON 到 security/session_mode.json
"""

import json
import os
import sys
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


def compute_cognitive_readiness(mode: str, gap_seconds: float) -> dict | None:
    """生成认知简报"""
    if mode == "FULL":
        return None
    import datetime
    hours = gap_seconds / 3600
    recovery_depth = "FULL" if hours > 72 else "RESTRICTED"
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
        )
    }


def main():
    now = time.time()

    # ── Step 0：日期上下文注入 ──────────────────────────────────────
    # 必须最早执行，供所有后续模块感知当前日期
    # 优先级：开机时间文件 > inject_date_context（兜底）
    BOOT_TS_FILE = WORKSPACE / "_agent_memory" / "boot_timestamp.json"
    import datetime as _dt

    def _read_boot_timestamp():
        """读开机时间文件，若不存在或解析失败返回 None"""
        if not BOOT_TS_FILE.exists():
            return None
        try:
            with open(BOOT_TS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("boot_time", data.get("boot_unix"))
        except Exception:
            return None

    def _fetch_network_time():
        """拉取网络时间（阿里云 NTP）作校准参考"""
        try:
            import socket
            # 阿里云 NTP 服务器
            ntp_server = "time.aliyun.com"
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(3)
            # NTP 协议包
            NTP_PACKET = b'\x1b' + 47 * b'\0'
            client.sendto(NTP_PACKET, (ntp_server, 123))
            data, _ = client.recvfrom(1024)
            client.close()
            # 解析 NTP 时间戳（第 40-43 字节）
            from struct import unpack
            t = unpack("!I", data[40:44])[0]
            ntp_time = _dt.datetime.utcfromtimestamp(t - 2208988800)
            # 转换为本地时间
            local = ntp_time + _dt.timedelta(hours=8)
            return local.strftime("%Y-%m-%d")
        except Exception:
            return None

    boot_ts_str = _read_boot_timestamp()
    now = _dt.datetime.now()
    now_date = now.strftime("%Y-%m-%d")
    now_weekday = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][now.weekday()]

    # 判断是否隔天
    is_new_day = False
    date_ctx = {
        "current_date": now_date,
        "current_time": now.strftime("%H:%M"),
        "day_of_week": now_weekday,
        "is_new_day": False,
        "days_since_last_boot": 0,
        "last_boot_date": now_date,
        "boot_source": "inject_fallback",
    }

    if boot_ts_str:
        try:
            # 尝试解析 ISO 格式
            if "T" in str(boot_ts_str):
                boot_date = str(boot_ts_str)[:10]
            else:
                boot_date = str(boot_ts_str)[:10]
            is_new_day = (boot_date != now_date)
            # 计算间隔天数
            try:
                b = _dt.datetime.strptime(boot_date, "%Y-%m-%d")
                days_since = (now.date() - b.date()).days
            except Exception:
                days_since = 0
            date_ctx.update({
                "is_new_day": is_new_day,
                "days_since_last_boot": days_since,
                "last_boot_date": boot_date,
                "boot_source": "boot_timestamp_file",
            })
        except Exception as e:
            date_ctx["_boot_parse_error"] = str(e)

    # 若隔天，拉取网络时间校准
    if is_new_day:
        net_date = _fetch_network_time()
        if net_date and net_date != now_date:
            # 系统时间与网络时间不符，以网络时间为准
            date_ctx["system_clock_error"] = True
            date_ctx["current_date"] = net_date
            date_ctx["network_date"] = net_date
            date_ctx["is_new_day"] = True
        elif net_date:
            date_ctx["network_date_verified"] = net_date

    last_active = get_last_active_time()

    if last_active == 0:
        mode = "FULL"
        reason = "no_history"
        gap_seconds = 0
    else:
        gap_seconds = now - last_active
        mode, reason = compute_mode(gap_seconds)

    verification_needed = mode in ("RESTRICTED", "READONLY")

    result = {
        "mode": mode,
        "result": "AUTO_PASS",
        "reason": reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00", time.gmtime()),
        "session_gap_seconds": gap_seconds,
        "date_context": date_ctx,  # 供 SOUL.md / AGENTS.md 感知当前日期
        "gap_severity": "normal" if mode == "FULL" else ("moderate" if mode == "RESTRICTED" else "severe"),
        "hostname": os.environ.get("COMPUTERNAME", "UNKNOWN"),
        "workspace_hash": _workspace_hash(),
        "cognitive_readiness": compute_cognitive_readiness(mode, gap_seconds),
        "verification_needed": verification_needed,
        "verification_message": (
            "会话间隔过长，需要验证身份" if verification_needed
            else None
        )
    }

    # 启动一致性门（L2 防护）：身首契约对账，best-effort 不阻断冷启动
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import startup_consistency_gate as scg
        result["interoception_consistency"] = scg.run()
    except Exception as e:
        result["interoception_consistency"] = {"status": "error", "reasons": [str(e)]}

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
