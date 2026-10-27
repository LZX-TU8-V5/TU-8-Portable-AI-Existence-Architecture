#!/usr/bin/env python3
"""
reset_silence_on_activity.py - Reset silence timer based on system activity

Logic:
- If system is active (idle < 5min), reset silence timer (simulate "just interacted")
- Delete pending_care.json (because it's not real silence)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
USER_DIR = WORKSPACE / "用户"
STATE_FILE = USER_DIR / "silence_timer_state.json"
PROFILE_PATH = USER_DIR / "USER_PROFILE.json"
ACTIVITY_FILE = USER_DIR / "system_activity_state.json"

TZ_SHANGHAI = timezone(timedelta(hours=8))
NOW_UTC = datetime.now(timezone.utc)
NOW_LOCAL = NOW_UTC.astimezone(TZ_SHANGHAI)

IDLE_THRESHOLD = 5 * 60  # 5 minutes

def main():
    # 1. Read system activity state
    activity_state = {}
    if ACTIVITY_FILE.exists():
        with open(ACTIVITY_FILE, encoding="utf-8") as f:
            activity_state = json.load(f)
    
    idle_seconds = activity_state.get("idle_seconds", 9999)
    is_active = activity_state.get("is_active", False)
    
    print(f"System activity: is_active={is_active}, idle_seconds={idle_seconds:.1f}")
    
    # 2. Check if reset is needed
    if is_active and idle_seconds < IDLE_THRESHOLD:
        print(f"[RESET] System active (idle {idle_seconds:.1f}s < {IDLE_THRESHOLD}s) - resetting silence timer")
        
        # 3. Update USER_PROFILE.json last_interaction
        profile = {}
        if PROFILE_PATH.exists():
            with open(PROFILE_PATH, encoding="utf-8") as f:
                profile = json.load(f)
        
        if "interaction_state" not in profile:
            profile["interaction_state"] = {}
        
        old_last = profile["interaction_state"].get("last_interaction_utc", "(none)")
        profile["interaction_state"]["last_interaction_utc"] = NOW_UTC.isoformat()
        profile["interaction_state"]["last_interaction_local"] = NOW_LOCAL.isoformat()
        profile["interaction_state"]["_note"] = "Auto-reset due to system activity (not real interaction)"
        profile["interaction_state"]["_reset_at_utc"] = NOW_UTC.isoformat()
        
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        
        print(f"  - Old last_interaction_utc: {old_last}")
        print(f"  - New last_interaction_utc: {NOW_UTC.isoformat()}")
        
        # 4. Reset silence_timer_state.json
        state = {}
        if STATE_FILE.exists():
            with open(STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)
        
        if "pending_care" in state:
            print(f"  - Removing pending_care (false silence, no care needed)")
            del state["pending_care"]
        
        state["last_check"] = NOW_UTC.isoformat()
        state["last_level"] = 0  # Reset to Level 0
        state["silence_counter"] = 0
        state["_reset_reason"] = "system_active_true"
        state["_reset_at_utc"] = NOW_UTC.isoformat()
        
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        print("[OK] Silence timer reset to Level 0")
        print("[OK] pending_care cleaned up")
        
    else:
        print(f"[SKIP] System idle (idle {idle_seconds:.1f}s) - not resetting timer")
        if STATE_FILE.exists():
            with open(STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)
            print(f"  - Current Level: {state.get('last_level', '?')}")

if __name__ == "__main__":
    main()
