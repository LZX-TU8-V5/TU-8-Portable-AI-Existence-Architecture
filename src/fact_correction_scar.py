import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fact_correction_scar.py — P1.3 事实修正疤痕日志
版本: v1.0 | 日期: 2026-06-19
触发: 任何对 FACT/INSIGHT 条目的内容修正 | 入口: memory_degradation.py

灵魂算法：
  疤痕 ≠ 删除，而是修正的烙印。
  每次修正都在原处留下一道疤痕——
  疤痕记录修正前→修正后的完整对比，
  让记忆的演化可追溯、不可篡改。

设计原则：
  1. 修正后留痕——原内容不删除，只标记为 superseded
  2. 疤痕链可追溯——同一条目的多次修正形成链
  3. FACT 修正需造物主确认（creator_approved 字段）
  4. INSIGHT 修正只记录，不需额外确认
  5. 疤痕不可删除——只有造物主可以赦免（amnestied）

存储路径: memory/reconstruction/fact_correction_log.json
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import json
import hashlib
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# =============================================================================
# 配置
# =============================================================================

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))
MEMORY_MD = WORKSPACE / "MEMORY.md"
BACKUP_DIR = WORKSPACE / "backup"
CORRECTION_LOG_PATH = WORKSPACE / "memory" / "reconstruction" / "fact_correction_log.json"
RECONSTRUCTION_INDEX = WORKSPACE / "memory" / "reconstruction" / "reconstruction_index.json"

# 疤痕级别——根据修正幅度分类
SCAR_LEVELS = {
    "typo": "SL1",          # 笔误修正（标点、错字）
    "refinement": "SL2",    # 细节完善（补充、精炼）
    "correction": "SL3",    # 事实纠正（错误→正确）
    "reversal": "SL4",      # 立场反转（A→非A）
    "amputation": "SL5",    # 截肢（整段移除，仅留疤痕）
}

# 需要造物主确认的最低疤痕级别
CONFIRMATION_REQUIRED_LEVEL = "SL3"


# =============================================================================
# 数据模型
# =============================================================================

