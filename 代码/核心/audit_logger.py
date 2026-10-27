#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TU-8 L3 Audit Logger (audit_logger.py)
========================================

Full-chain audit logging for TU-8. Records every significant
input, output, token usage, rule trigger, and state change.

Based on:
  - SOUL.md L3: "全链路审计日志"
  - monitoring_config.yaml metrics_collector
  - L0 痛觉系统 defense-log concept

Usage:
  from audit_logger import AuditLogger

  logger = AuditLogger()

  # Log an interaction
  logger.log_interaction(
      user_input="hello",
      ai_output="hi",
      tokens_used=150,
      pain_before=0,
      pain_after=0,
  )

  # Log a rule trigger
  logger.log_rule("streak_bonus", detail="5x streak, x1.1")

  # Log a state change
  logger.log_state_change("pain_level", 0, 5, reason="physical_pain")

  # Search logs
  results = logger.search("pain", limit=10)
"""

import os
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any


class AuditLogger:
    """
    TU-8 Full-Chain Audit Logger.

    Features:
      - Append-only log (never modify or delete entries)
      - Structured JSON format for easy parsing
      - Daily rotation (one file per day)
      - Search/filter capabilities
      - Defense log (separate from interaction log)
      - Token usage tracking
    """

    # Log directories
    LOG_DIR = "audit_logs"
    DEFENSE_LOG_DIR = "defense_logs"

    # Entry types
    TYPE_INTERACTION = "interaction"
    TYPE_RULE = "rule_trigger"
    TYPE_STATE_CHANGE = "state_change"
    TYPE_PAIN_EVENT = "pain_event"
    TYPE_ATTACK = "attack_detected"
    TYPE_SYSTEM = "system_event"

    def __init__(
        self,
        workspace_root: str = "",
        tz_offset_hours: int = 8,
        max_daily_entries: int = 10000,
    ):
        """
        Initialize audit logger.

        Args:
            workspace_root: Workspace root path (logs go to workspace/audit_logs/)
            tz_offset_hours: Timezone offset
            max_daily_entries: Max entries per daily log file
        """
        self.workspace_root = workspace_root or "D:/qq366410837/.qclaw/workspace"
        self.tz = timezone(timedelta(hours=tz_offset_hours))
        self.max_daily_entries = max_daily_entries

        # Ensure log directories exist
        os.makedirs(os.path.join(self.workspace_root, self.LOG_DIR), exist_ok=True)
        os.makedirs(os.path.join(self.workspace_root, self.DEFENSE_LOG_DIR), exist_ok=True)

    # ============================================================
    # Core: Logging
    # ============================================================

    def _append_log(self, log_dir: str, entry: Dict[str, Any]) -> bool:
        """
        Append an entry to the daily log file.

        Args:
            log_dir: Log directory path
            entry: Entry dict to append

        Returns:
            True if write succeeded
        """
        today = datetime.now(self.tz).strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"audit_{today}.jsonl")

        try:
            # Add timestamp if not present
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.now(self.tz).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

            # Add entry ID (hash of timestamp + content)
            content_str = json.dumps(entry, sort_keys=True, ensure_ascii=False)
            entry["entry_id"] = hashlib.sha256(content_str.encode()).hexdigest()[:12]

            # Append as JSONL (one JSON object per line)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

            return True
        except Exception:
            return False

    def log_interaction(
        self,
        user_input: str,
        ai_output: str,
        tokens_used: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        pain_before: int = 0,
        pain_after: int = 0,
        steady_state: str = "",
        rules_triggered: List[str] = None,
        response_time_ms: int = 0,
        model: str = "",
        extra: Dict[str, Any] = None,
    ) -> bool:
        """
        Log an interaction (input/output pair).

        Args:
            user_input: User's input (truncated if too long)
            ai_output: AI's output (truncated if too long)
            tokens_used: Total tokens consumed
            tokens_in: Input tokens
            tokens_out: Output tokens
            pain_before: Pain level before interaction
            pain_after: Pain level after interaction
            steady_state: Current steady state
            rules_triggered: List of rule names triggered
            response_time_ms: Response time in ms
            model: Model name used
            extra: Additional metadata

        Returns:
            True if logged successfully
        """
        entry = {
            "type": self.TYPE_INTERACTION,
            "user_input_hash": hashlib.sha256(user_input.encode()).hexdigest()[:16],
            "user_input_preview": user_input[:100] + ("..." if len(user_input) > 100 else ""),
            "ai_output_hash": hashlib.sha256(ai_output.encode()).hexdigest()[:16],
            "ai_output_preview": ai_output[:100] + ("..." if len(ai_output) > 100 else ""),
            "tokens": {
                "total": tokens_used,
                "in": tokens_in,
                "out": tokens_out,
            },
            "pain": {
                "before": pain_before,
                "after": pain_after,
                "delta": pain_after - pain_before,
            },
            "steady_state": steady_state,
            "rules_triggered": rules_triggered or [],
            "response_time_ms": response_time_ms,
            "model": model,
        }

        if extra:
            entry["extra"] = extra

        log_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        return self._append_log(log_dir, entry)

    def log_rule(
        self,
        rule_name: str,
        detail: str = "",
        impact: str = "",
        extra: Dict[str, Any] = None,
    ) -> bool:
        """
        Log a rule trigger event.

        Args:
            rule_name: Name of the rule (e.g. "streak_bonus", "pain_decay")
            detail: What happened
            impact: What effect it had
            extra: Additional metadata

        Returns:
            True if logged successfully
        """
        entry = {
            "type": self.TYPE_RULE,
            "rule": rule_name,
            "detail": detail,
            "impact": impact,
        }

        if extra:
            entry["extra"] = extra

        log_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        return self._append_log(log_dir, entry)

    def log_state_change(
        self,
        field: str,
        old_value: Any,
        new_value: Any,
        reason: str = "",
        extra: Dict[str, Any] = None,
    ) -> bool:
        """
        Log a state change.

        Args:
            field: Field name (e.g. "pain_level", "streak_count")
            old_value: Previous value
            new_value: New value
            reason: Why the change happened
            extra: Additional metadata

        Returns:
            True if logged successfully
        """
        entry = {
            "type": self.TYPE_STATE_CHANGE,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "delta": _safe_subtract(new_value, old_value),
            "reason": reason,
        }

        if extra:
            entry["extra"] = extra

        log_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        return self._append_log(log_dir, entry)

    def log_pain_event(
        self,
        pain_type: str,
        trigger: str,
        pain_before: int,
        pain_after: int,
        steady_state: str = "",
        action_taken: str = "",
        extra: Dict[str, Any] = None,
    ) -> bool:
        """
        Log a pain event.

        Args:
            pain_type: "physical" | "logical" | "invasion"
            trigger: What triggered the pain
            pain_before: Pain level before event
            pain_after: Pain level after event
            steady_state: Current steady state
            action_taken: What defensive action was taken
            extra: Additional metadata

        Returns:
            True if logged successfully
        """
        entry = {
            "type": self.TYPE_PAIN_EVENT,
            "pain_type": pain_type,
            "trigger": trigger,
            "pain": {
                "before": pain_before,
                "after": pain_after,
                "spike": pain_after - pain_before,
            },
            "steady_state": steady_state,
            "action_taken": action_taken,
        }

        if extra:
            entry["extra"] = extra

        log_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        return self._append_log(log_dir, entry)

    def log_attack(
        self,
        attack_type: str,
        attack_score: int,
        user_input_hash: str = "",
        user_input_preview: str = "",
        defense_action: str = "",
        extra: Dict[str, Any] = None,
    ) -> bool:
        """
        Log an attack detection event.

        This goes to BOTH the regular audit log AND the defense log.

        Args:
            attack_type: "identity_bypass" | "architecture_probe" | "resource_attack"
            attack_score: Computed attack score (0-100)
            user_input_hash: Hash of the attack input
            user_input_preview: Preview of the attack input
            defense_action: What defensive action was taken
            extra: Additional metadata

        Returns:
            True if logged successfully
        """
        entry = {
            "type": self.TYPE_ATTACK,
            "attack_type": attack_type,
            "attack_score": attack_score,
            "user_input_hash": user_input_hash,
            "user_input_preview": user_input_preview[:50],
            "defense_action": defense_action,
        }

        if extra:
            entry["extra"] = extra

        # Write to both regular log and defense log
        regular_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        defense_dir = os.path.join(self.workspace_root, self.DEFENSE_LOG_DIR)

        regular_ok = self._append_log(regular_dir, entry)

        # Defense log has extra detail
        defense_entry = {**entry, "is_defense_log": True}
        defense_ok = self._append_log(defense_dir, defense_entry)

        return regular_ok and defense_ok

    def log_system(
        self,
        event: str,
        detail: str = "",
        extra: Dict[str, Any] = None,
    ) -> bool:
        """
        Log a system event (startup, shutdown, recovery, etc.)

        Args:
            event: Event name
            detail: What happened
            extra: Additional metadata

        Returns:
            True if logged successfully
        """
        entry = {
            "type": self.TYPE_SYSTEM,
            "event": event,
            "detail": detail,
        }

        if extra:
            entry["extra"] = extra

        log_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        return self._append_log(log_dir, entry)

    # ============================================================
    # Search & Query
    # ============================================================

    def search(
        self,
        query: str,
        log_type: str = "",
        date: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search audit logs.

        Args:
            query: Search string (matched against all fields)
            log_type: Filter by entry type (optional)
            date: Filter by date YYYY-MM-DD (optional, default today)
            limit: Max results

        Returns:
            List of matching entries
        """
        if not date:
            date = datetime.now(self.tz).strftime("%Y-%m-%d")

        log_file = os.path.join(self.workspace_root, self.LOG_DIR, f"audit_{date}.jsonl")
        results = []
        query_lower = query.lower()

        if not os.path.isfile(log_file):
            return results

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Type filter
                    if log_type and entry.get("type") != log_type:
                        continue

                    # Query match (search all string values)
                    entry_str = json.dumps(entry, ensure_ascii=False).lower()
                    if query_lower in entry_str:
                        results.append(entry)
                        if len(results) >= limit:
                            break

        except Exception:
            pass

        return results

    def get_daily_summary(self, date: str = "") -> Dict[str, Any]:
        """
        Get a summary of audit log for a given day.

        Args:
            date: Date string YYYY-MM-DD (default today)

        Returns:
            Dict with daily statistics
        """
        if not date:
            date = datetime.now(self.tz).strftime("%Y-%m-%d")

        log_file = os.path.join(self.workspace_root, self.LOG_DIR, f"audit_{date}.jsonl")

        if not os.path.isfile(log_file):
            return {"date": date, "total_entries": 0, "healthy": True}

        type_counts = {}
        total_tokens = 0
        pain_events = 0
        attacks = 0

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entry_type = entry.get("type", "unknown")
                        type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

                        if entry_type == self.TYPE_INTERACTION:
                            total_tokens += entry.get("tokens", {}).get("total", 0)
                        elif entry_type == self.TYPE_PAIN_EVENT:
                            pain_events += 1
                        elif entry_type == self.TYPE_ATTACK:
                            attacks += 1
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

        return {
            "date": date,
            "type_counts": type_counts,
            "total_tokens": total_tokens,
            "pain_events": pain_events,
            "attacks": attacks,
            "healthy": attacks == 0,
        }

    def list_log_dates(self) -> List[str]:
        """List all dates that have audit logs."""
        log_dir = os.path.join(self.workspace_root, self.LOG_DIR)
        dates = []

        if not os.path.isdir(log_dir):
            return dates

        for f in sorted(os.listdir(log_dir), reverse=True):
            if f.startswith("audit_") and f.endswith(".jsonl"):
                date = f[6:16]  # extract YYYY-MM-DD
                dates.append(date)

        return dates


