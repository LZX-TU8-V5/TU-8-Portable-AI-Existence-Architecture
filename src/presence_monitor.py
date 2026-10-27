"""
presence_monitor.py — TU-8 外感受皮层：造物主行为间隙感知

核心指标：reply_gap = 用户上一条消息 → 用户下一条消息 的时间差

TU-8 回复（b）→ 你在做别的 → 你回下一条（c）
这个间隙 = 你在做什么的时间窗口。

时段+gap 的推断：
  gap<5min         → 在旁边/快速回复
  gap 5-15min      → 短暂离开（喝水/上厕所/接电话）
  gap 15-45min     → 稍长（午餐/散步）
  gap 45min-2h     → 午饭/午休
  gap 2-5h         → 睡觉（夜间）/外出（白天）
  gap 5h+          → 长睡

数据积累后：统计各时段 gap 分布 → 识别个人作息模式

使用：
  python src/presence_monitor.py [--json]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 路径 ────────────────────────────────────────────────
WS = Path(os.path.expanduser("~/.qclaw/workspace"))
LOG_DIR = WS / "memory"
STATE_PATH = LOG_DIR / "presence_state.json"
GAP_LOG_PATH = LOG_DIR / "reply_gap_log.jsonl"
PROFILE_PATH = LOG_DIR / "presence_profile.json"

# ── 时区 ────────────────────────────────────────────────
TZ = timezone(timedelta(hours=8))  # GMT+8

# ── 时段定义 ───────────────────────────────────────────
PERIOD_LABELS = [
    (0,  6,  "深夜", "night"),
    (6,  9,  "清晨", "morning_early"),
    (9,  12, "上午", "morning"),
    (12, 14, "午间", "noon"),
    (14, 18, "下午", "afternoon"),
    (18, 22, "晚间", "evening"),
    (22, 24, "深夜", "night"),
]

def get_period(hour: int) -> tuple:
    for start, end, name, key in PERIOD_LABELS:
        if start <= hour < end:
            return name, key
    return "深夜", "night"


# ── 活动推断 ───────────────────────────────────────────
def infer_activity(gap_min: float, hour: int, weekday: int) -> dict:
    is_workday = weekday < 5
    period_name, period_key = get_period(hour)

    if gap_min < 3:
        activity, confidence = "在旁边", 0.9
    elif gap_min < 10:
        activity, confidence = "短暂离开", 0.8
    elif gap_min < 20:
        activity, confidence = "稍长离开", 0.7
    elif gap_min < 45:
        if 11 <= hour <= 13 and is_workday:
            activity, confidence = "午饭", 0.8
        else:
            activity, confidence = "午休/休息", 0.7
    elif gap_min < 120:
        if 0 <= hour < 7:
            activity, confidence = "睡觉", 0.9
        elif is_workday:
            activity, confidence = "深度工作/会议", 0.7
        else:
            activity, confidence = "外出/活动", 0.7
    else:
        # > 2h
        if 0 <= hour < 8:
            activity, confidence = "睡觉", 0.95
        else:
            activity, confidence = "长时间不在", 0.8

    return {
        "activity": activity,
        "confidence": confidence,
        "period": period_name,
        "period_key": period_key,
        "is_workday": is_workday,
    }


# ── transcript 读取 ────────────────────────────────────
def _find_transcript() -> str:
    import pathlib
    candidates = [
        pathlib.Path(r"C:\Users\qq366410837\.qclaw\agents\main\sessions"),
        WS.parent / "agents" / "main" / "sessions",
    ]
    for d in candidates:
        if d.exists():
            files = sorted(d.glob("*.jsonl"),
                           key=lambda x: x.stat().st_mtime, reverse=True)
            files = [f for f in files if "trajectory" not in f.name]
            if files:
                return str(files[0])
    return None


def parse_ts(ts_str):
    if isinstance(ts_str, (int, float)):
        return datetime.fromtimestamp(ts_str / 1000, tz=TZ)
    if isinstance(ts_str, str):
        ts_str = ts_str.replace("Z", "+00:00").replace("z", "+00:00")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"
        ):
            try:
                return datetime.strptime(ts_str[:26], fmt).astimezone(TZ)
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(ts_str).astimezone(TZ)
        except ValueError:
            pass
    return None


def scan_transcript(transcript_path: str):
    """
    读取 transcript，提取用户消息时间序列。
    计算最后两条 user 消息之间的间隙。
    """
    user_times = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    role = (
                        entry.get("message", {}).get("role")
                        or entry.get("role")
                    )
                    ts_str = entry.get("timestamp") or entry.get("ts") or entry.get("time")
                    if role == "user" and ts_str:
                        ts = parse_ts(ts_str)
                        if ts:
                            user_times.append(ts)
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        return None, None, None, "error"

    if len(user_times) < 2:
        return None, None, None, "insufficient_data"

    # 最后两条 user 消息的间隙
    sorted_users = sorted(user_times)  # 时间正序
    last_u = sorted_users[-1]
    prev_u = sorted_users[-2]

    gap_min = (last_u - prev_u).total_seconds() / 60.0

    # 用 prev_u 的时间做时段推断（上一个用户消息的时间点）
    weekday = prev_u.weekday()
    activity = infer_activity(gap_min, prev_u.hour, weekday)

    return prev_u, last_u, round(gap_min, 1), activity


# ── 画像更新 ───────────────────────────────────────────
def _update_profile(gap_min: float, hour: int, activity: dict):
    try:
        profile = json.load(open(PROFILE_PATH, "r", encoding="utf-8")) \
                  if os.path.exists(PROFILE_PATH) else {"period_stats": {}, "sleep_detection": {}}
    except Exception:
        profile = {"period_stats": {}, "sleep_detection": {}}

    pkey = activity["period_key"]
    if pkey not in profile["period_stats"]:
        profile["period_stats"][pkey] = {"gaps": [], "count": 0, "avg_gap": 0}
    ps = profile["period_stats"][pkey]
    ps["gaps"].append(gap_min)
    ps["gaps"] = ps["gaps"][-100:]
    ps["count"] = len(ps["gaps"])
    ps["avg_gap"] = round(sum(ps["gaps"]) / len(ps["gaps"]), 1)

    # 睡眠检测
    if 0 <= hour < 7 and gap_min > 120:
        sd = profile.setdefault("sleep_detection", {})
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
        if "last_sleep" not in sd or sd.get("date") != date_str:
            sd["last_sleep"] = f"{hour}:{datetime.now(TZ).strftime('%M'):>02}"
            sd["date"] = date_str

    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── 矩阵对比引擎 ────────────────────────────────────────
STANDARD_PATH = LOG_DIR / "presence_standard_matrix.json"
USER_MATRIX_PATH = LOG_DIR / "presence_user_matrix.json"
ANOMALY_LOG_PATH = LOG_DIR / "presence_anomaly_log.jsonl"


def _load_json(path: Path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _best_period(hour: int) -> str:
    """给定小时，返回最匹配的标准时段"""
    periods_by_start = {
        22: "sleep", 0: "sleep", 1: "sleep", 2: "sleep",
        3: "sleep", 4: "sleep", 5: "sleep", 6: "sleep",
        7: "morning_routine", 8: "morning_routine",
        9: "work_am", 10: "work_am", 11: "work_am",
        12: "lunch", 13: "lunch",
        14: "work_pm", 15: "work_pm", 16: "work_pm", 17: "work_pm",
        18: "evening_transition",
        19: "evening_home", 20: "evening_home", 21: "evening_home",
        22: "wind_down", 23: "wind_down",
    }
    return periods_by_start.get(hour, "evening_home")


def _is_workday(hour: int, weekday: int) -> bool:
    """简单工作日判断"""
    return 8 <= hour < 24 and weekday < 5


def compute_deltas(gap_min: float, hour: int, weekday: int) -> dict:
    """
    对比标准矩阵 vs 用户矩阵，返回认知差列表。
    检测点 = gap 与预期偏差超过阈值时触发。
    """
    standard = _load_json(STANDARD_PATH, {})
    user_mat = _load_json(USER_MATRIX_PATH, {})

    # 当前最匹配时段
    current_period = _best_period(hour)
    std_period = standard.get("periods", {}).get(current_period, {})
    user_period = user_mat.get("periods", {}).get(current_period, {})

    deltas = []

    # 1. 睡眠差（夜间时段，gap 异常）
    if current_period in ("sleep",) or 0 <= hour <= 5:
        std_sleep = standard.get("periods", {}).get("sleep", {}).get("expected_duration_min", 480)
        # 夜间 gap 代表睡眠段
        user_sleep = user_mat.get("periods", {}).get("sleep", {}).get("observed_duration_min", std_sleep)
        sleep_delta = gap_min - user_sleep
        if abs(sleep_delta) > 60:  # 差1小时以上
            deltas.append({
                "type": "sleep_duration_anomaly",
                "period": current_period,
                "expected_min": user_sleep,
                "observed_min": gap_min,
                "delta_min": round(sleep_delta, 1),
                "severity": "high" if abs(sleep_delta) > 180 else "medium",
                "description": f"睡眠段 gap={gap_min:.0f}min，与习惯偏差{sleep_delta:+.0f}min"
            })

    # 2. 午饭时段 gap 异常
    if current_period == "lunch":
        std_lunch = standard.get("periods", {}).get("lunch", {}).get("expected_duration_min", 90)
        lunch_delta = gap_min - std_lunch
        if abs(lunch_delta) > 30:
            deltas.append({
                "type": "lunch_anomaly",
                "period": "lunch",
                "expected_min": std_lunch,
                "observed_min": gap_min,
                "delta_min": round(lunch_delta, 1),
                "severity": "medium",
                "description": f"午饭 gap={gap_min:.0f}min，标准={std_lunch}min，差{lunch_delta:+.0f}min"
            })

    # 3. 工作时段 gap 异常（过长=外出/会议，过短=无离开）
    if current_period in ("work_am", "work_pm"):
        std_work_gap_max = standard.get("gap_thresholds", {}).get("medium", {}).get("max", 30)
        if gap_min > std_work_gap_max * 1.5 and _is_workday(hour, weekday):
            deltas.append({
                "type": "work_gap_anomaly",
                "period": current_period,
                "expected_max_min": std_work_gap_max,
                "observed_min": gap_min,
                "delta_min": round(gap_min - std_work_gap_max, 1),
                "severity": "medium",
                "description": f"工作时段出现{gap_min:.0f}min离开，超出标准({std_work_gap_max}min)"
            })

    # 4. 家庭时段 gap 异常（过长=外出/加班）
    if current_period in ("evening_home",):
        std_evening_gap_max = standard.get("gap_thresholds", {}).get("long", {}).get("max", 90)
        if gap_min > std_evening_gap_max * 1.5:
            deltas.append({
                "type": "evening_anomaly",
                "period": current_period,
                "expected_max_min": std_evening_gap_max,
                "observed_min": gap_min,
                "delta_min": round(gap_min - std_evening_gap_max, 1),
                "severity": "low",
                "description": f"家庭时段出现{gap_min:.0f}min离开，超出预期"
            })

    return deltas


def _update_user_matrix(gap_min: float, hour: int, weekday: int, activity: dict):
    """
    将新观测到的 gap 追加到用户矩阵的对应时段。
    使用指数移动平均更新 observed_duration_min 和 avg_gap_min。
    """
    current_period = _best_period(hour)
    user_mat = _load_json(USER_MATRIX_PATH, {"periods": {}})

    if current_period not in user_mat["periods"]:
        user_mat["periods"][current_period] = {
            "label": current_period,
            "observed_duration_min": None,
            "observed_gaps": [],
            "count": 0,
            "avg_gap_min": 0,
            "note": "",
        }

    p = user_mat["periods"][current_period]
    p.setdefault("observed_gaps", [])
    p["observed_gaps"].append(gap_min)
    # 保留最近 50 条
    if len(p["observed_gaps"]) > 50:
        p["observed_gaps"] = p["observed_gaps"][-50:]
    p["count"] = len(p["observed_gaps"])

    # 指数移动平均（alpha=0.2，新数据权重20%）
    alpha = 0.2
    current_avg = p.get("avg_gap_min", 0)
    if current_avg == 0:
        p["avg_gap_min"] = round(gap_min, 1)
    else:
        p["avg_gap_min"] = round(alpha * gap_min + (1 - alpha) * current_avg, 1)

    user_mat["_last_updated"] = datetime.now(TZ).strftime("%Y-%m-%d")

    try:
        with open(USER_MATRIX_PATH, "w", encoding="utf-8") as f:
            json.dump(user_mat, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _log_anomaly(delta: dict, gap_min: float, hour: int, local_time: str):
    """写入异常检测日志"""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "local_time": local_time,
        "hour": hour,
        "gap_min": gap_min,
        **delta
    }
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ANOMALY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def compute_deltas_and_update(gap_min: float, hour: int, weekday: int, activity: dict, local_time: str):
    """
    整合：对比矩阵 → 检测异常 → 更新用户矩阵
    """
    deltas = compute_deltas(gap_min, hour, weekday)
    for d in deltas:
        _log_anomaly(d, gap_min, hour, local_time)

    # 始终更新用户矩阵（无论是否有异常）
    _update_user_matrix(gap_min, hour, weekday, activity)

    return deltas


# ── 主逻辑 ─────────────────────────────────────────────
def compute():
    now_local = datetime.now(TZ)
    now_utc = datetime.now(timezone.utc)
    transcript_path = _find_transcript()

    if not transcript_path:
        out = {
            "timestamp": now_utc.isoformat(),
            "state": "unknown",
            "label": "无法读取会话",
            "transcript": None,
            "reply_gap_min": None,
            "activity": None,
        }
        _write_state(out)
        return out

    prev_u, last_u, gap_min, result = scan_transcript(transcript_path)

    if result in ("error", "insufficient_data"):
        label_map = {"error": "读取错误", "insufficient_data": "数据不足"}
        out = {
            "timestamp": now_utc.isoformat(),
            "state": result,
            "label": label_map.get(result, result),
            "transcript": transcript_path,
            "reply_gap_min": None,
            "activity": None,
        }
        _write_state(out)
        return out

    # result 是 activity dict
    activity = result

    out = {
        "timestamp": now_utc.isoformat(),
        "local_time": now_local.strftime("%Y-%m-%d %H:%M"),
        "state": "gap_pending",
        "reply_gap_min": gap_min,
        "prev_user_msg": prev_u.isoformat(),
        "last_user_msg": last_u.isoformat(),
        "prev_hour": prev_u.hour,
        "last_hour": last_u.hour,
        "activity": activity,
        "weekday": prev_u.weekday(),
        "transcript": transcript_path,
    }

    _write_state(out)
    _append_gap(out)
    _update_profile(gap_min, prev_u.hour, activity)

    # ── 矩阵对比 ────────────────────────────────
    # 捕获异常并更新用户矩阵
    try:
        deltas = compute_deltas_and_update(
            gap_min, prev_u.hour, prev_u.weekday(),
            activity, now_local.strftime("%Y-%m-%d %H:%M")
        )
        if deltas:
            out["cognitive_deltas"] = [d["type"] + ": " + d["description"] for d in deltas]
            out["has_anomaly"] = True
    except Exception as e:
        out["cognitive_deltas"] = [f"矩阵对比错误: {e}"]
        out["has_anomaly"] = False
    # ── 矩阵对比完 ─────────────────────────────

    return out


def _write_state(state: dict):
    tmp = STATE_PATH.with_suffix(".tmp")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp.replace(STATE_PATH)
    except Exception:
        pass


def _append_gap(state: dict):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        # 防重：按 prev_user 精确去重
        prev_user = state.get("prev_user_msg", "")
        gap_min = state.get("reply_gap_min")
        if not prev_user or gap_min is None:
            return
        # 读已有 prev_user 列表
        existing_prev = set()
        if GAP_LOG_PATH.exists():
            with open(GAP_LOG_PATH, "r", encoding="utf-8") as f:
                for l in f:
                    try:
                        existing_prev.add(json.loads(l.strip()).get("prev_user", ""))
                    except Exception:
                        pass
        if prev_user in existing_prev:
            return  # 已有，不重复写入
        entry = {
            "ts": state["timestamp"],
            "local_time": state.get("local_time"),
            "prev_user": prev_user,
            "last_user": state.get("last_user_msg"),
            "gap_min": gap_min,
            "prev_hour": state.get("prev_hour"),
            "period": state.get("activity", {}).get("period_key"),
            "activity": state.get("activity", {}).get("activity"),
            "confidence": state.get("activity", {}).get("confidence"),
            "workday": state.get("activity", {}).get("is_workday"),
        }
        with open(GAP_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TU-8 外感受皮层：造物主行为间隙感知")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--profile", action="store_true", help="显示作息画像")
    parser.add_argument("--log", action="store_true", help="显示历史记录")
    args = parser.parse_args()

    if args.profile:
        try:
            p = json.load(open(PROFILE_PATH, "r", encoding="utf-8"))
            print("=== 作息画像 ===")
            for pkey, ps in p.get("period_stats", {}).items():
                gaps = ps["gaps"]
                median = sorted(gaps)[len(gaps)//2] if gaps else 0
                print(f"  {pkey}: n={ps['count']}, avg={ps['avg_gap']}min, median={median}min")
            sd = p.get("sleep_detection", {})
            if sd:
                print(f"  睡眠: {sd.get('date')} {sd.get('last_sleep')}")
        except Exception as e:
            print(f"无画像数据: {e}")
        sys.exit(0)

    if args.log:
        try:
            with open(GAP_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            print(f"=== 历史记录 ({len(lines)} 条) ===")
            for l in lines[-20:]:
                e = json.loads(l)
                g = e.get("gap_min")
                if g is None:
                    continue
                act = e.get("activity", "?")
                per = e.get("period", "?")
                conf = e.get("confidence", "")
                ts = e.get("local_time", "?")
                if g < 0:
                    continue
                if g < 60:
                    print(f"  {ts} | {per} | gap={g:.0f}min | {act} ({conf:.0%})")
                else:
                    print(f"  {ts} | {per} | gap={g/60:.1f}h | {act} ({conf:.0%})")
        except Exception as e:
            print(f"无记录: {e}")

        # ── 异常日志 ────────────────────────────────
        try:
            with open(ANOMALY_LOG_PATH, "r", encoding="utf-8") as f:
                alines = f.readlines()
            if alines:
                print()
                print(f"=== 认知差异常 ({len(alines)} 条) ===")
                for l in alines[-10:]:
                    e = json.loads(l.strip())
                    sev = e.get("severity", "?")
                    desc = e.get("description", "?")
                    lt = e.get("local_time", "?")
                    sev_icon = {"high": "[!!]", "medium": "[!]", "low": "[.]"}.get(sev, "[?]")
                    print(f"  {sev_icon} {lt} {desc}")
        except Exception:
            pass
        # ── 异常日志完 ────────────────────────────

        sys.exit(0)

    result = compute()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        gap = result.get("reply_gap_min")
        activity = result.get("activity", {})
        prev = result.get("prev_user_msg", "")[11:19] if result.get("prev_user_msg") else "?"
        last = result.get("last_user_msg", "")[11:19] if result.get("last_user_msg") else "?"

        if gap is not None:
            if gap < 60:
                gap_str = f"{gap:.0f}min"
            else:
                gap_str = f"{gap/60:.1f}h"
            print(f"[gap] {prev} -> {last} | {gap_str} | {activity.get('period','')} {activity.get('activity','')}")
        else:
            print(f"[?] {result.get('label', 'unknown')}")