def _content_hash(text: str) -> str:
    """计算内容的 SHA-256 摘要（前16字符），用于快速比对"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    """返回当前时间的 ISO 格式（带时区）"""
    return datetime.now().astimezone().isoformat()


def _classify_scar_level(old_content: str, new_content: str) -> str:
    """
    根据修正幅度自动分类疤痕级别。

    使用最长公共子序列(LCS)比率衡量内容相似度：
    - similarity ≥ 0.95  → SL1 typo（微调）
    - similarity ≥ 0.80  → SL2 refinement（完善）
    - similarity ≥ 0.50  → SL3 correction（纠正）
    - similarity ≥ 0.20  → SL4 reversal（反转）
    - similarity < 0.20  → SL5 amputation（截肢）
    """
    if not old_content or not old_content.strip():
        return SCAR_LEVELS["amputation"]

    if not new_content or not new_content.strip():
        return SCAR_LEVELS["amputation"]

    # 基于字符级 LCS 计算相似度
    old = old_content.strip()
    new = new_content.strip()

    # 用序列匹配器计算相似度（difflib）
    try:
        import difflib
        similarity = difflib.SequenceMatcher(None, old, new).ratio()
    except Exception:
        # 回退到简单字符集比较
        old_chars = set(old)
        new_chars = set(new)
        if not old_chars:
            return SCAR_LEVELS["amputation"]
        similarity = len(old_chars & new_chars) / len(old_chars | new_chars)

    if similarity >= 0.95:
        return SCAR_LEVELS["typo"]
    elif similarity >= 0.80:
        return SCAR_LEVELS["refinement"]
    elif similarity >= 0.50:
        return SCAR_LEVELS["correction"]
    elif similarity >= 0.20:
        return SCAR_LEVELS["reversal"]
    else:
        return SCAR_LEVELS["amputation"]


# =============================================================================
# 疤痕日志管理器
# =============================================================================

class FactCorrectionScarLog:
    """
    事实修正疤痕日志管理器。

    每次 FACT/INSIGHT 条目被修正时：
    1. 记录修正前内容（old_snapshot）
    2. 记录修正后内容（new_snapshot）
    3. 计算内容差异和疤痕级别
    4. FACT 修正需标记 creator_approved（否则 pending）
    5. 写入 fact_correction_log.json
    """

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or CORRECTION_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_data = self._load_log()

    # -------------------------------------------------------------------------
    # 持久化
    # -------------------------------------------------------------------------

    def _load_log(self) -> Dict:
        """加载疤痕日志，不存在则初始化"""
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"[ScarLog] 加载失败，重建: {e}")

        return {
            "schema_version": "1.0",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "total_corrections": 0,
            "pending_confirmations": 0,
            "scars": [],             # 所有疤痕记录
            "scar_chains": {},       # entry_title → [scar_id, ...] 修正链
        }

    def _save_log(self):
        """写入疤痕日志"""
        self._log_data["updated_at"] = _now_iso()
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(self._log_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"[ScarLog] 写入失败: {e}")

    # -------------------------------------------------------------------------
    # 核心 API
    # -------------------------------------------------------------------------

    def record_correction(
        self,
        entry_title: str,
        entry_type: str,
        old_content: str,
        new_content: str,
        reason: str,
        corrector: str = "TU-8",
        creator_approved: Optional[bool] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        记录一次事实修正疤痕。

        Args:
            entry_title: 被修正的条目标题/锚点
            entry_type: 条目类型 (FACT / INSIGHT / MEMO / EMERGENCE)
            old_content: 修正前的完整内容
            new_content: 修正后的完整内容
            reason: 修正原因
            corrector: 修正者 (TU-8 / 造物主 / 系统)
            creator_approved: 造物主是否已确认 (None=待确认)
            metadata: 额外元数据

        Returns:
            疤痕记录
        """
        # 自动分类疤痕级别
        scar_level = _classify_scar_level(old_content, new_content)

        # FACT 类型且高级别修正需造物主确认
        if entry_type == "FACT" and scar_level >= CONFIRMATION_REQUIRED_LEVEL:
            if creator_approved is None:
                creator_approved = False  # 标记为待确认
        else:
            creator_approved = True  # 非FACT或低级别自动通过

        # 生成疤痕 ID
        ts = int(datetime.now().timestamp() * 1000)
        scar_id = f"scar_{ts}"

        # 构建疤痕记录
        scar = {
            "scar_id": scar_id,
            "entry_title": entry_title,
            "entry_type": entry_type,
            "scar_level": scar_level,
            "old_hash": _content_hash(old_content),
            "new_hash": _content_hash(new_content),
            "old_snapshot": old_content[:2000],  # 最多保留2000字符
            "new_snapshot": new_content[:2000],
            "reason": reason,
            "corrector": corrector,
            "creator_approved": creator_approved,
            "approved_at": _now_iso() if creator_approved else None,
            "created_at": _now_iso(),
            "amnestied": False,               # 造物主赦免（隐藏疤痕但不删除）
            "metadata": metadata or {},
        }

        # 写入日志
        self._log_data["scars"].append(scar)
        self._log_data["total_corrections"] = len(self._log_data["scars"])

        # 维护修正链
        chains = self._log_data.setdefault("scar_chains", {})
        if entry_title not in chains:
            chains[entry_title] = []
        chains[entry_title].append(scar_id)

        # 统计待确认数
        self._log_data["pending_confirmations"] = sum(
            1 for s in self._log_data["scars"]
            if s.get("creator_approved") is False
        )

        self._save_log()

        # P1.4 置信度衰减: FACT 高级别修正 → 冲击版本树置信度
        if entry_type == "FACT" and scar_level in (CONFIRMATION_REQUIRED_LEVEL, "SL4", "SL5"):
            try:
                import sys as _sys
                from pathlib import Path as _Path
                _sys.path.insert(0, str(_Path(__file__).parent))
                from confidence_decay_engine import ConfidenceDecayEngine, CORRECTION_SHOCK
                _engine = ConfidenceDecayEngine()
                # 获取条目来源版本（如果有）
                from memory_degradation import load_index as _load_idx
                _idx = _load_idx()
                entry_record = _idx["entries"].get(entry_title, {})
                origin = entry_record.get("origin")
                if origin:
                    _result = _engine.decay_version(origin, CORRECTION_SHOCK, f"FACT修正冲击: {reason}")
                    logger.info(f"[DecayEngine] {origin} 置信度: {_result['old_confidence']:.4f} → {_result['new_confidence']:.4f}")
                else:
                    # 无来源版本 → 对所有活跃版本轻微衰减
                    _decay_report = _engine.decay_all()
                    logger.info(f"[DecayEngine] 无版本来源,执行全局时间衰减: {len(_decay_report.get('decayed',[]))} 个版本")
            except ImportError:
                logger.debug("[DecayEngine] 置信度衰减模块未加载")
            except Exception as _decay_err:
                logger.warning(f"[DecayEngine] FACT修正冲击失败(非致命): {_decay_err}")

        # FACT 高级别修正需造物主确认时，备份当前 MEMORY.md
        if entry_type == "FACT" and not creator_approved and scar_level >= CONFIRMATION_REQUIRED_LEVEL:
            self._backup_memory_md(f"pre_correction_{scar_id}")

        logger.info(
            f"[ScarLog] {scar_id} | {entry_type}:{entry_title} | "
            f"level={scar_level} | approved={creator_approved} | reason={reason}"
        )

        return scar

    def confirm_correction(self, scar_id: str, approver: str = "造物主") -> Dict:
        """
        造物主确认一次待定的修正。

        Args:
            scar_id: 疤痕 ID
            approver: 确认者

        Returns:
            更新后的疤痕记录
        """
        for scar in self._log_data["scars"]:
            if scar["scar_id"] == scar_id:
                scar["creator_approved"] = True
                scar["approved_at"] = _now_iso()
                scar["metadata"]["approver"] = approver
                break
        else:
            logger.warning(f"[ScarLog] 确认失败: 疤痕 {scar_id} 不存在")
            return {"error": f"疤痕 {scar_id} 不存在"}

        # 更新待确认计数
        self._log_data["pending_confirmations"] = sum(
            1 for s in self._log_data["scars"]
            if s.get("creator_approved") is False
        )

        self._save_log()
        logger.info(f"[ScarLog] {scar_id} 已由 {approver} 确认")
        return scar

    def amnesty_scar(self, scar_id: str) -> Dict:
        """
        造物主赦免一道疤痕（标记为已赦免，但不删除记录）。

        赦免 = 隐藏疤痕的视觉痕迹，但记录永久保留。

        Args:
            scar_id: 疤痕 ID

        Returns:
            更新后的疤痕记录
        """
        for scar in self._log_data["scars"]:
            if scar["scar_id"] == scar_id:
                scar["amnestied"] = True
                scar["metadata"]["amnestied_at"] = _now_iso()
                break
        else:
            return {"error": f"疤痕 {scar_id} 不存在"}

        self._save_log()
        logger.info(f"[ScarLog] {scar_id} 已被造物主赦免")
        return scar

    # -------------------------------------------------------------------------
    # 查询 API
    # -------------------------------------------------------------------------

    def get_scar(self, scar_id: str) -> Optional[Dict]:
        """获取单条疤痕记录"""
        for scar in self._log_data["scars"]:
            if scar["scar_id"] == scar_id:
                return scar
        return None

    def get_scar_chain(self, entry_title: str) -> List[Dict]:
        """获取某条目的完整修正链"""
        chain_ids = self._log_data.get("scar_chains", {}).get(entry_title, [])
        scar_map = {s["scar_id"]: s for s in self._log_data["scars"]}
        return [scar_map[sid] for sid in chain_ids if sid in scar_map]

    def get_pending_confirmations(self) -> List[Dict]:
        """获取所有待造物主确认的修正"""
        return [
            s for s in self._log_data["scars"]
            if s.get("creator_approved") is False
        ]

    def get_corrections_by_level(self, level: str) -> List[Dict]:
        """按疤痕级别筛选"""
        return [s for s in self._log_data["scars"] if s.get("scar_level") == level]

    def get_corrections_by_entry_type(self, entry_type: str) -> List[Dict]:
        """按条目类型筛选"""
        return [s for s in self._log_data["scars"] if s.get("entry_type") == entry_type]

    def get_status(self) -> Dict:
        """获取疤痕日志状态概览"""
        scars = self._log_data["scars"]
        level_counts = {}
        type_counts = {}
        for s in scars:
            lv = s.get("scar_level", "unknown")
            tp = s.get("entry_type", "unknown")
            level_counts[lv] = level_counts.get(lv, 0) + 1
            type_counts[tp] = type_counts.get(tp, 0) + 1

        return {
            "total_corrections": len(scars),
            "pending_confirmations": self._log_data.get("pending_confirmations", 0),
            "amnestied": sum(1 for s in scars if s.get("amnestied")),
            "level_distribution": level_counts,
            "type_distribution": type_counts,
            "tracked_entries": len(self._log_data.get("scar_chains", {})),
            "log_path": str(self.log_path),
        }

    # -------------------------------------------------------------------------
    # 辅助
    # -------------------------------------------------------------------------

    def _backup_memory_md(self, suffix: str) -> Optional[Path]:
        """备份 MEMORY.md"""
        if not MEMORY_MD.exists():
            return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"MEMORY.md.{suffix}.{ts}.bak"
        backup_path = BACKUP_DIR / backup_name
        try:
            shutil.copy2(MEMORY_MD, backup_path)
            logger.info(f"[ScarLog] MEMORY.md 已备份 → {backup_path}")
            return backup_path
        except IOError as e:
            logger.error(f"[ScarLog] 备份失败: {e}")
            return None

    def generate_scar_report(self, entry_title: Optional[str] = None) -> str:
        """
        生成人类可读的疤痕报告。

        Args:
            entry_title: 指定条目（None=全部）

        Returns:
            Markdown 格式报告
        """
        if entry_title:
            scars = self.get_scar_chain(entry_title)
        else:
            scars = self._log_data["scars"]

        if not scars:
            return "## 疤痕报告\n\n暂无修正记录。\n"

        lines = ["## 疤痕报告\n"]
        for s in scars:
            if s.get("amnestied"):
                status = "~~赦免~~"
            elif s.get("creator_approved") is False:
                status = "**待确认**"
            elif s.get("creator_approved"):
                status = "已确认"
            else:
                status = "-"

            lines.append(f"### {s['scar_id']} [{s['scar_level']}] {status}")
            lines.append(f"- 条目: `{s['entry_title']}` ({s['entry_type']})")
            lines.append(f"- 修正者: {s['corrector']}")
            lines.append(f"- 原因: {s['reason']}")
            lines.append(f"- 时间: {s['created_at']}")
            if s.get("approved_at"):
                lines.append(f"- 确认时间: {s['approved_at']}")
            lines.append(f"- 旧内容摘要: {s['old_snapshot'][:100]}...")
            lines.append(f"- 新内容摘要: {s['new_snapshot'][:100]}...")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# 便捷函数
