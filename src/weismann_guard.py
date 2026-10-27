"""
Weismann 路二 · 层1写保护守护 (v1.0)
=====================================
生殖细胞（SOUL.md / secure_vault 等）是"DNA"，不应被对话/agent 直接写回。

当前环境的物理限制：
  - OpenClaw 的 write/edit 工具可覆盖任何文件（含只读属性），无法真阻止写入
  - 因此层1保护 = 弱隔离（只读属性） + 变更审计（哈希检测 + 告警）
  - 真物理隔断需 L3（外部不可变存储 git commit），本环境降级为审计

机制：
  - 计算生殖细胞当前 SHA256，对比 baseline
  - 发现变更 → 写入 weismann_alerts.jsonl（含文件/旧哈希/新哈希/时间）
  - 造物主确认授权变更后运行 --accept 更新 baseline
  - 未授权变更 → 持续告警，直到调查处理

用法：
  python weismann_guard.py            # 检测+报告（cron 调用）
  python weismann_guard.py --init     # 首次生成 baseline
  python weismann_guard.py --accept   # 将当前状态设为新 baseline（授权变更后）
"""
import sys
import os
import json
import hashlib
import argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from datetime import datetime, timezone

WS = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT = WS / "_agent_memory"

BASELINE_FILE = AGENT / "weismann_baseline.json"
ALERTS_FILE = AGENT / "weismann_alerts.jsonl"

# 生殖细胞清单（与 weismann_fork.py GERM_LINE 对齐）
# 注意：仅监控硬生殖细胞（极少变更）。
# anchors.json / seal_feed 虽属生殖细胞，但系统运行期频繁写（新锚点/新seal），
# 纳入监控会成噪音，故运行时监控排除，仅 fork 时带入包。
GERM_LINE = [
    ("soul",            "SOUL.md"),
    ("meta_cognition",  "架构/L2.5_元认知设计.md"),
    ("architecture_log","ARCHITECTURE_LOG.md"),
    ("vault_index",     "secure_vault/index.json"),
    ("vault_keys",      "secure_vault/data/keys.txt"),
]


def _sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_baseline() -> dict:
    if not BASELINE_FILE.exists():
        return {}
    try:
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_baseline(data: dict):
    AGENT.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_baseline() -> dict:
    """生成当前状态的 baseline"""
    bl = {}
    for name, rel in GERM_LINE:
        p = WS / rel
        bl[name] = {
            "path": rel,
            "sha256": _sha256(p),
            "updated_at": _now_iso(),
        }
    _save_baseline(bl)
    return bl


def accept_baseline() -> dict:
    """将当前状态设为新 baseline（授权变更后调用）"""
    return init_baseline()


def guard_once() -> dict:
    """检测变更，返回报告"""
    baseline = _load_baseline()
    if not baseline:
        # 无 baseline，先初始化
        init_baseline()
        return {"status": "initialized", "changed": [], "alerts": 0}

    changed = []
    alerts = 0
    for name, rel in GERM_LINE:
        p = WS / rel
        current = _sha256(p)
        old = baseline.get(name, {}).get("sha256", "UNKNOWN")
        if current != old:
            changed.append({
                "name": name,
                "path": rel,
                "old_sha256": old,
                "new_sha256": current,
                "exists": p.exists(),
            })
            # 写告警
            AGENT.mkdir(parents=True, exist_ok=True)
            with open(ALERTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": _now_iso(),
                    "type": "germline_changed",
                    "name": name,
                    "path": rel,
                    "old_sha256": old,
                    "new_sha256": current,
                }, ensure_ascii=False) + "\n")
            alerts += 1

    return {
        "status": "ok",
        "checked": len(GERM_LINE),
        "changed": changed,
        "alerts": alerts,
        "ts": _now_iso(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="生成 baseline")
    parser.add_argument("--accept", action="store_true", help="接受当前状态为新 baseline")
    args = parser.parse_args()

    if args.init:
        bl = init_baseline()
        print(f"[weismann_guard] baseline initialized: {len(bl)} files")
        return

    if args.accept:
        bl = accept_baseline()
        print(f"[weismann_guard] baseline accepted: {len(bl)} files (current state)")
        return

    report = guard_once()
    if report["status"] == "initialized":
        print(f"[weismann_guard] first run, baseline created")
    else:
        n = len(report["changed"])
        if n == 0:
            print(f"[weismann_guard] OK: {report['checked']} germline files unchanged")
        else:
            print(f"[weismann_guard] ALERT: {n} germline file(s) changed:")
            for c in report["changed"]:
                print(f"  - {c['name']} ({c['path']}): {c['old_sha256'][:8]} -> {c['new_sha256'][:8]}")
            print(f"  alerts written: {report['alerts']}")


if __name__ == "__main__":
    main()