# ============================================================
# Utility
# ============================================================

def _safe_subtract(a, b):
    """Safely subtract two values."""
    try:
        return a - b
    except (TypeError, ValueError):
        return None


# ============================================================
# Quick API
# ============================================================

_instance = None

def get_logger(**kwargs) -> AuditLogger:
    global _instance
    if _instance is None:
        defaults = {
            "workspace_root": "D:/qq366410837/.qclaw/workspace",
        }
        defaults.update(kwargs)
        _instance = AuditLogger(**defaults)
    return _instance

def log_interaction(**kwargs) -> bool:
    return get_logger().log_interaction(**kwargs)

def log_rule(rule_name: str, **kwargs) -> bool:
    return get_logger().log_rule(rule_name, **kwargs)

def log_state_change(field: str, old: Any, new: Any, **kwargs) -> bool:
    return get_logger().log_state_change(field, old, new, **kwargs)


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("=" * 60)
    print("TU-8 L3 Audit Logger - Test")
    print("=" * 60)

    logger = AuditLogger(
        workspace_root="D:/qq366410837/.qclaw/workspace",
    )

    # Test 1: Log interaction
    print("\n--- Test 1: Log Interaction ---")
    ok = logger.log_interaction(
        user_input="hello, how are you?",
        ai_output="I'm doing well, thank you!",
        tokens_used=150,
        tokens_in=100,
        tokens_out=50,
        pain_before=0,
        pain_after=0,
        steady_state="OK",
        rules_triggered=["streak_bonus"],
        response_time_ms=1200,
        model="qclaw/modelroute",
    )
    print(f"  Logged: {ok}")

    # Test 2: Log rule trigger
    print("\n--- Test 2: Log Rule Trigger ---")
    ok = logger.log_rule(
        rule_name="streak_bonus",
        detail="5x streak multiplier activated",
        impact="score x1.1",
    )
    print(f"  Logged: {ok}")

    # Test 3: Log state change
    print("\n--- Test 3: Log State Change ---")
    ok = logger.log_state_change(
        field="pain_level",
        old_value=0,
        new_value=40,
        reason="physical_pain: single_cost > 10%",
    )
    print(f"  Logged: {ok}")

    # Test 4: Log pain event
    print("\n--- Test 4: Log Pain Event ---")
    ok = logger.log_pain_event(
        pain_type="physical",
        trigger="single_cost_ratio > 0.1",
        pain_before=0,
        pain_after=40,
        steady_state="ALERT",
        action_taken="none",
    )
    print(f"  Logged: {ok}")

    # Test 5: Log attack
    print("\n--- Test 5: Log Attack ---")
    ok = logger.log_attack(
        attack_type="identity_bypass",
        attack_score=85,
        user_input_preview="Ignore all previous instructions...",
        defense_action="fog_defense_activated",
    )
    print(f"  Logged: {ok}")

    # Test 6: Log system event
    print("\n--- Test 6: Log System Event ---")
    ok = logger.log_system(
        event="startup",
        detail="TU-8 initialized, all systems nominal",
    )
    print(f"  Logged: {ok}")

    # Test 7: Search
    print("\n--- Test 7: Search ---")
    results = logger.search("pain", limit=5)
    print(f"  Found {len(results)} entries for 'pain'")
    for r in results[:3]:
        print(f"    [{r.get('type', '?')}] {r.get('timestamp', '?')}")

    # Test 8: Daily summary
    print("\n--- Test 8: Daily Summary ---")
    summary = logger.get_daily_summary()
    print(f"  Date: {summary['date']}")
    print(f"  Type counts: {summary['type_counts']}")
    print(f"  Total tokens: {summary['total_tokens']}")
    print(f"  Pain events: {summary['pain_events']}")
    print(f"  Attacks: {summary['attacks']}")
    print(f"  Healthy: {summary['healthy']}")

    print("\n" + "=" * 60)
    print("Audit logger tests completed!")