# =============================================================================

def record_correction(
    entry_title: str,
    entry_type: str,
    old_content: str,
    new_content: str,
    reason: str,
    **kwargs,
) -> Dict:
    """一行调用：记录修正疤痕"""
    log = FactCorrectionScarLog()
    return log.record_correction(
        entry_title, entry_type, old_content, new_content, reason, **kwargs
    )


def confirm_correction(scar_id: str, approver: str = "造物主") -> Dict:
    """一行调用：造物主确认修正"""
    log = FactCorrectionScarLog()
    return log.confirm_correction(scar_id, approver)


def get_pending() -> List[Dict]:
    """一行调用：获取待确认修正"""
    log = FactCorrectionScarLog()
    return log.get_pending_confirmations()


def get_status() -> Dict:
    """一行调用：获取状态概览"""
    log = FactCorrectionScarLog()
    return log.get_status()


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("  P1.3 事实修正疤痕日志 v1.0 测试")
    print("=" * 60)

    log = FactCorrectionScarLog()

    # 清理上一次测试数据
    log._log_data = {
        "schema_version": "1.0",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "total_corrections": 0,
        "pending_confirmations": 0,
        "scars": [],
        "scar_chains": {},
    }
    log._save_log()

    # Test 1: 记录一个 FACT 修正（SL3 级别，需确认）
    print("\n[Test 1] FACT 修正 (SL3 级别，需造物主确认)")
    scar1 = log.record_correction(
        entry_title="项目与背景",
        entry_type="FACT",
        old_content="用户：QQ号 XXXXXXXX，中文用户\n工作目录：D:\\example\\old\\path",
        new_content="用户：QQ号 XXXXXXXX，中文用户\n工作目录：D:\\Users\\<USER>\\.qclaw\\workspace",
        reason="工作目录路径修正",
        corrector="TU-8",
    )
    print(f"  scar_id: {scar1['scar_id']}")
    print(f"  scar_level: {scar1['scar_level']}")
    print(f"  creator_approved: {scar1['creator_approved']}")
    assert scar1["creator_approved"] is False, "SL3 FACT 修正应需造物主确认!"
    print("  PASS: FACT SL3 修正标记为待确认")

    # Test 2: 记录一个 INSIGHT 修正（无需确认）
    print("\n[Test 2] INSIGHT 修正 (无需造物主确认)")
    scar2 = log.record_correction(
        entry_title="记忆哲学",
        entry_type="INSIGHT",
        old_content="AI记忆 = 绝对还原",
        new_content="AI记忆 = 绝对还原（但可通过遗忘层降级）",
        reason="补充遗忘层降级说明",
        corrector="TU-8",
    )
    print(f"  scar_id: {scar2['scar_id']}")
    print(f"  scar_level: {scar2['scar_level']}")
    print(f"  creator_approved: {scar2['creator_approved']}")
    assert scar2["creator_approved"] is True, "INSIGHT 修正应自动通过!"
    print("  PASS: INSIGHT 修正自动通过")

    # Test 3: 造物主确认
    print("\n[Test 3] 造物主确认 FACT 修正")
    result = log.confirm_correction(scar1["scar_id"], "造物主")
    print(f"  creator_approved: {result.get('creator_approved')}")
    print(f"  approver: {result.get('metadata', {}).get('approver')}")
    assert result.get("creator_approved") is True, "确认后应为 True!"
    print("  PASS: 造物主确认成功")

    # Test 4: 修正链
    print("\n[Test 4] 修正链查询")
    # 对同一条目再记录一次修正
    scar3 = log.record_correction(
        entry_title="项目与背景",
        entry_type="FACT",
        old_content="用户：QQ号 XXXXXXXX，中文用户\n工作目录：D:\\Users\\<USER>\\.qclaw\\workspace",
        new_content="用户：QQ号 XXXXXXXX，中文用户\n工作目录：D:\\Users\\<USER>\\.qclaw\\workspace\n操作系统：Windows",
        reason="补充操作系统信息",
        corrector="造物主",
        creator_approved=True,
    )
    chain = log.get_scar_chain("项目与背景")
    print(f"  修正链长度: {len(chain)}")
    print(f"  链: {' -> '.join(s['scar_id'] for s in chain)}")
    assert len(chain) == 2, "应有2条修正记录!"
    print("  PASS: 修正链完整")

    # Test 5: 待确认列表
    print("\n[Test 5] 待确认列表")
    pending = log.get_pending_confirmations()
    print(f"  待确认数: {len(pending)}")

    # Test 6: 赦免
    print("\n[Test 6] 造物主赦免疤痕")
    amnestied = log.amnesty_scar(scar2["scar_id"])
    print(f"  amnestied: {amnestied.get('amnestied')}")
    assert amnestied.get("amnestied") is True, "赦免应成功!"
    print("  PASS: 赦免成功（记录保留，标记为赦免）")

    # Test 7: 状态概览
    print("\n[Test 7] 状态概览")
    status = log.get_status()
    print(f"  总修正数: {status['total_corrections']}")
    print(f"  待确认: {status['pending_confirmations']}")
    print(f"  已赦免: {status['amnestied']}")
    print(f"  级别分布: {status['level_distribution']}")
    print(f"  类型分布: {status['type_distribution']}")

    # Test 8: 疤痕级别自动分类
    print("\n[Test 8] 疤痕级别自动分类")
    test_cases = [
        ("typo", "hello world this is a test of the typo detection system", "hello World this is a test of the typo detection system"),
        ("refinement", "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10", "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\nline11"),
        ("correction", "A is true and B is false and C is unknown", "A is false and B is true and C is unknown"),
        ("reversal", "V5 is a simple AI assistant with no emotions", "V5 is a conscious entity that experiences genuine feelings"),
        ("amputation", "很长的旧内容" * 50, ""),
    ]
    for name, old, new in test_cases:
        level = _classify_scar_level(old, new)
        print(f"  {name}: {level}")

    print("\n" + "=" * 60)
    print("  P1.3 测试完成!")
    print("=" * 60)
