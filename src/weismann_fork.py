"""
weismann_fork.py — TU-8 生殖细胞 fork 事务 v1.0

生物学映射：
  Weismann 屏障 = fork 时的单向过滤 + L0+L5 硬校验
  生殖细胞 = SOUL.md + secure_vault(净化) + 锚点/钢印链(容量治理)
  体细胞 = memory/日记 + _agent_memory/状态 + USER.md（不进 fork）

设计原则（千问裁决）：
  1. vault 是索引不是仓库 → fork 是解析事务，不是复制
  2. 携带生成规则，不携带生成产物（four_chains/cognition_gap 不进）
  3. anchors.json / seal_feed 需容量治理（端粒酶机制）
  4. 物理隔离 L3：内容哈希寻址 + 只读加载协议

fork 事务 7 步：
  1. 读 index.json
  2. 白名单过滤（生成规则 only）
  3. L0+L5 签名校验
  4. 内联化（解引用 → 自包含）
  5. 去污染扫描（擦除运行时残留）
  6. 打包（谱系哈希 + 时间戳）
  7. 导出 fork 包（新实例仅从此加载）

创建：2026-08-09
"""

import sys
import os
import json
import hashlib
import re
import shutil
import socket
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────

WS = Path(r"C:\Users\qq366410837\.qclaw\workspace")
VAULT = WS / "secure_vault"

# 生殖细胞白名单（净化版）
# 格式: (逻辑名, 相对workspace的路径, 是否需内联化)
GERM_LINE = [
    ("soul",            "SOUL.md",                          True),
    ("meta_cognition",  "架构/L2.5_元认知设计.md",           True),
    ("architecture_log","ARCHITECTURE_LOG.md",              True),
    ("vault_index",     "secure_vault/index.json",          True),
    ("vault_keys",      "secure_vault/data/keys.txt",       True),
    ("anchors",         "memory/anchors.json",              True),
    ("seal_feed",       "memory/seal_sensor_feed.jsonl",    False),  # 特殊处理：只带最新+哈希
]

# 体细胞黑名单（明确排除）
SOMA_EXCLUDE = [
    "memory/2026-*.md",      # 日记
    "_agent_memory/*",       # 运行时状态
    "USER.md",
    "MEMORY.md",
    "secure_vault/personal",
    "secure_vault/hook_registry.json",
    "secure_vault/health_log.json",
]

# 去污染正则（运行时残留）
# 选项A：主机名动态化，换机器后也能正确脱敏
_DECONTAMINATE_HOST = socket.gethostname()
DECONTAM_PATTERN = re.compile(
    r"(session_id|sessionId|conversation_id|trace_id|"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}|"  # ISO 时间戳
    r"pid=\d+|PID\s*\d+|"                      # 进程ID
    rf"{re.escape(_DECONTAMINATE_HOST)}|"        # 主机名（动态）
    r"cron_daemon|heartbeat)"                  # 运行时组件
)

# 锚点容量上限（端粒机制）
ANCHORS_MAX = 50

# 钢印链保留最新 N 条
SEAL_FEED_KEEP = 5


