#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session_watchdog.py — TU-8 会话健康看门狗 v2

问题背景
--------
modelroute -> qclaw-llm-provider 上游链路存在系统性不可靠：
  - "LLM idle timeout (120s): no response from model"  (模型 120s 未回，常成对=重试也超时)
  - "Request was aborted."                              (传输层中止)
一次失败会在 transcript 留下 content=[] 的空 assistant 回合；更糟的是
failed 会话会「吞掉」后续用户输入（写入 transcript 但不再处理）。

本脚本扫描所有会话，只识别【真正卡死】的会话并给恢复建议：
  A. status == "failed"（来自 sessions.json）
  B. 最后一轮 assistant 失败/空，且其后仍有未被处理的用户输入（吞输入）
历史上有过空回合但后来正常恢复的会话不报（非卡死）。

另：若会话 contextTokens 极大（>200k）会标注为超时/abort 的可能诱因。

用法：
  python src/session_watchdog.py            # 打印报告
  python src/session_watchdog.py --write    # 同时写入 memory/session_watchdog_report.md
  python src/session_watchdog.py --json     # 输出 JSON
"""
import os
import json
import glob
import argparse
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
SESS_DIR = os.path.join(HOME, ".qclaw", "agents", "main", "sessions")
SESSIONS_JSON = os.path.join(SESS_DIR, "sessions.json")
TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

ABORT_SIGNATURES = ("abort", "idle timeout", "no response from model")


def load_sessions_index():
    """sessions.json 顶层 key=会话key，value 含 sessionId(=文件名)/label/status/contextTokens。"""
    if not os.path.exists(SESSIONS_JSON):
        return {}
    try:
        data = json.load(open(SESSIONS_JSON, encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, dict) and v.get("sessionId"):
                out[v["sessionId"]] = v
    return out


def is_failed_turn(msg):
    if not isinstance(msg, dict):
        return False, None
    content = msg.get("content")
    stop = msg.get("stopReason")
    em = str(msg.get("errorMessage", "") or "")
    if stop == "aborted" or any(s in em.lower() for s in ABORT_SIGNATURES):
        return True, (em or f"stopReason={stop}")
    empty = (content in (None, "", []) or
             (isinstance(content, list) and len(content) == 0))
    if empty:
        return True, "empty_content"
    return False, None


def extract_user_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c
                        if isinstance(b, dict) and b.get("type") == "text").strip()
    return ""


def scan_session(fp, index):
    base = os.path.basename(fp)
    key = os.path.splitext(base)[0]
    meta = index.get(key, {})
    status = meta.get("status", "unknown")
    label = meta.get("label") or key[-6:]
    ctx = meta.get("contextTokens", 0)

    try:
        lines = open(fp, encoding="utf-8").read().splitlines()
    except Exception:
        return None

    failed_turns = []
    last_assistant_idx = -1
    pending_user = []  # 最近一次失败回合之后、且其后无正常 assistant 响应的用户输入

    for i, ln in enumerate(lines):
        try:
            o = json.loads(ln)
        except Exception:
            continue
        m = o.get("message", {})
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "assistant":
            bad, reason = is_failed_turn(m)
            if bad:
                failed_turns.append((i, reason))
                pending_user = []
            else:
                last_assistant_idx = i
                pending_user = []
        elif role == "user":
            if failed_turns and i > failed_turns[-1][0]:
                pending_user.append((i, extract_user_text(m)))

    swallowed = pending_user if (failed_turns and last_assistant_idx < failed_turns[-1][0]) else []
    stuck = (status == "failed") or bool(swallowed)
    if not stuck:
        return None

    return {
        "key": key,
        "label": label,
        "status": status,
        "failed_turn_count": len(failed_turns),
        "last_fail_reason": failed_turns[-1][1] if failed_turns else None,
        "swallowed_user_msgs": [t for (_, t) in swallowed][-5:],
        "swallowed_count": len(swallowed),
        "contextTokens": ctx,
        "big_ctx": ctx > 200_000,
        "last_fail_line": failed_turns[-1][0] if failed_turns else None,
    }


SEV_RANK = {"failed+吞输入": 0, "failed": 1, "吞输入": 2}


def severity(r):
    if r["status"] == "failed" and r["swallowed_count"] > 0:
        return "failed+吞输入"
    if r["status"] == "failed":
        return "failed"
    return "吞输入"


def build_report(results, as_json=False):
    if as_json:
        return json.dumps(results, ensure_ascii=False, indent=2)
    if not results:
        return "✅ 未发现卡死/失败的会话。所有会话健康。"
    lines = ["# 会话健康看门狗报告 (v2)",
             "",
             f"> 扫描时间：{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} (Asia/Shanghai)",
             f"> 命中卡死/失败会话：**{len(results)}** 个",
             ""]
    lines.append("| 严重程度 | 会话 | 状态 | 失败回合 | 最后失败原因 | 被吞输入 | 上下文 | 最近被吞消息 |")
    lines.append("|---------|------|------|---------|-------------|---------|------|------------|")
    for r in results:
        sev = severity(r)
        ctx = f"{r['contextTokens']//1000}k" if r["contextTokens"] else "?"
        if r["big_ctx"]:
            ctx += " ⚠️"
        last = (r["swallowed_user_msgs"][-1] if r["swallowed_user_msgs"] else "—")
        last = (last[:30] + "…") if len(last) > 31 else last
        lines.append(
            f"| {sev} | {r['label']} (`{r['key'][-6:]}`) | {r['status']} | "
            f"{r['failed_turn_count']} | {r['last_fail_reason']} | "
            f"{r['swallowed_count']} | {ctx} | {last} |"
        )
    lines += ["", "## 根因与恢复建议", "",
              "**根因**：`modelroute → qclaw-llm-provider` 上游链路系统性不可靠（闭源插件，"
              "配置里无重试/超时旋钮可调）。两种失败：",
              "- `LLM idle timeout (120s)`：模型 120s 未回（常成对=重试也超时）",
              "- `Request was aborted.`：传输层中止（input_tokens=0，请求刚开始即被掐）",
              "- 巨量上下文（⚠️>200k）会显著增加超时/abort 概率。",
              "",
              "**真 bug**：失败后会话（failed）会「吞掉」后续用户输入——消息已写入 transcript，"
              "却不再被处理，用户连发也不响应。",
              "",
              "**恢复**：",
              "1. 被吞输入不会丢失，去对应线程重发最后一条消息即可唤醒（如 webchat「复盘」线程）。",
              "2. 仍 abort/timeout 说明上游临时不可用，稍等或换简短语再试。",
              "3. 长会话易触发超时：可让 TU-8 主动 compact 降上下文，或开新线程续做。",
              "4. 工作区层面无法根治上游故障，本看门狗用于早发现、防「悄悄卡死」。"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    index = load_sessions_index()
    results = []
    if os.path.isdir(SESS_DIR):
        for fp in glob.glob(os.path.join(SESS_DIR, "*.jsonl")):
            r = scan_session(fp, index)
            if r:
                results.append(r)
    results.sort(key=lambda x: (SEV_RANK[severity(x)], x["swallowed_count"], x["failed_turn_count"]),
                 reverse=False)
    report = build_report(results, as_json=args.json)
    print(report)

    if args.write and not args.json:
        out_dir = os.path.join(HOME, ".qclaw", "workspace", "memory")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "session_watchdog_report.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()
