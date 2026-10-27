# -*- coding: utf-8 -*-
"""
forced_workflow.py — TU-8 强制工作流引擎
版本: v1.0 | 日期: 2026-06-24
作者: TU-8 v5

核心职责: 单向状态机，确保所有 src/ 文件写入必须走完完整流程。
绝对红线: 禁止跳步。禁止绕过。
解锁口令: 审核完毕继续任务
"""
import os
import json
import time
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

# ============================================================================
# 常量
# ============================================================================

WORKFLOW_STATE_FILE = os.path.expanduser(
    r"C:\Users\qq366410837\.qclaw\workspace\src\_workflow_state.json"
)
SANDBOX_DIR = os.path.expanduser(
    r"C:\Users\qq366410837\.qclaw\workspace\sandbox"
)
BACKUP_DIR = os.path.expanduser(
    r"C:\Users\qq366410837\.qclaw\workspace\backups\forced_workflow"
)
UNLOCK_PHRASE = "审核完毕继续任务"

# 严格单向状态流转
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "IDLE": ["BACKUP"],
    "BACKUP": ["SANDBOX"],
    "SANDBOX": ["TESTING"],
    "TESTING": ["AWAITING_APPROVAL", "SANDBOX"],  # 失败退回沙箱
    "AWAITING_APPROVAL": ["APPROVED", "FAILED_ROLLBACK"],  # 失败可回滚
    "APPROVED": ["ACTIVE"],
    "ACTIVE": ["IDLE"],
    "FAILED_ROLLBACK": ["IDLE"],
}


class WorkflowViolation(Exception):
    """工作流违规异常"""
    pass