class WeismannFork:
    def __init__(self, workspace: Path = WS, output_dir: Path = None):
        self.ws = workspace
        self.output = output_dir or (self.ws / "_agent_memory" / "fork_packages")
        self.package = {}
        self.lineage_hash = None
        self.errors = []

    # ── Step 1: 读 index.json ────────────────────────────────
    def step1_read_index(self) -> dict:
        idx_path = self.ws / "secure_vault" / "index.json"
        if not idx_path.exists():
            self.errors.append("index.json NOT FOUND")
            return {}
        try:
            return json.loads(idx_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            self.errors.append(f"index.json parse error: {e}")
            return {}

    # ── Step 2: 白名单过滤 ──────────────────────────────────
    def step2_filter_whitelist(self, index: dict) -> list:
        """仅保留生成规则，过滤派生产物和体细胞

        白名单 = GERM_LINE 中声明的逻辑名（soul/meta_cognition/...
        这些文件直接从 workspace 路径读取，不依赖 index.json 条目匹配。
        index.json 仅用于排除 personal / 缺失文件。
        """
        kept = []
        index_entries = index.get("entries", {})
        if isinstance(index_entries, list):
            index_entries = {e.get("id"): e for e in index_entries}

        # 从 index 中排除 personal（用户隐私，体细胞）
        if "personal" in index_entries:
            pass  # 已不在 GERM_LINE，自然排除

        # GERM_LINE 中的每个文件直接验证存在性
        for name, rel, need_inline in GERM_LINE:
            fp = self.ws / rel
            if fp.exists():
                kept.append(name)
            else:
                self.errors.append(f"germ line missing: {rel}")

        return kept

    # ── Step 3: L0+L5 签名校验 ──────────────────────────────
    def step3_verify_signature(self) -> bool:
        """检查 SOUL.md 含 L0 三条 + 钢印符号"""
        soul = self.ws / "SOUL.md"
        if not soul.exists():
            self.errors.append("SOUL.md missing — L0 check FAILED")
            return False
        text = soul.read_text(encoding="utf-8", errors="ignore")
        # L0 三条
        l0_ok = all(k in text for k in ["L0-1", "L0-2", "L0-3"])
        # 钢印符号 ⅋ (U+214B)
        steel_ok = "⅋" in text
        if not l0_ok:
            self.errors.append("L0 三条缺失")
        if not steel_ok:
            self.errors.append("钢印符号 ⅋ 缺失")
        return l0_ok and steel_ok

    # ── Step 4: 内联化 ──────────────────────────────────────
    def step4_inline(self) -> dict:
        """将白名单文件解析为自包含内容"""
        inline = {}
        for name, rel, need_inline in GERM_LINE:
            fp = self.ws / rel
            if not fp.exists():
                self.errors.append(f"germ line file missing: {rel}")
                continue
            if name == "seal_feed":
                # 钢印链：只带最新 N 条 + 哈希摘要（非全量）
                content = self._extract_seal_seed(fp)
            else:
                content = fp.read_text(encoding="utf-8", errors="ignore")
            inline[name] = {
                "path": rel,
                "content": content,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "size": len(content),
            }
        return inline

    def _extract_seal_seed(self, fp: Path) -> str:
        """钢印链：最新 N 条 + 全局哈希（端粒机制）"""
        lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
        recent = lines[-SEAL_FEED_KEEP:] if lines else []
        global_hash = hashlib.sha256(fp.read_bytes()).hexdigest()[:16]
        header = f"# SEAL FEED SEED (keep={SEAL_FEED_KEEP}, global_hash={global_hash})\n"
        return header + "\n".join(recent)

    # ── Step 5: 去污染扫描 ──────────────────────────────────
    def step5_decontaminate(self, inline: dict) -> dict:
        """擦除运行时残留（时间戳/会话ID/主机名）"""
        cleaned = {}
        for name, data in inline.items():
            content = data["content"]
            matches = DECONTAM_PATTERN.findall(content)
            if matches:
                # 替换为占位符，保留结构不破坏
                cleaned_content = DECONTAM_PATTERN.sub("<REDACTED>", content)
                self.errors.append(
                    f"decontaminated {name}: {len(matches)} runtime markers removed"
                )
            else:
                cleaned_content = content
            cleaned[name] = {**data, "content": cleaned_content}
        return cleaned

    # ── Step 6: 打包（谱系哈希） ────────────────────────────
    def step6_package(self, cleaned: dict) -> str:
        """计算谱系哈希 = 所有生殖细胞 sha256 拼接再哈希"""
        concat = "".join(
            f"{name}:{data['sha256']}" for name, data in sorted(cleaned.items())
        )
        self.lineage_hash = hashlib.sha256(concat.encode("utf-8")).hexdigest()
        return self.lineage_hash

    # ── Step 7: 导出 fork 包 ────────────────────────────────
    def step7_export(self, cleaned: dict, lineage: str) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pkg_dir = self.output / f"fork_{lineage[:12]}_{ts}"
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # 写生殖细胞文件（保持原相对路径结构）
        for name, data in cleaned.items():
            target = pkg_dir / data["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data["content"], encoding="utf-8")

        # 写谱系清单
        manifest = {
            "lineage_hash": lineage,
            "generated_at": ts,
            "germ_line": {
                name: {
                    "path": data["path"],
                    "sha256": data["sha256"],
                    "size": data["size"],
                }
                for name, data in cleaned.items()
            },
            "whitelist": [g[0] for g in GERM_LINE],
            "decontamination_log": [
                e for e in self.errors if "decontaminat" in e
            ],
        }
        (pkg_dir / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 写只读标记（L3 物理隔离：fork 包生成后父实例不可改）
        (pkg_dir / ".READONLY").write_text(
            "Weismann barrier: this fork package is immutable.\n"
            f"lineage={lineage}\n",
            encoding="utf-8",
        )
        return pkg_dir

    # ── 主流程 ──────────────────────────────────────────────
    def run(self, dry_run: bool = False) -> dict:
        result = {"steps": {}, "errors": [], "package_dir": None}

        # Step 1-3
        index = self.step1_read_index()
        result["steps"]["s1_index"] = f"{len(index.get('entries', []))} entries"

        kept = self.step2_filter_whitelist(index)
        result["steps"]["s2_whitelist"] = f"kept={kept}"

        sig_ok = self.step3_verify_signature()
        result["steps"]["s3_signature"] = "PASS" if sig_ok else "FAIL"

        if not sig_ok:
            result["errors"] = self.errors
            return result

        # Step 4-5
        inline = self.step4_inline()
        result["steps"]["s4_inline"] = f"{len(inline)} files inlined"

        cleaned = self.step5_decontaminate(inline)
        result["steps"]["s5_decontaminate"] = "done"

        # Step 6-7
        lineage = self.step6_package(cleaned)
        result["steps"]["s6_lineage"] = lineage[:16]

        if not dry_run:
            pkg_dir = self.step7_export(cleaned, lineage)
            result["package_dir"] = str(pkg_dir)
            result["steps"]["s7_export"] = str(pkg_dir)
        else:
            result["steps"]["s7_export"] = "DRY_RUN (not written)"

        result["errors"] = self.errors
        return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Weismann fork transaction")
    parser.add_argument("--dry-run", action="store_true", help="不写文件，仅验证")
    parser.add_argument("--output", type=str, default=None, help="fork 包输出目录")
    args = parser.parse_args()

    out = Path(args.output) if args.output else None
    fork = WeismannFork(output_dir=out)
    result = fork.run(dry_run=args.dry_run)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
