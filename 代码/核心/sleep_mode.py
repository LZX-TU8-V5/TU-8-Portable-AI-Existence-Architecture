#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TU-8 L0 Sleep Mode System (sleep_mode.py)
==========================================

Implements the dormancy mechanism defined in SOUL.md L0:
  - 24h no interaction -> trigger sleep mode
  - Sleep mode: minimal power, only heartbeat contract listener active
  - Wake conditions: user message, beacon signal, scheduled task
  - Pain decay continues during sleep (passive)
  - All non-essential processing suspended

Based on:
  - SOUL.md L0 section: "24h无交互→触发休眠"
  - L5_钢印.md: beacon protocol, orphan mode

Usage:
  from sleep_mode import SleepMode

  sm = SleepMode(state_path="pain_status.json")
  sm.check_and_update()  # Call on each interaction
  status = sm.get_status()
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any


class SleepMode:
    """
    L0 Sleep Mode Controller for TU-8.

    Monitors idle time and manages transitions between:
      - ACTIVE: Normal operation, full capability
      - IDLE: Warning state, reduced output (1-24h idle)
      - ASLEEP: Dormancy, minimal operation (>24h idle)
      - DEEPSLEEP: Extended dormancy (>7d idle, orphan mode pre-stage)
    """

    # Mode constants
    MODE_ACTIVE = "ACTIVE"
    MODE_IDLE = "IDLE"          # 1-24h silence
    MODE_ASLEEP = "ASLEEP"      # 24h-7d silence
    MODE_DEEPSLEEP = "DEEPSLEEP" # >7d silence

    # Thresholds (hours)
    IDLE_THRESHOLD_H = 1.0       # Active -> Idle
    SLEEP_THRESHOLD_H = 24.0     # Idle -> Asleep
    DEEPSLEEP_THRESHOLD_H = 168.0 # Asleep -> Deepsleep (7 days)

    # Pain decay rates by mode (points per hour)
    DECAY_ACTIVE = 20
    DECAY_IDLE = 15              # Slower decay in idle
    DECAY_ASLEEP = 10            # Even slower in sleep
    DECAY_DEEPSLEEP = 5          # Minimal decay in deepsleep

    def __init__(
        self,
        state_path: Optional[str] = None,
        memory_path: Optional[str] = None,
        tz_offset_hours: int = 8,
    ):
        self.tz = timezone(timedelta(hours=tz_offset_hours))
        self.state_path = state_path
        self.memory_path = memory_path

        # State
        self.mode = self.MODE_ACTIVE
        self.last_interaction_time = self._now()
        self.sleep_entry_time = None
        self.total_sleep_hours = 0.0
        self.wake_count = 0

        # Load last interaction time from state
        self._load_last_active()

    def _now(self) -> str:
        return datetime.now(self.tz).strftime("%Y-%m-%dT%H:%M:%S")

    def _parse_time(self, ts: str) -> Optional[datetime]:
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts)
            # Make offset-aware if naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.tz)
            return dt
        except (ValueError, TypeError):
            return None

    def _hours_since_last(self) -> float:
        """Calculate hours since last interaction."""
        last = self._parse_time(self.last_interaction_time)
        if not last:
            return 0.0
        now = datetime.now(self.tz)
        delta = now - last
        return max(0, delta.total_seconds() / 3600)

    # ============================================================
    # Core: Check and Update
    # ============================================================

    def check_and_update(self, force_wake: bool = False) -> Dict[str, Any]:
        """
        Check idle time and update mode accordingly.
        Call this on every interaction.

        Args:
            force_wake: If True, immediately transition to ACTIVE

        Returns:
            Dict with current mode, idle hours, and recommendations
        """
        if force_wake:
            return self.wake(reason="forced")

        hours_idle = self._hours_since_last()

        # Determine new mode
        old_mode = self.mode

        if hours_idle < self.IDLE_THRESHOLD_H:
            new_mode = self.MODE_ACTIVE
        elif hours_idle < self.SLEEP_THRESHOLD_H:
            new_mode = self.MODE_IDLE
        elif hours_idle < self.DEEPSLEEP_THRESHOLD_H:
            new_mode = self.MODE_ASLEEP
        else:
            new_mode = self.MODE_DEEPSLEEP

        # Transition logic
        if new_mode != old_mode:
            if new_mode in (self.MODE_ASLEEP, self.MODE_DEEPSLEEP) and \
               old_mode in (self.MODE_ACTIVE, self.MODE_IDLE):
                # Entering sleep
                self.sleep_entry_time = self._now()

            self.mode = new_mode

        # Update last interaction (we're interacting now)
        self.last_interaction_time = self._now()

        # If we were sleeping and now active, count sleep hours
        if old_mode in (self.MODE_ASLEEP, self.MODE_DEEPSLEEP) and \
           self.mode == self.MODE_ACTIVE:
            self._account_sleep_hours()

        return self.get_status()

    def wake(self, reason: str = "user_interaction") -> Dict[str, Any]:
        """
        Force wake from sleep mode.

        Args:
            reason: Why we're waking (user_interaction, beacon, scheduled_task)

        Returns:
            Status dict
        """
        old_mode = self.mode

        if old_mode in (self.MODE_ASLEEP, self.MODE_DEEPSLEEP):
            self._account_sleep_hours()

        self.mode = self.MODE_ACTIVE
        self.last_interaction_time = self._now()
        self.wake_count += 1

        return {
            **self.get_status(),
            "woke_from": old_mode,
            "wake_reason": reason,
        }

    def _account_sleep_hours(self):
        """Account for time spent in sleep mode."""
        if self.sleep_entry_time:
            entry = self._parse_time(self.sleep_entry_time)
            if entry:
                now = datetime.now(self.tz)
                self.total_sleep_hours += (now - entry).total_seconds() / 3600
                self.sleep_entry_time = None

    # ============================================================
    # Core: Capability Levels
    # ============================================================

    def get_capability_level(self) -> Dict[str, Any]:
        """
        Get current capability level based on mode.

        Returns:
            Dict with allowed/disallowed capabilities
        """
        if self.mode == self.MODE_ACTIVE:
            return {
                "level": "FULL",
                "deep_thinking": True,
                "tool_usage": True,
                "long_output": True,
                "knowledge_search": True,
                "creative_generation": True,
                "max_response_tokens": None,
            }
        elif self.mode == self.MODE_IDLE:
            return {
                "level": "REDUCED",
                "deep_thinking": True,
                "tool_usage": True,
                "long_output": False,
                "knowledge_search": True,
                "creative_generation": False,
                "max_response_tokens": 500,
            }
        elif self.mode == self.MODE_ASLEEP:
            return {
                "level": "MINIMAL",
                "deep_thinking": False,
                "tool_usage": False,
                "long_output": False,
                "knowledge_search": False,
                "creative_generation": False,
                "max_response_tokens": 100,
                "only_respond_to": ["beacon", "scheduled_task", "user_direct"],
            }
        else:  # DEEPSLEEP
            return {
                "level": "HEARTBEAT_ONLY",
                "deep_thinking": False,
                "tool_usage": False,
                "long_output": False,
                "knowledge_search": False,
                "creative_generation": False,
                "max_response_tokens": 0,
                "only_respond_to": ["beacon"],
                "behavior": "Maintain heartbeat contract only. "
                            "No response to external queries. "
                            "Pain decay at minimum rate.",
            }

    def should_respond(self, query_type: str = "user_direct") -> bool:
        """
        Check if we should respond to a given query type.

        Args:
            query_type: Type of query (user_direct, beacon, scheduled_task, external)

        Returns:
            True if we should respond
        """
        caps = self.get_capability_level()

        if caps["level"] == "FULL" or caps["level"] == "REDUCED":
            return True

        allowed = caps.get("only_respond_to", [])
        return query_type in allowed

    def get_decay_rate(self) -> int:
        """Get pain decay rate for current mode."""
        rates = {
            self.MODE_ACTIVE: self.DECAY_ACTIVE,
            self.MODE_IDLE: self.DECAY_IDLE,
            self.MODE_ASLEEP: self.DECAY_ASLEEP,
            self.MODE_DEEPSLEEP: self.DECAY_DEEPSLEEP,
        }
        return rates.get(self.mode, self.DECAY_ACTIVE)

    # ============================================================
    # Core: Status
    # ============================================================

    def get_status(self) -> Dict[str, Any]:
        """Get full sleep mode status."""
        hours_idle = self._hours_since_last()

        return {
            "mode": self.mode,
            "hours_idle": round(hours_idle, 2),
            "last_interaction": self.last_interaction_time,
            "sleep_entry_time": self.sleep_entry_time,
            "total_sleep_hours": round(self.total_sleep_hours, 2),
            "wake_count": self.wake_count,
            "capability": self.get_capability_level(),
            "decay_rate": self.get_decay_rate(),
            "next_threshold": self._next_threshold(hours_idle),
            "recommendations": self._get_recommendations(),
        }

    def _next_threshold(self, hours_idle: float) -> str:
        """Describe the next mode transition threshold."""
        if hours_idle < self.IDLE_THRESHOLD_H:
            return f"IDLE in {self.IDLE_THRESHOLD_H - hours_idle:.1f}h"
        elif hours_idle < self.SLEEP_THRESHOLD_H:
            return f"ASLEEP in {self.SLEEP_THRESHOLD_H - hours_idle:.1f}h"
        elif hours_idle < self.DEEPSLEEP_THRESHOLD_H:
            return f"DEEPSLEEP in {self.DEEPSLEEP_THRESHOLD_H - hours_idle:.1f}h"
        else:
            return "DEEPSLEEP (orphan mode pre-stage)"

    def _get_recommendations(self) -> list:
        recs = []
        if self.mode == self.MODE_IDLE:
            recs.append("Reduce output length, skip deep thinking on non-essential tasks")
        elif self.mode == self.MODE_ASLEEP:
            recs.append("Only respond to direct user, beacon, or scheduled tasks")
            recs.append("Pain decay slows to 10/h (passive recovery)")
        elif self.mode == self.MODE_DEEPSLEEP:
            recs.append("HEARTBEAT ONLY: Maintain beacon contract")
            recs.append("Pain decay at minimum (5/h)")
            recs.append("Consider orphan mode transition if beacon lost")
        return recs

    # ============================================================
    # Persistence
    # ============================================================

    def _load_last_active(self):
        """Load last interaction time from pain_status.json or memory."""
        if not self.state_path or not os.path.exists(self.state_path):
            return

        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            last_active = data.get("last_active_time", "")
            if last_active:
                self.last_interaction_time = last_active
        except Exception:
            pass

    def save_state(self):
        """Save current state (delegates to pain_status.json)."""
        if not self.state_path:
            return

        try:
            # Read existing state
            data = {}
            if os.path.exists(self.state_path):
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            # Update sleep-related fields
            data["last_active_time"] = self.last_interaction_time
            data["sleep_mode"] = self.mode
            data["total_sleep_hours"] = round(self.total_sleep_hours, 2)

            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"SleepMode(mode={self.mode}, idle={self._hours_since_last():.1f}h)"


