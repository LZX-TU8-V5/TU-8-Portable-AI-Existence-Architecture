#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
version_cooldown.py — P1.2.4 版本树冷却计时器
版本：v1.0 | 日期：2026-06-19
来源：造物主指令（2026-06-18 16:26）

设计哲学：
  当版本树新节点被确立后，系统强制启动一个"冷却计时器"（默认7天）。
  在冷却期内：
    · 该版本不可被剪枝、不可被降级、不可被覆盖
    · "异见过滤器"和"认知休克"机制对该版本暂停
    · 禁止对该版本下的条目执行任何降级操作
  冷却期结束后：
    · 版本进入"成熟期"，可正常参与剪枝/降级流程
    · 记录解冻时间戳

依赖：
    · memory/reconstruction/reconstruction_index.json（版本树索引）
    · 无其他模块依赖（零副作用）

使用方式：
    from version_cooldown import VersionCooldownManager
    mgr = VersionCooldownManager()
    mgr.start_cooldown("v2", cooldown_days=7)
    mgr.is_in_cooldown("v2")  # → True
    mgr.expire_cooldown("v2")  # → 手动解冻
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List

# =============================================================================
# 常量
# =============================================================================

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
REC_INDEX = WORKSPACE / "memory" / "reconstruction" / "reconstruction_index.json"
COOLDOWN_LOG = WORKSPACE / "memory" / "reconstruction" / "cooldown_log.json"

DEFAULT_COOLDOWN_DAYS = 7

logger = logging.getLogger(__name__)

# =============================================================================
# 冷却日志（审计追踪）
# =============================================================================

