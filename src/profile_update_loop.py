"""
profile_update_loop.py — 用户画像更新循环

功能：
  1. 读取 user_state_changes.md 中的状态变化
  2. 过滤出"可固化"的信息
  3. 写入或更新 USER.md 对应字段
  4. 清空已处理的状态变化

触发时机：
  - Heartbeat 巡检（轻量检查）
  - Cron 梦境期（深度代谢）
  - 重要变化实时触发

与 anomaly_detector.py 的关系：
  - anomaly_detector 写入 user_state_changes.md
  - profile_update_loop 读取并消化
"""

import os, re, json, time
from datetime import datetime, timezone
from typing import Optional

# ── 路径常量 ────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_MD = os.path.join(BASE, "USER.md")
STATE_CHANGES = os.path.join(BASE, "memory", "user_state_changes.md")
PROFILE_LOG = os.path.join(BASE, "memory", "profile_update_log.jsonl")

# ── USER.md 可更新字段 ─────────────────────────────────────
UPDATEABLE_FIELDS = {
    # (regex模式, USER.md 中目标行前缀)
    "shici":        (r"当前状态[:：].*",          "当前状态"),
    "project":      (r"项目状态",                 "项目状态"),
    "preference":   (r"沟通偏好",                 "沟通偏好"),
}

# ── 状态变化 → USER.md 映射规则 ────────────────────────────
STATE_TO_FIELD = {}


class ProfileUpdateLoop:
    """
    用户画像更新循环

    Usage:
        loop = ProfileUpdateLoop()
        loop.cycle()          # 一次完整更新
        loop.extract_field("当前状态")  # 从 USER.md 提取当前值
        loop.update_field("当前状态", "初级会计考试已结束，等成绩中")
    """

    def __init__(self):
        self._fresh_changes: list[str] = []

    # ── 主循环 ──────────────────────────────────────────────

    def cycle(self, force: bool = False) -> dict:
        """
        执行一轮更新循环：
          1. 读取 user_state_changes.md
          2. 提取可固化的状态变化
          3. 更新 USER.md
          4. 清空状态文件

        返回: 操作报告
        """
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": 0,
            "processed": 0,
            "updates": [],
            "errors": [],
        }

        # Step 1: 读取状态变化
        changes = self._read_state_changes()
        report["read"] = len(changes)
        if not changes:
            return report

        # Step 2: 分类处理
        for change in changes:
            result = self._digest(change)
            if result:
                report["processed"] += 1
                report["updates"].append(result)

        # Step 3: 写 USER.md
        if report["updates"]:
            self._write_user_md(report["updates"])

        # Step 4: 清空
        self._clear_state_changes()

        # Step 5: 记录日志
        self._log(report)

        return report

    # ── 读取状态变化 ────────────────────────────────────────

    def _read_state_changes(self) -> list[dict]:
        """解析 user_state_changes.md 返回变化列表"""
        if not os.path.exists(STATE_CHANGES):
            return []
        entries = []
        with open(STATE_CHANGES, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 格式: - timestamp | [TYPE] text
                m = re.match(r"-\s+(\S+T\S+Z?)\s*\|\s*\[(\w+)\]\s*(.*)", line)
                if m:
                    entries.append({
                        "ts": m.group(1),
                        "type": m.group(2),
                        "text": m.group(3).strip(),
                    })
        return entries

    # ── 消化单条变化 ────────────────────────────────────────

    def _digest(self, change: dict) -> Optional[dict]:
        """
        将一条状态变化映射为 USER.md 更新。

        规则：
          DISSATISFACTION → 暂不更新 USER.md（仅记录日志）
          SUSPICIOUS      → 暂不更新（需人工复核）
          TOPIC_JUMP      → 可触发兴趣标签微调
          SENTIMENT_SHIFT → 暂不更新
        """
        ctype = change["type"]
        text = change["text"]

        if ctype == "DISSATISFACTION":
            # 不满意信号 → 存入日志，不直接修改 USER.md
            self._log({
                "event": "dissatisfaction_recorded",
                "text": text,
                "action": "no_update",
                "reason": "need_human_review",
            })
            return {
                "field": "_dissatisfaction_log",
                "value": text,
                "action": "logged_only",
            }

        if ctype == "TOPIC_JUMP":
            # 话题跳转 → 如果出现多次同一新话题，可更新兴趣偏好
            # 当前暂不自动更新（信息不够成熟）
            return {
                "field": "_topic_jump",
                "value": text,
                "action": "observed_no_update",
            }

        # 其他类型暂不更新 USER.md
        return None

    # ── USER.md 写入 ────────────────────────────────────────

    def _write_user_md(self, updates: list[dict]):
        """执行对 USER.md 的写入操作"""
        if not os.path.exists(USER_MD):
            return
        with open(USER_MD, "r", encoding="utf-8") as f:
            content = f.read()

        # 当前仅支持"当前状态"字段的简单替换
        for upd in updates:
            if upd["field"] == "current_status":
                content = re.sub(
                    r"\| 当前状态 .*",
                    f"| 当前状态 | {upd['value']} |",
                    content,
                )

        with open(USER_MD, "w", encoding="utf-8") as f:
            f.write(content)

    def extract_field(self, field_name: str) -> Optional[str]:
        """从 USER.md 提取指定字段值"""
        if not os.path.exists(USER_MD):
            return None
        with open(USER_MD, "r", encoding="utf-8") as f:
            content = f.read()
            if field_name == "当前状态":
                m = re.search(r"\| 当前状态 \| (.+?) \|", content)
                return m.group(1).strip() if m else None
            if field_name == "项目状态":
                m = re.search(r"\| 项目状态 \| (.+?) \|", content)
                return m.group(1).strip() if m else None
        return None

    def update_field(self, field_name: str, value: str) -> bool:
        """直接更新 USER.md 中的指定字段"""
        if not os.path.exists(USER_MD):
            return False
        with open(USER_MD, "r", encoding="utf-8") as f:
            content = f.read()

        if field_name == "当前状态":
            new_content = re.sub(
                r"\| 当前状态 \| .*? \|",
                f"| 当前状态 | {value} |",
                content,
            )
            if new_content == content:
                return False
            with open(USER_MD, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

        return False

    # ── 清空 ────────────────────────────────────────────────

    def _clear_state_changes(self):
        """清空状态变化文件"""
        with open(STATE_CHANGES, "w", encoding="utf-8") as f:
            f.write("# 用户状态变化记录\n\n")
            f.write("> 此文件由 Heartbeat 追加写入\n")
            f.write("> 由 ProfileUpdateLoop 循环清空\n\n")
            f.write(f"*最后清空：{datetime.now(timezone.utc).isoformat()}*\n")

    # ── 日志 ────────────────────────────────────────────────

    def _log(self, entry: dict):
        """追加日志"""
        os.makedirs(os.path.dirname(PROFILE_LOG), exist_ok=True)
        with open(PROFILE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