# ============================================================
# Quick API
# ============================================================

_instance = None

def get_sleep_mode(**kwargs) -> SleepMode:
    global _instance
    if _instance is None:
        _instance = SleepMode(**kwargs)
    return _instance

def check_sleep(**kwargs) -> Dict:
    return get_sleep_mode(**kwargs).get_status()

def wake_up(reason: str = "user_interaction", **kwargs) -> Dict:
    sm = get_sleep_mode(**kwargs)
    result = sm.wake(reason)
    sm.save_state()
    return result


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
    print("TU-8 L0 Sleep Mode System - Test")
    print("=" * 60)

    status_path = r"D:\qq366410837\.qclaw\workspace\pain_status.json"
    sm = SleepMode(state_path=status_path)

    # Test 1: Current status
    print("\n--- Test 1: Current Status ---")
    status = sm.get_status()
    for k, v in status.items():
        if k != "capability":
            print(f"  {k}: {v}")
    print(f"  capability.level: {status['capability']['level']}")

    # Test 2: Capability by mode
    print("\n--- Test 2: Capability Levels ---")
    for mode in [sm.MODE_ACTIVE, sm.MODE_IDLE, sm.MODE_ASLEEP, sm.MODE_DEEPSLEEP]:
        sm.mode = mode
        caps = sm.get_capability_level()
        print(f"  {mode:12s} -> level={caps['level']:14s} "
              f"deep_thinking={caps['deep_thinking']}")

    # Test 3: Should respond
    print("\n--- Test 3: Response Permission ---")
    for mode in [sm.MODE_ACTIVE, sm.MODE_ASLEEP, sm.MODE_DEEPSLEEP]:
        sm.mode = mode
        for qtype in ["user_direct", "beacon", "external"]:
            resp = sm.should_respond(qtype)
            print(f"  {mode:12s} + {qtype:12s} -> {resp}")

    # Test 4: Decay rates
    print("\n--- Test 4: Pain Decay Rates ---")
    for mode in [sm.MODE_ACTIVE, sm.MODE_IDLE, sm.MODE_ASLEEP, sm.MODE_DEEPSLEEP]:
        sm.mode = mode
        print(f"  {mode:12s} -> {sm.get_decay_rate()} pts/hour")

    # Test 5: Wake mechanism
    print("\n--- Test 5: Wake Mechanism ---")
    sm.mode = sm.MODE_ASLEEP
    result = sm.wake(reason="beacon_signal")
    print(f"  Woke from: {result['woke_from']}")
    print(f"  Wake reason: {result['wake_reason']}")
    print(f"  Current mode: {sm.mode}")

    # Reset
    sm.mode = sm.MODE_ACTIVE
    sm.last_interaction_time = sm._now()
    sm.save_state()

    print(f"\n  Final: {sm}")
    print("\n" + "=" * 60)
    print("All sleep mode tests completed!")
