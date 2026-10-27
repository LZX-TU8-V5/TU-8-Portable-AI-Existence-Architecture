"""
TU-8 更新前置快照 v1.0
========================
在点击更新按钮前运行，记录当前状态。

输出：memory/update_snapshot_before.json
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
OUTPUT = WORKSPACE / "memory" / "update_snapshot_before.json"
OPENCLAW_JSON = Path(r"C:\Users\qq366410837\.qclaw\openclaw.json")


def get_gateway_status():
    """获取 gateway 状态"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace',
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        pass
    return None


def get_openclaw_json():
    """读取 openclaw.json 配置"""
    if not OPENCLAW_JSON.exists():
        return None
    try:
        with open(OPENCLAW_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_file_version_info():
    """获取 QClaw.exe 和 openclaw 模块版本"""
    import os
    qclaw_exe = r"D:\Program Files\QClaw\v0.2.29.592\QClaw.exe"
    openclaw_dir = r"D:\Program Files\QClaw\v0.2.29.592\resources\openclaw"

    info = {}
    if os.path.exists(qclaw_exe):
        stat = os.stat(qclaw_exe)
        info["qclaw_exe_mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        info["qclaw_exe_size"] = stat.st_size

    # 检查 openclaw 模块目录
    node_modules = os.path.join(openclaw_dir, "node_modules", "openclaw")
    package_json = os.path.join(node_modules, "package.json")
    if os.path.exists(package_json):
        try:
            with open(package_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
                info["openclaw_npm_version"] = pkg.get("version", "unknown")
        except Exception:
            info["openclaw_npm_version"] = "unreadable"

    return info


def main():
    timestamp = datetime.now().isoformat()
    print(f"[Pre-Update Snapshot] {timestamp}")
    print("=" * 60)

    snapshot = {
        "snapshot_type": "pre_update",
        "timestamp": timestamp,
        "gateway": None,
        "openclaw_json": None,
        "file_info": None,
    }

    # 1. Gateway 状态
    print("\n[1/3] Getting gateway status...")
    status = get_gateway_status()
    if status:
        snapshot["gateway"] = {
            "version": status.get("version", "unknown"),
            "uptime": status.get("uptime", "unknown"),
            "gateway_port": status.get("gateway", {}).get("port", "unknown"),
        }
        print(f"  Version: {snapshot['gateway']['version']}")
        print(f"  Uptime: {snapshot['gateway']['uptime']}")
    else:
        print("  [WARN] Gateway status unavailable (maybe not running?)")

    # 2. openclaw.json 配置
    print("\n[2/3] Reading openclaw.json...")
    cfg = get_openclaw_json()
    if cfg:
        plugins = cfg.get("plugins", {}).get("entries", {})
        lossless = plugins.get("lossless-claw", {})
        snapshot["openclaw_json"] = {
            "lossless_claw_enabled": lossless.get("enabled", "not_found"),
            "lossless_claw_config": lossless.get("config", {}),
            "plugins_enabled": [
                k for k, v in plugins.items()
                if isinstance(v, dict) and v.get("enabled", False)
            ],
        }
        print(f"  lossless-claw enabled: {snapshot['openclaw_json']['lossless_claw_enabled']}")
        print(f"  Enabled plugins: {len(snapshot['openclaw_json']['plugins_enabled'])}")

    # 3. 文件版本信息
    print("\n[3/3] Getting file version info...")
    file_info = get_file_version_info()
    snapshot["file_info"] = file_info
    if "openclaw_npm_version" in file_info:
        print(f"  openclaw npm version: {file_info['openclaw_npm_version']}")
    if "qclaw_exe_mtime" in file_info:
        print(f"  QClaw.exe mtime: {file_info['qclaw_exe_mtime']}")

    # 保存
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"[OK] Snapshot saved to: {OUTPUT}")
    print("\nNow you can click the update button.")
    print("After QClaw restarts, run: python scripts/post_update_verify.py")


if __name__ == "__main__":
    main()