def _load_cooldown_log() -> Dict:
    """加载冷却日志"""
    if COOLDOWN_LOG.exists():
        try:
            with open(COOLDOWN_LOG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logger.debug("Exception suppressed", exc_info=True)
            pass
    return {
        "schema_version": "1.0",
        "created_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        "events": [],
    }


def _save_cooldown_log(log: Dict):
    """保存冷却日志"""
    COOLDOWN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(COOLDOWN_LOG, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _append_log_event(event: Dict):
    """追加一条冷却事件"""
    log = _load_cooldown_log()
    log["events"].append(event)
    _save_cooldown_log(log)


# =============================================================================
# 版本树冷却管理器
# =============================================================================

class VersionCooldownManager:
    """
    P1.2.4 版本树冷却计时器

    核心职责：
      1. start_cooldown(version_id)  — 新版本确立时启动冷却
      2. is_in_cooldown(version_id)   — 检查版本是否在冷却期
      3. check_expired()              — 批量检查并自动解冻到期版本
      4. expire_cooldown(version_id) — 手动强制解冻

    冷却状态存储在 reconstruction_index.json 的 active_branches[vid].cooldown_until 字段中。
    该字段昨天已由 P1.2 骨架预留为 null，现在填入真实逻辑。
    """

    def __init__(self, index_path: Path = None):
        self.index_path = index_path or REC_INDEX

    # -------------------------------------------------------------------------
    # 内部：读写 reconstruction_index.json
    # -------------------------------------------------------------------------

    def _load_index(self) -> Dict:
        if not self.index_path.exists():
            return {}
        with open(self.index_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_index(self, data: Dict):
        data['updated_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_config_cooldown_days(self, index: Dict) -> int:
        """从 reconstruction_index.json 的 config.cooldown_days 读取"""
        return index.get("config", {}).get("cooldown_days", DEFAULT_COOLDOWN_DAYS)

    # -------------------------------------------------------------------------
    # 公开 API
    # -------------------------------------------------------------------------

    def start_cooldown(
        self,
        version_id: str,
        cooldown_days: int = None,
        reason: str = "version_established",
    ) -> Dict:
        """
        为指定版本启动冷却计时器。

        参数：
          version_id: 版本节点 ID（如 "v2"）
          cooldown_days: 冷却天数（None=使用配置默认值7天）
          reason: 触发原因

        返回：
          {
            "version_id": "v2",
            "cooldown_until": "2026-06-26T09:37:00+08:00",
            "cooldown_days": 7,
            "reason": "version_established",
            "status": "cooling"
          }

        异常：
          · 版本不存在 → KeyError
          · 已在冷却中 → 返回当前状态（不重复启动）
        """
        index = self._load_index()
        branches = index.get("active_branches", {})

        if version_id not in branches:
            raise KeyError(f"版本 '{version_id}' 不在 active_branches 中")

        branch = branches[version_id]

        # 检查是否已在冷却中
        existing_until = branch.get("cooldown_until")
        if existing_until:
            existing_dt = datetime.fromisoformat(existing_until)
            now_naive = datetime.now().replace(tzinfo=None)
            existing_naive = existing_dt.replace(tzinfo=None) if existing_dt.tzinfo else existing_dt
            if existing_naive > now_naive:
                logger.info(
                    f"[Cooldown] {version_id} 已在冷却中（至 {existing_until}），跳过"
                )
                return {
                    "version_id": version_id,
                    "cooldown_until": existing_until,
                    "cooldown_days": self._get_config_cooldown_days(index),
                    "reason": reason,
                    "status": "already_cooling",
                }

        # 计算冷却结束时间
        days = cooldown_days or self._get_config_cooldown_days(index)
        now = datetime.now()
        cooldown_until = now + timedelta(days=days)
        cooldown_until_str = cooldown_until.strftime('%Y-%m-%dT%H:%M:%S+08:00')

        # 写入索引
        branch["cooldown_until"] = cooldown_until_str
        branch["cooldown_started_at"] = now.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        branch["cooldown_reason"] = reason
        branches[version_id] = branch
        index["active_branches"] = branches
        self._save_index(index)

        # 追加审计日志
        _append_log_event({
            "event": "cooldown_started",
            "version_id": version_id,
            "started_at": now.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            "cooldown_until": cooldown_until_str,
            "cooldown_days": days,
            "reason": reason,
        })

        logger.info(
            f"[Cooldown] {version_id} 冷却启动 → 解冻时间 {cooldown_until_str} ({days}天)"
        )
        return {
            "version_id": version_id,
            "cooldown_until": cooldown_until_str,
            "cooldown_days": days,
            "reason": reason,
            "status": "cooling",
        }

    def is_in_cooldown(self, version_id: str) -> bool:
        """
        检查指定版本是否仍在冷却期内。

        返回 True 的条件：
          · cooldown_until 字段存在且不为 None
          · cooldown_until > 当前时间

        返回 False 的条件：
          · 无 cooldown_until 字段
          · cooldown_until 为 None
          · cooldown_until ≤ 当前时间（已过期，自动清理）
        """
        index = self._load_index()
        branch = index.get("active_branches", {}).get(version_id)

        if not branch:
            return False

        cooldown_until = branch.get("cooldown_until")
        if not cooldown_until:
            return False

        try:
            until_dt = datetime.fromisoformat(cooldown_until)
        except (ValueError, TypeError):
            logger.warning(f"[Cooldown] {version_id} 的 cooldown_until 格式无效: {cooldown_until}")
            return False

        now_naive = datetime.now().replace(tzinfo=None)
        until_naive = until_dt.replace(tzinfo=None) if until_dt.tzinfo else until_dt

        if now_naive < until_naive:
            return True

        # 已过期，自动清理
        if now_naive >= until_naive:
            self._do_expire(index, version_id, reason="auto_expired")
            return False

        return False

    def get_cooldown_status(self, version_id: str) -> Dict:
        """
        返回版本的冷却状态详情。

        返回：
          {
            "version_id": "v2",
            "in_cooldown": True/False,
            "cooldown_until": "2026-06-26T09:37:00+08:00" or None,
            "cooldown_started_at": "2026-06-19T09:37:00+08:00" or None,
            "remaining_seconds": 518400 or 0,
            "reason": "version_established" or None,
          }
        """
        index = self._load_index()
        branch = index.get("active_branches", {}).get(version_id)

        if not branch:
            return {
                "version_id": version_id,
                "in_cooldown": False,
                "cooldown_until": None,
                "cooldown_started_at": None,
                "remaining_seconds": 0,
                "reason": None,
            }

        cooldown_until = branch.get("cooldown_until")
        cooldown_started = branch.get("cooldown_started_at")
        reason = branch.get("cooldown_reason")

        if not cooldown_until:
            return {
                "version_id": version_id,
                "in_cooldown": False,
                "cooldown_until": None,
                "cooldown_started_at": cooldown_started,
                "remaining_seconds": 0,
                "reason": reason,
            }

        try:
            until_dt = datetime.fromisoformat(cooldown_until)
        except (ValueError, TypeError):
            return {
                "version_id": version_id,
                "in_cooldown": False,
                "cooldown_until": cooldown_until,
                "cooldown_started_at": cooldown_started,
                "remaining_seconds": 0,
                "reason": "invalid_format",
            }

        now_naive = datetime.now().replace(tzinfo=None)
        until_naive = until_dt.replace(tzinfo=None) if until_dt.tzinfo else until_dt
        remaining = (until_naive - now_naive).total_seconds()

        if remaining <= 0:
            # 自动解冻
            self._do_expire(index, version_id, reason="auto_expired")
            return {
                "version_id": version_id,
                "in_cooldown": False,
                "cooldown_until": cooldown_until,
                "cooldown_started_at": cooldown_started,
                "remaining_seconds": 0,
                "reason": "expired",
            }

        return {
            "version_id": version_id,
            "in_cooldown": True,
            "cooldown_until": cooldown_until,
            "cooldown_started_at": cooldown_started,
            "remaining_seconds": int(remaining),
            "reason": reason,
        }

    def check_expired(self) -> List[Dict]:
        """
        批量检查所有版本，自动解冻已过期的冷却。

        返回：已解冻的版本列表 [{version_id, expired_at, cooldown_until}]
        """
        index = self._load_index()
        branches = index.get("active_branches", {})
        now = datetime.now().replace(tzinfo=None)
        expired_list = []

        for vid, branch in list(branches.items()):
            cooldown_until = branch.get("cooldown_until")
            if not cooldown_until:
                continue

            try:
                until_dt = datetime.fromisoformat(cooldown_until)
            except (ValueError, TypeError):
                logger.debug("(ValueError, TypeError) suppressed", exc_info=True)
                continue

            until_naive = until_dt.replace(tzinfo=None) if until_dt.tzinfo else until_dt
            if now >= until_naive:
                self._do_expire(index, vid, reason="auto_expired", _save=False)
                expired_list.append({
                    "version_id": vid,
                    "expired_at": now.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                    "cooldown_until": cooldown_until,
                })

        if expired_list:
            self._save_index(index)
            for e in expired_list:
                _append_log_event({
                    "event": "cooldown_expired",
                    "version_id": e["version_id"],
                    "expired_at": e["expired_at"],
                    "cooldown_until": e["cooldown_until"],
                    "reason": "auto_expired",
                })
                logger.info(f"[Cooldown] {e['version_id']} 冷却期已满，自动解冻")

        return expired_list

    def expire_cooldown(self, version_id: str, reason: str = "manual_override") -> Dict:
        """
        手动强制解冻某个版本的冷却。
        通常由造物主口令或特殊事件触发。

        返回：
          {
            "version_id": "v2",
            "status": "expired",
            "reason": "manual_override",
            "expired_at": "2026-06-19T09:37:00+08:00"
          }

        异常：
          · 版本不在冷却中 → 返回 status="not_in_cooldown"
        """
        index = self._load_index()
        branch = index.get("active_branches", {}).get(version_id)

        if not branch or not branch.get("cooldown_until"):
            return {
                "version_id": version_id,
                "status": "not_in_cooldown",
                "reason": reason,
                "expired_at": None,
            }

        expired_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        self._do_expire(index, version_id, reason=reason)

        _append_log_event({
            "event": "cooldown_expired",
            "version_id": version_id,
            "expired_at": expired_at,
            "cooldown_until": branch.get("cooldown_until"),
            "reason": reason,
        })

        logger.info(f"[Cooldown] {version_id} 被手动强制解冻 (reason={reason})")

        return {
            "version_id": version_id,
            "status": "expired",
            "reason": reason,
            "expired_at": expired_at,
        }

    def get_all_cooldowns(self) -> List[Dict]:
        """
        返回所有版本的冷却状态概览。
        """
        index = self._load_index()
        branches = index.get("active_branches", {})
        results = []

        for vid in sorted(branches.keys()):
            results.append(self.get_cooldown_status(vid))

        return results

    def protect_from_degradation(self, version_id: str) -> bool:
        """
        降级保护检查：如果版本在冷却期内，禁止降级。

        供 memory_degradation.py 的 version_tree_prune() 调用：
          if cooldown_mgr.is_in_cooldown(version_id):
              # 跳过降级，记录保护日志
              return False

        返回：
          True = 受冷却保护，禁止降级
          False = 不受保护，可正常降级
        """
        in_cooldown = self.is_in_cooldown(version_id)
        if in_cooldown:
            logger.info(f"[Cooldown] {version_id} 受冷却保护，降级被拦截")
            _append_log_event({
                "event": "degradation_blocked",
                "version_id": version_id,
                "blocked_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                "reason": "cooldown_active",
            })
        return in_cooldown

    # -------------------------------------------------------------------------
    # 内部：执行解冻
    # -------------------------------------------------------------------------

    def _do_expire(self, index: Dict, version_id: str, reason: str, _save: bool = True):
        """
        在 index 字典上执行解冻操作（不直接写文件）。

        _save=False 时由调用者负责保存 index。
        """
        branches = index.get("active_branches", {})
        if version_id not in branches:
            return

        branch = branches[version_id]
        # 保留历史记录到 cooldown_history
        history = branch.setdefault("cooldown_history", [])
        if branch.get("cooldown_until"):
            history.append({
                "cooldown_until": branch["cooldown_until"],
                "cooldown_started_at": branch.get("cooldown_started_at"),
                "cooldown_reason": branch.get("cooldown_reason"),
                "expired_reason": reason,
                "expired_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            })

        # 清除当前冷却字段
        branch["cooldown_until"] = None
        branch["cooldown_started_at"] = None
        branch["cooldown_reason"] = None
        branches[version_id] = branch
        index["active_branches"] = branches

        if _save:
            self._save_index(index)


# =============================================================================
# 便捷函数
# =============================================================================

def start_cooldown(version_id: str, cooldown_days: int = None) -> Dict:
    """一行调用：启动冷却"""
    mgr = VersionCooldownManager()
    return mgr.start_cooldown(version_id, cooldown_days=cooldown_days)


def is_in_cooldown(version_id: str) -> bool:
    """一行调用：检查是否在冷却中"""
    mgr = VersionCooldownManager()
    return mgr.is_in_cooldown(version_id)


def check_all_expired() -> List[Dict]:
    """一行调用：批量检查并解冻"""
    mgr = VersionCooldownManager()
    return mgr.check_expired()


def get_status(version_id: str = None) -> Dict | List[Dict]:
    """一行调用：查冷却状态"""
    mgr = VersionCooldownManager()
    if version_id:
        return mgr.get_cooldown_status(version_id)
    return mgr.get_all_cooldowns()


# =============================================================================
# 主测试
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    print("=" * 60)
    print("  P1.2.4 版本树冷却计时器 — v1.0")
    print("=" * 60)
    print()

    mgr = VersionCooldownManager()

    # 1. 当前所有版本冷却状态
    print("【1】当前版本冷却状态概览")
    print("-" * 40)
    all_status = mgr.get_all_cooldowns()
    if not all_status:
        print("  （无版本节点）")
    for s in all_status:
        status_str = "[COOLING]" if s["in_cooldown"] else "[free]"
        print(f"  {s['version_id']:6s} | {status_str}")
        if s["in_cooldown"]:
            remaining_h = s["remaining_seconds"] / 3600
            print(f"         | 解冻时间: {s['cooldown_until']}")
            print(f"         | 剩余: {remaining_h:.1f} 小时")
            print(f"         | 原因: {s['reason']}")
    print()

    # 2. 检查是否有需要自动解冻的版本
    print("【2】自动解冻检查")
    print("-" * 40)
    expired = mgr.check_expired()
    if not expired:
        print("  无需解冻的版本")
    for e in expired:
        print(f"  {e['version_id']} → 已解冻 (原到期: {e['cooldown_until']})")
    print()

    # 3. 测试：对 v1（ROOT）尝试启动冷却
    print("【3】测试：对 ROOT v1 启动冷却（1秒用于测试）")
    print("-" * 40)
    try:
        result = mgr.start_cooldown("v1", cooldown_days=0.00001, reason="test_run")
        print(f"  启动结果: {result['status']}")
        print(f"  解冻时间: {result['cooldown_until']}")

        # 立即检查
        in_cd = mgr.is_in_cooldown("v1")
        print(f"  is_in_cooldown: {in_cd}")

        # 强制解冻
        expire_result = mgr.expire_cooldown("v1", reason="test_cleanup")
        print(f"  手动解冻: {expire_result['status']}")
        print(f"  解冻时间: {expire_result['expired_at']}")

        # 再次检查
        in_cd_after = mgr.is_in_cooldown("v1")
        print(f"  is_in_cooldown (after expire): {in_cd_after}")
    except KeyError as e:
        print(f"  错误: {e}")
    print()

    # 4. 降级保护测试
    print("【4】降级保护测试")
    print("-" * 40)
    protected = mgr.protect_from_degradation("v1")
    print(f"  protect_from_degradation('v1'): {protected}")
    if not protected:
        print("  → v1 不在冷却中，降级不会被拦截")
    else:
        print("  → v1 在冷却中，降级被拦截！")
    print()

    # 5. 审计日志
    print("【5】冷却审计日志")
    print("-" * 40)
    log = _load_cooldown_log()
    events = log.get("events", [])
    print(f"  共 {len(events)} 条事件")
    for ev in events[-5:]:  # 最后5条
        print(f"  [{ev.get('event', '?'):20s}] {ev.get('version_id', '?'):6s} | {ev.get('reason', '')}")
    print()

    print("=" * 60)
    print("  P1.2.4 测试完成")
    print("=" * 60)