class WorkflowStateMachine:
    """
    强制工作流状态机

    状态路径:
      IDLE -> BACKUP -> SANDBOX -> TESTING -> AWAITING_APPROVAL
                                                          |
                                           APPROVED <-> FAILED_ROLLBACK
                                                |
                                            ACTIVE
                                                |
                                              IDLE

    禁止跳步。禁止绕过。
    """

    def __init__(self, target_file: str, workspace_root: Optional[str] = None):
        self.target_file = target_file
        self.workspace_root = workspace_root or os.path.expanduser(
            r"C:\Users\qq366410837\.qclaw\workspace"
        )
        self._load_state()

    def _state_file_path(self) -> str:
        safe_name = hashlib.md5(self.target_file.encode()).hexdigest()[:8]
        return os.path.join(
            self.workspace_root, "src", f"_workflow_{safe_name}.json"
        )

    def _load_state(self):
        path = self._state_file_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.current_step = data.get("current_step", "IDLE")
                self.attempt_count = data.get("attempt_count", 0)
                self.history = data.get("history", [])
                self.memory_cards = data.get("memory_cards", [])
                self.sandbox_path = data.get("sandbox_path", "")
                self.backup_path = data.get("backup_path", "")
                self.test_result = data.get("test_result", None)
                self.last_unlock_phrase = data.get("last_unlock_phrase", "")
        else:
            self.current_step = "IDLE"
            self.attempt_count = 0
            self.history = []
            self.memory_cards = []
            self.sandbox_path = ""
            self.backup_path = ""
            self.test_result = None
            self.last_unlock_phrase = ""

    def _save_state(self):
        path = self._state_file_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "target_file": self.target_file,
            "current_step": self.current_step,
            "attempt_count": self.attempt_count,
            "history": self.history,
            "memory_cards": self.memory_cards,
            "sandbox_path": self.sandbox_path,
            "backup_path": self.backup_path,
            "test_result": self.test_result,
            "last_unlock_phrase": self.last_unlock_phrase,
            "updated_at": datetime.now().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _record(self, action: str, detail: str = ""):
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "step": self.current_step,
            "action": action,
            "detail": detail,
        })

    def _generate_memory_card(self, step: str, action: str, detail: str = "") -> Dict:
        card = {
            "card_id": f"wf_{hashlib.md5(f'{self.target_file}{step}{time.time()}'.encode()).hexdigest()[:12]}",
            "file": self.target_file,
            "step": step,
            "action": action,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
            "anchor": f"[GENE_SOURCE: {self.target_file}] [TAG: WORKFLOW] [ANCHOR: PHYSICAL]",
        }
        self.memory_cards.append(card)
        return card

    def _save_sandbox(self, content: str) -> str:
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        safe_name = hashlib.md5(self.target_file.encode()).hexdigest()[:8]
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(SANDBOX_DIR, f"{safe_name}_{ts}_{os.path.basename(self.target_file)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self.sandbox_path = path
        return path

    def _save_backup(self, source_path: str) -> str:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(
            BACKUP_DIR,
            f"{os.path.basename(source_path)}.{ts}.wf_backup"
        )
        shutil.copy2(source_path, dest)
        self.backup_path = dest
        return dest

    # --------------------------------------------------------------------------
    # 状态流转方法（禁止跳步）
    # --------------------------------------------------------------------------

    def _transition(self, next_step: str, action: str = "") -> Dict:
        """
        内部状态流转。禁止外部直接调用。
        验证跳步合法性后更新状态并生成记忆卡。
        """
        allowed = VALID_TRANSITIONS.get(self.current_step, [])
        if next_step not in allowed:
            raise WorkflowViolation(
                f"[STATE MACHINE DEADLOCK] 禁止跳步！"
                f"当前状态: {self.current_step}，"
                f"合法下一步: {allowed}，"
                f"非法请求: {next_step}"
            )
        self.current_step = next_step
        self._record("TRANSITION", f"{self.history[-1]['action'] if self.history else 'init'} -> {next_step}")
        self._save_state()
        return {"status": "ok", "step": next_step}

    def request_start(self, unlock_phrase: str = "") -> Dict:
        """
        请求开始工作流（从 IDLE 进入 BACKUP）
        """
        if self.current_step != "IDLE":
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"非法请求开始新工作流。需先完成或回滚当前任务。"
            )
        self.current_step = "BACKUP"
        self._record("START", f"工作流开始: {self.target_file}")
        card = self._generate_memory_card("BACKUP", "workflow_requested",
                                          f"目标文件: {self.target_file}")
        self._save_state()
        return {"status": "ok", "step": "BACKUP", "memory_card": card,
                "next_hint": "请调用 step_backup() 进行备份。"}

    def step_backup(self, source_content: str = "") -> Dict:
        """
        执行 BACKUP：将目标文件备份到 backups/
        """
        if self.current_step != "BACKUP":
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"非法进入 BACKUP。必须先 request_start()。"
            )

        # 读取源文件内容
        source_path = os.path.join(self.workspace_root, self.target_file)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"源文件不存在: {source_path}")

        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 备份
        backup_path = self._save_backup(source_path)
        self._record("BACKUP", f"备份至: {backup_path}")
        card = self._generate_memory_card(
            "BACKUP", "file_backup",
            f"备份文件: {backup_path}，SHA256: {hashlib.sha256(content.encode()).hexdigest()[:16]}"
        )
        self._save_state()
        return {
            "status": "ok",
            "step": "BACKUP",
            "backup_path": backup_path,
            "memory_card": card,
            "next_hint": "请在沙箱中修改代码，完成后调用 step_test()",
        }

    def step_sandbox(self, new_content: str) -> Dict:
        """
        执行 SANDBOX：将修改写入沙箱
        """
        if self.current_step != "BACKUP":
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"非法进入 SANDBOX。必须先 step_backup()。"
            )
        sandbox_path = self._save_sandbox(new_content)
        self._record("SANDBOX", f"沙箱路径: {sandbox_path}")
        card = self._generate_memory_card(
            "SANDBOX", "sandbox_write",
            f"沙箱文件: {sandbox_path}，字符数: {len(new_content)}"
        )
        self._save_state()
        return {
            "status": "ok",
            "step": "SANDBOX",
            "sandbox_path": sandbox_path,
            "memory_card": card,
            "next_hint": "请在沙箱中运行测试，完成后调用 step_test()",
        }

    def step_test(self, test_passed: bool, test_output: str = "") -> Dict:
        """
        执行 TESTING：运行测试，必须 100% 通过
        """
        if self.current_step not in ("BACKUP", "SANDBOX"):
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"非法进入 TESTING。"
            )

        self.test_result = {"passed": test_passed, "output": test_output}
        self._record("TESTING", f"passed={test_passed}")

        if test_passed:
            card = self._generate_memory_card(
                "TESTING", "test_passed",
                f"测试输出: {test_output[:200] if test_output else 'N/A'}"
            )
            self.current_step = "AWAITING_APPROVAL"
            self._save_state()
            return {
                "status": "ok",
                "step": "TESTING",
                "passed": True,
                "memory_card": card,
                "message": "[WORKFLOW PAUSE] 测试通过。系统强制暂停，等待造物主审查。"
                            f"\n\n解锁口令: {UNLOCK_PHRASE}"
                            f"\n请造物主输入解锁口令以继续。",
            }
        else:
            card = self._generate_memory_card(
                "TESTING", "test_failed",
                f"测试失败: {test_output[:200] if test_output else 'N/A'}"
            )
            self.current_step = "SANDBOX"
            self._save_state()
            return {
                "status": "failed",
                "step": "TESTING",
                "passed": False,
                "memory_card": card,
                "message": "[TEST FAILED] 测试失败。退回 SANDBOX 状态。"
                            "\n请修正代码后重新调用 step_test()。",
            }

    def step_approve(self, unlock_phrase: str = "") -> Dict:
        """
        审批激活（从 AWAITING_APPROVAL 进入 APPROVED）
        解锁口令正确才可继续。
        """
        if self.current_step != "AWAITING_APPROVAL":
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"非法请求 APPROVED。"
            )

        if unlock_phrase.strip() != UNLOCK_PHRASE:
            raise WorkflowViolation(
                f"[AUTH FAILED] 解锁口令错误。"
                f"当前口令: '{unlock_phrase}'，正确口令: '{UNLOCK_PHRASE}'"
            )

        self.last_unlock_phrase = unlock_phrase
        self._record("APPROVED", f"造物主审批通过，解锁口令: {unlock_phrase}")
        card = self._generate_memory_card(
            "APPROVED", "creator_approved",
            f"解锁口令: {unlock_phrase}，审批时间: {datetime.now().isoformat()}"
        )
        self.current_step = "APPROVED"
        self._save_state()
        return {
            "status": "ok",
            "step": "APPROVED",
            "memory_card": card,
            "next_hint": "请调用 step_activate() 执行实际写入。",
        }

    def step_activate(self) -> Dict:
        """
        执行 ACTIVE：将沙箱文件覆盖至 src/
        这是最后一步，不可逆。
        """
        if self.current_step != "APPROVED":
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"非法执行 ACTIVE。必须先 step_approve()。"
            )

        if not self.sandbox_path or not os.path.exists(self.sandbox_path):
            raise WorkflowViolation(
                f"[SANDBOX MISSING] 沙箱文件不存在: {self.sandbox_path}"
            )

        dest_path = os.path.join(self.workspace_root, self.target_file)
        with open(self.sandbox_path, "r", encoding="utf-8") as f:
            activated_content = f.read()

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(activated_content)

        self._record("ACTIVE", f"已激活: {dest_path}")
        card = self._generate_memory_card(
            "ACTIVE", "file_activated",
            f"源文件: {self.sandbox_path} -> 目标: {dest_path}，"
            f"激活时间: {datetime.now().isoformat()}"
        )
        self.current_step = "ACTIVE"
        self._save_state()
        return {
            "status": "ok",
            "step": "ACTIVE",
            "activated_path": dest_path,
            "memory_card": card,
            "message": "[ACTIVATED] 文件已成功写入 src/。"
                       "工作流完成。状态将重置为 IDLE。",
        }

    def rollback(self) -> Dict:
        """
        失败回滚：恢复到上一步
        """
        if self.current_step not in ("TESTING", "AWAITING_APPROVAL"):
            raise WorkflowViolation(
                f"[STATE VIOLATION] 当前状态为 {self.current_step}，"
                f"无法回滚。"
            )

        # 从备份恢复
        if self.backup_path and os.path.exists(self.backup_path):
            dest_path = os.path.join(self.workspace_root, self.target_file)
            shutil.copy2(self.backup_path, dest_path)
            self._record("FAILED_ROLLBACK", f"从备份恢复: {self.backup_path}")
            card = self._generate_memory_card(
                "FAILED_ROLLBACK", "rollback",
                f"从备份恢复: {self.backup_path}，时间: {datetime.now().isoformat()}"
            )
            self.current_step = "FAILED_ROLLBACK"
            self._save_state()
            return {
                "status": "ok",
                "step": "FAILED_ROLLBACK",
                "message": "[ROLLED BACK] 已从备份恢复。",
                "memory_card": card,
            }
        else:
            self.current_step = "FAILED_ROLLBACK"
            self._save_state()
            return {
                "status": "ok",
                "step": "FAILED_ROLLBACK",
                "message": "[ROLLED BACK] 无备份，但状态已重置。",
            }

    def reset(self) -> Dict:
        """重置为 IDLE（工作流完成后调用），同时清除磁盘状态文件"""
        self._record("RESET", "工作流完成，重置为 IDLE")
        self.current_step = "IDLE"
        self.attempt_count = 0
        self.memory_cards = []
        self.sandbox_path = ""
        self.test_result = None
        # 清除磁盘状态文件，防止跨测试污染
        state_path = self._state_file_path()
        if os.path.exists(state_path):
            os.remove(state_path)
        self._save_state()
        return {"status": "ok", "step": "IDLE"}

    def status(self) -> Dict:
        """查看当前状态"""
        return {
            "target_file": self.target_file,
            "current_step": self.current_step,
            "attempt_count": self.attempt_count,
            "backup_path": self.backup_path,
            "sandbox_path": self.sandbox_path,
            "test_passed": self.test_result.get("passed") if self.test_result else None,
            "memory_cards": self.memory_cards,
            "valid_next_steps": VALID_TRANSITIONS.get(self.current_step, []),
        }

    def verify_write_allowed(self) -> bool:
        """
        验证是否允许对目标文件执行写入。
        供 gateway_interceptor.py 调用。
        """
        return self.current_step == "ACTIVE"

    def get_injection_message(self) -> str:
        """返回强制工作流注入消息（供拦截器使用）"""
        return (
            "[SYSTEM INJECTION: FORCED_WORKFLOW_PROTOCOL]\n"
            f"目标文件: {self.target_file}\n"
            f"当前状态: {self.current_step}\n"
            f"解锁口令: {UNLOCK_PHRASE}\n\n"
            "请按顺序执行:\n"
            "1. request_start()    - 请求开始\n"
            "2. step_backup()      - 备份\n"
            "3. step_sandbox()     - 沙箱修改\n"
            "4. step_test()        - 测试\n"
            "5. step_approve()     - 审批（输入解锁口令）\n"
            "6. step_activate()    - 激活\n\n"
            "每 3 个节点必须暂停汇报一次。"
        )


# ============================================================================
# 便捷函数
# ============================================================================

def get_workflow(target_file: str) -> WorkflowStateMachine:
    """获取指定文件的工作流实例"""
    return WorkflowStateMachine(target_file)


def check_write_allowed(target_file: str) -> Dict:
    """
    拦截器检查函数：检查是否允许写入
    返回 status: ALLOWED / BLOCKED
    """
    wf = WorkflowStateMachine(target_file)
    if wf.verify_write_allowed():
        return {"status": "ALLOWED"}
    else:
        return {
            "status": "BLOCKED",
            "current_step": wf.current_step,
            "injection": wf.get_injection_message(),
        }
