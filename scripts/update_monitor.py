"""
TU-8 更新自动监测 v1.0
======================
由 cron 定期调用（每 10 分钟）。

功能：
  1. 读取前置快照（update_snapshot_before.json）
  2. 获取当前 gateway 版本
  3. 如果版本变化 → 自动运行后置验证
  4. 生成报告并通知造物主

依赖：
  - memory/update_snapshot_before.json（由 pre_update_snapshot.py 生成）
  - scripts/post_update_verify.py（后置验证脚本）

cron 注册：
  openclaw cron add \
    --label "TU8_update_monitor" \
    --schedule "every 10m" \
    --task "python scripts/update_monitor.py"
"""

import json
import sys
import io
import subprocess
import time
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
SNAPSHOT_BEFORE = WORKSPACE / "memory" / "update_snapshot_before.json"
STATE_FILE = WORKSPACE / "memory" / ".update_monitor_state.json"
VERIFY_SCRIPT = WORKSPACE / "scripts" / "post_update_verify.py"


def get_gateway_version():
    """获取当前 gateway 版本"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace',
        )
        if result.returncode == 0:
            status = json.loads(result.stdout)
            return status.get("version", None)
    except Exception:
        pass
    return None


def load_state():
    """加载监测状态"""
    if not STATE_FILE.exists():
        return {"last_check_ms": 0, "version_change_detected": False, "verify_run": False}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_check_ms": 0, "version_change_detected": False, "verify_run": False}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def run_verify():
    """运行后置验证脚本"""
    if not VERIFY_SCRIPT.exists():
        print(f"[ERROR] Verify script not found: {VERIFY_SCRIPT}")
        return False

    try:
        result = subprocess.run(
            ["python", str(VERIFY_SCRIPT)],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace',
            cwd=str(WORKSPACE),
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] Failed to run verify script: {e}")
        return False


def main():
    timestamp = datetime.now().isoformat()
    print(f"[Update Monitor] {timestamp}")

    # 检查前置快照是否存在
    if not SNAPSHOT_BEFORE.exists():
        print("[INFO] No pre-update snapshot found. Monitor exiting (no update in progress).")
        return

    # 读取前置快照
    with open(SNAPSHOT_BEFORE, "r", encoding="utf-8") as f:
        before = json.load(f)

    before_version = None
    gw = before.get("gateway", None)
    if isinstance(gw, dict):
        before_version = gw.get("version", None)
    
    if not before_version:
        print("[WARN] No version in snapshot (gateway was unavailable when snapshot was taken).")
        print("[INFO] Falling back to file version info...")
        file_info = before.get("file_info", {})
        before_version = file_info.get("openclaw_npm_version", None)
    
    if not before_version:
        print("[WARN] Cannot determine before version. Skipping monitor.")
        return

    # 获取当前版本
    after_version = get_gateway_version()
    if not after_version:
        print("[WARN] Cannot get current gateway version. Gateway may be restarting...")
        return

    print(f"  Snapshot version: {before_version}")
    print(f"  Current version:  {after_version}")

    # 检测版本变化
    if before_version == after_version:
        print("[INFO] Version unchanged. Update not detected yet.")
        return

    print(f"\n[DETECTED] Version change: {before_version} → {after_version}")

    # 版本变化 → 运行后置验证
    state = load_state()
    if state.get("verify_run", False):
        print("[INFO] Verification already run. Skipping.")
        return

    print("\n" + "=" * 60)
    print("[ACTION] Running post-update verification...")
    print("=" * 60)
    ok = run_verify()

    # 更新状态
    state["version_change_detected"] = True
    state["verify_run"] = True
    state["after_version"] = after_version
    state["verify_timestamp"] = timestamp
    save_state(state)

    print("\n" + "=" * 60)
    if ok:
        print("[OK] Post-update verification completed.")
        print("\n请查看验证报告：")
        print("  memory/update_verify_*.md")
    else:
        print("[WARN] Post-update verification had errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()
