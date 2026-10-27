"""
TU-8 更新后置验证 v1.0
=======================
在 QClaw 重启后运行，对比前置快照并验证 3 项关键配置。

用法：
  python scripts/post_update_verify.py
"""

import json
import sys
import io
import subprocess
import difflib
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
SNAPSHOT_BEFORE = WORKSPACE / "memory" / "update_snapshot_before.json"
REPORT_FILE = WORKSPACE / "memory" / f"update_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"


def get_gateway_status():
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace',
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def get_openclaw_json():
    p = Path(r"C:\Users\qq366410837\.qclaw\openclaw.json")
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def verify_item(label, before_val, after_val, check_fn=None):
    """
    check_fn: optional custom check → (ok: bool, detail: str)
    returns: (ok, detail)
    """
    if check_fn:
        return check_fn(before_val, after_val)

    # default: exact match
    ok = (before_val == after_val)
    detail = f"before={before_val} → after={after_val}" if not ok else f"unchanged: {before_val}"
    return ok, detail


def main():
    timestamp = datetime.now().isoformat()
    print(f"[Post-Update Verify] {timestamp}")
    print("=" * 60)

    # 加载前置快照
    if not SNAPSHOT_BEFORE.exists():
        print(f"[ERROR] Pre-update snapshot not found: {SNAPSHOT_BEFORE}")
        print("Run `python scripts/pre_update_snapshot.py` before updating.")
        sys.exit(1)

    with open(SNAPSHOT_BEFORE, "r", encoding="utf-8") as f:
        before = json.load(f)

    print(f"Loaded pre-update snapshot: {SNAPSHOT_BEFORE}")
    print()

    # 获取当前状态
    after_gw = get_gateway_status()
    after_cfg = get_openclaw_json()

    report_lines = []
    report_lines.append(f"# 更新验证报告")
    report_lines.append(f"生成时间: {timestamp}")
    report_lines.append(f"快照时间: {before['timestamp']}")
    report_lines.append("")

    all_ok = True

    # ── 验证 1：OpenClaw 运行时版本 ──
    print("[1/3] Verifying OpenClaw runtime version...")
    report_lines.append("## ✅ 验证 1：OpenClaw 运行时版本")
    if after_gw:
        after_version = after_gw.get("version", "unknown")
        before_version = before.get("gateway", {}).get("version", "unknown")
        changed = after_version != before_version
        ok = True  # version change is expected
        detail = f"`{before_version}` → `{after_version}`" + ("  **[已更新]**" if changed else "  [未变更]")
        print(f"  {detail}")
        report_lines.append(f"- 前置版本: `{before_version}`")
        report_lines.append(f"- 当前版本: `{after_version}`")
        report_lines.append(f"- 状态: {'**已更新**' if changed else '未变更'}")
        if changed:
            report_lines.append(f"- ✅ 运行时版本已更新")
        else:
            report_lines.append(f"- ⚠️ 运行时版本未变更（可能仅客户端更新，或更新未生效）")
            all_ok = False
    else:
        print("  [ERROR] Cannot get gateway status")
        report_lines.append("- ❌ 无法获取 gateway 状态")
        all_ok = False
    report_lines.append("")

    # ── 验证 2：lossless-claw 插件是否还在 ──
    print("[2/3] Verifying lossless-claw plugin...")
    report_lines.append("## ✅ 验证 2：lossless-claw 插件状态")
    before_enabled = before.get("openclaw_json", {}).get("lossless_claw_enabled", "unknown")
    after_plugins = after_cfg.get("plugins", {}).get("entries", {}) if after_cfg else {}
    after_enabled = after_plugins.get("lossless-claw", {}).get("enabled", "not_found")

    ok = (after_enabled is True)
    print(f"  before.enabled = {before_enabled}")
    print(f"  after.enabled  = {after_enabled}")
    report_lines.append(f"- 前置状态: `enabled={before_enabled}`")
    report_lines.append(f"- 当前状态: `enabled={after_enabled}`")
    if ok:
        report_lines.append(f"- ✅ lossless-claw 插件已启用")
        print("  [OK] lossless-claw still enabled")
    else:
        report_lines.append(f"- ❌ lossless-claw 插件 **未启用**（更新后配置被重置）")
        report_lines.append(f"- **修复方法**：编辑 `openclaw.json`，设置 `plugins.entries.lossless-claw.enabled = true`")
        print("  [WARN] lossless-claw NOT enabled!")
        all_ok = False
    report_lines.append("")

    # ── 验证 3：LCM DB 路径配置 ──
    print("[3/3] Verifying LCM DB path config...")
    report_lines.append("## ✅ 验证 3：LCM DB 路径配置")
    before_dbpath = before.get("openclaw_json", {}).get("lossless_claw_config", {}).get("dbPath", "not_set")
    after_dbpath = after_plugins.get("lossless-claw", {}).get("config", {}).get("dbPath", "not_set")

    ok = (after_dbpath != "not_set")
    print(f"  before.dbPath = {before_dbpath}")
    print(f"  after.dbPath  = {after_dbpath}")
    report_lines.append(f"- 前置 dbPath: `{before_dbpath}`")
    report_lines.append(f"- 当前 dbPath: `{after_dbpath}`")
    if ok:
        report_lines.append(f"- ✅ LCM DB 路径已配置: `{after_dbpath}`")
        print("  [OK] LCM DB path configured")
    else:
        report_lines.append(f"- ❌ LCM DB 路径 **未配置**（lossless-claw 可能无法正常工作）")
        report_lines.append(f"- **修复方法**：在 `openclaw.json` 中添加 `plugins.entries.lossless-claw.config.dbPath`")
        print("  [WARN] LCM DB path NOT configured!")
        all_ok = False
    report_lines.append("")

    # ── 总结 ──
    print("=" * 60)
    report_lines.append("## 总结")
    if all_ok:
        print("[OK] All 3 verifications passed.")
        report_lines.append("✅ **所有验证通过**，更新成功，配置未丢失。")
    else:
        print("[WARN] Some verifications failed. See report.")
        report_lines.append("⚠️ **部分验证失败**，需要手动修复。")

    # 保存报告
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\nFull report saved to: {REPORT_FILE}")
    print(f"\nYou can also check the diff by comparing:")
    print(f"  before: {SNAPSHOT_BEFORE}")
    print(f"  after : run `python scripts/post_update_verify.py --dump-current` to save current state")


if __name__ == "__main__":
    main()
