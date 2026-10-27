#!/usr/bin/env python3
"""
TU-8 Automatic Cold Start Script
Automatically runs cold_start_engine at session startup

This script should be called during OpenClaw session initialization.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
def check_cold_start_needed(workspace_dir: str) -> tuple:
    """
    Check if cold start is needed by examining session state
    
    Returns:
        (needed: bool, reason: str, cold_start_type: str)
        - needed: True if cold start should be executed
        - reason: Human-readable reason
        - cold_start_type: Recommended cold start type (CONTINUOUS/MINIMAL/PARTIAL/STANDARD/FULL)
    """
    workspace_path = Path(workspace_dir)
    
    # Check if genesis_block exists
    genesis_file = workspace_path / "secure_vault" / "genesis_block.json"
    if not genesis_file.exists():
        return True, "genesis_block not found", "FULL"
    
    # Check P0 lock file
    lock_file = workspace_path / "secure_vault" / "p0_complete.lock"
    if not lock_file.exists():
        return True, "P0 lock file not found", "FULL"
    
    # Advanced session gap detection
    try:
        with open(lock_file, "r", encoding="utf-8") as f:
            lock_data = json.load(f)
            last_p0_time_str = lock_data.get("timestamp")
            
            if not last_p0_time_str:
                return True, "No timestamp in lock file", "FULL"
            
            # Parse timestamp
            last_p0_time = datetime.fromisoformat(last_p0_time_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            
            # Calculate hours since last P0 completion
            hours_since = (now - last_p0_time).total_seconds() / 3600
            
            # Session gap thresholds (aligned with cold_start_engine.py)
            if hours_since < 0.5:
                # Continuous session (< 0.5 hours)
                return False, f"Continuous session ({hours_since:.2f}h ago), no cold start needed", "CONTINUOUS"
            elif hours_since < 4:
                # Short break (0.5-4 hours)
                return True, f"Short break ({hours_since:.2f}h ago), MINIMAL cold start recommended", "MINIMAL"
            elif hours_since < 12:
                # Deep work session (4-12 hours)
                return True, f"Deep work gap ({hours_since:.2f}h ago), PARTIAL cold start recommended", "PARTIAL"
            elif hours_since < 24:
                # Overnight (12-24 hours)
                return True, f"Overnight gap ({hours_since:.2f}h ago), STANDARD cold start recommended", "STANDARD"
            elif hours_since < 72:
                # Long break (24-72 hours)
                return True, f"Long break ({hours_since:.2f}h ago), FULL cold start recommended", "FULL"
            else:
                # Deep dormancy (> 72 hours)
                return True, f"Deep dormancy ({hours_since:.2f}h ago), FULL cold start with verification", "FULL"
                
    except Exception as e:
        return True, f"Error reading lock file: {e}", "FULL"
def run_cold_start(workspace_dir: str, auto_mode: bool = True) -> int:
    """
    Execute cold_start_engine
    
    Args:
        workspace_dir: Path to workspace directory
        auto_mode: If True, run in automatic mode (skip interactive auth)
    
    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    script_path = Path(workspace_dir) / "src" / "cold_start_engine.py"
    
    if not script_path.exists():
        print(f"[AutoColdStart] ERROR: cold_start_engine.py not found at {script_path}")
        return 1
    
    # Build command
    cmd = [sys.executable, str(script_path)]
    
    if auto_mode:
        cmd.append("--auto")
    
    # Set PYTHONPATH to include workspace and src directories
    env = os.environ.copy()
    workspace_path = str(workspace_dir)
    src_path = str(Path(workspace_dir) / "src")
    
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{workspace_path};{src_path};{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = f"{workspace_path};{src_path}"
    
    print(f"[AutoColdStart] Running: {' '.join(cmd)}")
    print("=" * 60)
    
    # Execute
    try:
        result = subprocess.run(
            cmd,
            cwd=str(Path(workspace_dir)),
            env=env,
            capture_output=False,
            text=True
        )
        
        return result.returncode
        
    except Exception as e:
        print(f"[AutoColdStart] ERROR: Failed to execute cold_start_engine: {e}")
        return 1
def main():
    print("[AutoColdStart] TU-8 Automatic Cold Start")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # Determine workspace directory
    # Default: parent of scripts directory
    script_dir = Path(__file__).parent
    workspace_dir = script_dir.parent
    
    # Allow override via environment variable
    if "QCLAW_WORKSPACE" in os.environ:
        workspace_dir = Path(os.environ["QCLAW_WORKSPACE"])
    
    print(f"[AutoColdStart] Workspace: {workspace_dir}")
    
    if not workspace_dir.exists():
        print(f"[AutoColdStart] ERROR: Workspace directory not found: {workspace_dir}")
        return 1
    
    # Check if cold start is needed
    needed, reason, cold_start_type = check_cold_start_needed(str(workspace_dir))
    print(f"[AutoColdStart] Check result: {reason}")
    print(f"[AutoColdStart] Recommended type: {cold_start_type}")
    
    if not needed:
        print("\n[AutoColdStart] Skipping cold start (not needed)")
        return 0
    
    # Run cold start
    print("\n[AutoColdStart] Executing cold start...")
    exit_code = run_cold_start(str(workspace_dir), auto_mode=True)
    
    if exit_code == 0:
        print("\n[AutoColdStart] Cold start completed successfully")
    else:
        print(f"\n[AutoColdStart] Cold start failed with exit code {exit_code}")
        print("[AutoColdStart] TU-8 will continue with limited functionality")
    
    return exit_code
if __name__ == "__main__":
    exit(main())
