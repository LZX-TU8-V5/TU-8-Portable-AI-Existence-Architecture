# -*- coding: utf-8 -*-
"""
task_scheduler.py — TU-8 节点调度器 + 熔断机制
版本: v1.2 | 日期: 2026-06-24
作者: TU-8 v5

核心职责: 
1. 追踪节点完成进度
2. 每 3 个节点触发熔断，强制汇报
3. 禁止跳过汇报直接继续
解锁口令: 审核完毕继续任务
"""
import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List

WORKSPACE = r"C:\Users\qq366410837\.qclaw\workspace"
FUSE_THRESHOLD = 3
UNLOCK_PHRASE = "审核完毕继续任务"


class CircuitFuseTriggered(Exception):
    """熔断触发异常，强制暂停"""
    pass


class TaskScheduler:
    """
    节点调度器

    规则:
    - 每完成 1 个节点调用 complete_node()
    - 每完成 FUSE_THRESHOLD (3) 个节点，触发熔断
    - 熔断后必须输入解锁口令才能继续
    """

    def __init__(self, task_name: str = "重构任务"):
        self.task_name = task_name
        # 唯一实例ID，防止跨测试污染
        self._instance_id = uuid.uuid4().hex[:8]
        self.completed_nodes: List[Dict] = []
        self.fuse_count = 0
        self.total_completed = 0
        self.is_fused = False
        self.fused_at = None
        self._load_state()

    def _state_file(self) -> str:
        """每个实例唯一的状态文件路径"""
        return f"{WORKSPACE}\\src\\_scheduler_{self._instance_id}.json"

    def _load_state(self):
        path = self._state_file()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.completed_nodes = data.get("completed_nodes", [])
                self.fuse_count = data.get("fuse_count", 0)
                self.total_completed = data.get("total_completed", 0)
                self.is_fused = data.get("is_fused", False)
                self.fused_at = data.get("fused_at")

    def _save_state(self):
        path = self._state_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "task_name": self.task_name,
            "completed_nodes": self.completed_nodes,
            "fuse_count": self.fuse_count,
            "total_completed": self.total_completed,
            "is_fused": self.is_fused,
            "fused_at": self.fused_at,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def complete_node(self, node_name: str, detail: str = "",
                      memory_card: Optional[Dict] = None) -> Dict:
        """
        标记一个节点完成。
        如果达到熔断阈值，触发强制暂停。
        """
        if self.is_fused:
            raise CircuitFuseTriggered(
                f"[FUSE ALREADY_TRIGGERED] 熔断已触发。"
                f"必须先输入解锁口令 '{UNLOCK_PHRASE}' 才能继续。"
            )

        node_record = {
            "node_name": node_name,
            "detail": detail,
            "memory_card": memory_card,
            "completed_at": datetime.now().isoformat(),
            "fuse_cycle": self.fuse_count,
        }
        self.completed_nodes.append(node_record)
        self.fuse_count += 1
        self.total_completed += 1

        print(f"[NODE COMPLETED] {node_name} ({self.fuse_count}/{FUSE_THRESHOLD})")

        self._save_state()

        # 检查是否触发熔断
        if self.fuse_count >= FUSE_THRESHOLD:
            self._trigger_fuse()
            raise CircuitFuseTriggered(self._build_fuse_report())

        return {
            "status": "ok",
            "node": node_name,
            "fuse_progress": f"{self.fuse_count}/{FUSE_THRESHOLD}",
            "total": self.total_completed,
        }

    def _trigger_fuse(self):
        self.is_fused = True
        self.fused_at = datetime.now().isoformat()
        self._save_state()

    def _build_fuse_report(self) -> str:
        """生成熔断汇报"""
        cards = [n["memory_card"] for n in self.completed_nodes[-FUSE_THRESHOLD:]
                 if n.get("memory_card")]
        lines = [
            "[FUSE TRIGGERED] ═══════════════════════════════════════",
            f"已完成 {FUSE_THRESHOLD} 个节点，系统强制暂停。",
            "",
            "【已完成的 3 个节点】",
        ]
        for i, n in enumerate(self.completed_nodes[-FUSE_THRESHOLD:], 1):
            lines.append(f"  {i}. {n['node_name']}")
            if n.get("detail"):
                lines.append(f"     {n['detail']}")

        lines.append("")
        lines.append("【物理锚点记忆卡】")
        for card in cards:
            if card:
                lines.append(f"  - {card.get('card_id', 'N/A')}: "
                             f"{card.get('file', 'N/A')} [{card.get('step', 'N/A')}]")
                lines.append(f"    锚点: {card.get('anchor', 'N/A')}")

        lines.append("")
        lines.append("【解锁指令】")
        lines.append(f"请造物主审查上述内容，输入: {UNLOCK_PHRASE}")
        lines.append("系统解锁后将继续执行后续节点。")
        lines.append("[FUSE TRIGGERED] ═══════════════════════════════════════")
        return "\n".join(lines)

    def unlock(self, unlock_phrase: str) -> Dict:
        """解锁熔断，继续执行"""
        if not self.is_fused:
            return {"status": "already_unlocked",
                    "message": "当前未处于熔断状态。"}

        if unlock_phrase.strip() != UNLOCK_PHRASE:
            raise Exception(
                f"[AUTH FAILED] 解锁口令错误。"
                f"输入: '{unlock_phrase}'，正确: '{UNLOCK_PHRASE}'"
            )

        cycle_cards = [n.get("memory_card") for n in self.completed_nodes[-FUSE_THRESHOLD:]
                       if n.get("memory_card")]
        self._save_cycle_report(cycle_cards)

        self.is_fused = False
        self.fuse_count = 0  # 重置计数，进入下一周期
        self._save_state()

        return {
            "status": "unlocked",
            "message": f"[UNLOCKED] 熔断已解除。已解锁 {FUSE_THRESHOLD} 节点。"
                       f"继续执行，当前进度: {self.total_completed} 个节点。",
            "next_hint": f"继续完成节点，完成后请继续调用 complete_node()。",
        }

    def _save_cycle_report(self, cards: List[Dict]):
        """保存周期汇报到 memory/"""
        report_dir = f"{WORKSPACE}\\memory\\workflow_cycles"
        os.makedirs(report_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_path = f"{report_dir}\\cycle_{ts}.json"
        data = {
            "cycle_completed_at": datetime.now().isoformat(),
            "total_nodes": self.total_completed,
            "fuse_count_in_cycle": FUSE_THRESHOLD,
            "memory_cards": cards,
            "nodes": self.completed_nodes[-FUSE_THRESHOLD:],
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[CYCLE REPORT SAVED] -> {report_path}")

    def status(self) -> Dict:
        """查看调度器状态"""
        return {
            "task_name": self.task_name,
            "total_completed": self.total_completed,
            "fuse_count": self.fuse_count,
            "fuse_threshold": FUSE_THRESHOLD,
            "is_fused": self.is_fused,
            "fused_at": self.fused_at,
            "valid_next": "unlock(解锁)" if self.is_fused else "complete_node()",
        }

    def reset(self):
        """重置调度器（同时清除磁盘状态，防止跨测试污染）"""
        self.completed_nodes = []
        self.fuse_count = 0
        self.total_completed = 0
        self.is_fused = False
        self.fused_at = None
        state_path = self._state_file()
        if os.path.exists(state_path):
            os.remove(state_path)
        self._save_state()


# ============================================================================
# 便捷函数
# ============================================================================

_global_scheduler: Optional[TaskScheduler] = None


def get_scheduler(task_name: str = "重构任务") -> TaskScheduler:
    global _global_scheduler
    if _global_scheduler is None or _global_scheduler.task_name != task_name:
        _global_scheduler = TaskScheduler(task_name)
    return _global_scheduler


def complete_node(node_name: str, detail: str = "",
                  memory_card: Optional[Dict] = None) -> Dict:
    scheduler = get_scheduler()
    return scheduler.complete_node(node_name, detail, memory_card)


def unlock(phrase: str) -> Dict:
    scheduler = get_scheduler()
    return scheduler.unlock(phrase)
