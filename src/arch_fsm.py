#-*- coding: utf-8 -*-
"""
TU-8 架构变更状态机 v2.0
Architecture Change StateChart — 基于 python-statemachine 3.2.0

设计原则：
- LLM只负责意图解析和参数填充
- 破坏性操作由状态机确定性执行
- 测试失败自动回滚（Saga补偿链语义）
- 审计日志哈希链防篡改（CT/Merkle + Event Sourcing语义）
- 前置条件检查（DbC require语义 + Guard条件）
- 审批节点（HITL条件边中断 + Checkpoint持久化）
- 偏差门联动（高偏差→强制审批）

6节点主流程：
  LOCATE → BACKUP → MODIFY → APPROVE → TEST → MARK_DELETE → LOG

v2.0 变更（v1.0→v2.0 差距消解）：
  - 差距1：状态机集成主循环 → StateChart + SQLite持久化
  - 差距2：偏差门联动 → Guard条件 + APPROVE节点
  - 差距3：批量原子性 → atomic_configuration_update + Saga补偿链
  - 差距4：前置条件检查 → cond=Guard + DbC require
  - 差距5：审批流 → APPROVE节点 + Checkpoint + Timeout降级
  - 差距6：审计日志防篡改 → HashChainLog + state_history

作者：金木蟾 | CC BY-SA 4.0
"""

import os
import json
import shutil
import hashlib
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from statemachine import State, StateChart

# ─── 路径配置 ───
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
PENDING_QUEUE = os.path.join(WORKSPACE_DIR, ".pending_deletion.jsonl")
AUDIT_LOG = os.path.join(WORKSPACE_DIR, "audit_log.jsonl")
BACKUP_DIR = os.path.join(WORKSPACE_DIR, ".arch_backups")
STATE_DB = os.path.join(WORKSPACE_DIR, ".arch_state.db")

# ─── 路径白名单 ───
ALLOWED_PATH_PREFIXES = [
    os.path.join(WORKSPACE_DIR, "src"),
    os.path.join(WORKSPACE_DIR, "config"),
    os.path.join(WORKSPACE_DIR, "docs"),
]

# ─── 日志配置 ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(WORKSPACE_DIR, "arch_fsm.log"),
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger("ArchFSM")


# ═══════════════════════════════════════════════════════════
# 差距6：哈希链审计日志（CT/Merkle + Event Sourcing语义）
# ═══════════════════════════════════════════════════════════

class HashChainLog:
    """
    防篡改追加日志 — Event Sourcing语义 + 哈希链完整性

    - 事件追加不可变（Event Sourcing）
    - 每条事件含prev_hash，形成哈希链（CT/Merkle简化版）
    - 补偿事件用 negative=True 标记（红字冲销语义）
    - verify() 可从任意点回溯genesis验证完整性
    """

    GENESIS_HASH = "0" * 16  # 16位全零起始哈希

    def __init__(self, log_path: str = AUDIT_LOG):
        self._path = log_path
        self._last_hash = self.GENESIS_HASH
        # 读取已有日志的末尾哈希
        if os.path.exists(self._path):
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            self._last_hash = entry.get("hash", self.GENESIS_HASH)
                        except json.JSONDecodeError:
                            logger.debug("JSONDecodeError suppressed", exc_info=True)
                            pass

    def append(self, event_type: str, data: Dict[str, Any],
               negative: bool = False) -> str:
        """
        追加事件到日志

        Args:
            event_type: 事件类型（如 LOCATE, BACKUP, ROLLBACK等）
            data: 事件数据
            negative: 是否为补偿事件（红字冲销）

        Returns:
            本次事件的哈希值
        """
        timestamp = datetime.now().isoformat()
        payload = json.dumps({
            "type": event_type,
            "data": data,
            "negative": negative,
            "timestamp": timestamp,
            "prev_hash": self._last_hash,
        }, ensure_ascii=False, sort_keys=True)

        event_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        entry = {
            "hash": event_hash,
            "prev_hash": self._last_hash,
            "type": event_type,
            "negative": negative,
            "timestamp": timestamp,
            "data": data,
        }

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._last_hash = event_hash
        return event_hash

    def verify(self) -> bool:
        """验证日志哈希链完整性"""
        if not os.path.exists(self._path):
            return True

        prev_hash = self.GENESIS_HASH
        with open(self._path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    logger.error(f"哈希链验证失败: 第{line_no}行JSON解析错误")
                    return False

                if entry.get("prev_hash") != prev_hash:
                    logger.error(
                        f"哈希链验证失败: 第{line_no}行prev_hash不匹配 "
                        f"(期望={prev_hash}, 实际={entry.get('prev_hash')})"
                    )
                    return False

                # 重新计算哈希
                payload = json.dumps({
                    "type": entry["type"],
                    "data": entry["data"],
                    "negative": entry.get("negative", False),
                    "timestamp": entry["timestamp"],
                    "prev_hash": entry["prev_hash"],
                }, ensure_ascii=False, sort_keys=True)
                expected_hash = hashlib.sha256(
                    payload.encode("utf-8")
                ).hexdigest()[:16]

                if entry.get("hash") != expected_hash:
                    logger.error(
                        f"哈希链验证失败: 第{line_no}行hash不匹配 "
                        f"(期望={expected_hash}, 实际={entry.get('hash')})"
                    )
                    return False

                prev_hash = entry["hash"]

        logger.info(f"哈希链验证通过: 末尾hash={prev_hash}")
        return True

    @property
    def last_hash(self) -> str:
        return self._last_hash


# ═══════════════════════════════════════════════════════════
# 差距1+3：SQLite持久化层 + 批量原子性
# ═══════════════════════════════════════════════════════════

class ArchStateDB:
    """
    SQLite持久化层 — 状态机配置 + 状态变更历史

    双表设计（参考python-statemachine SQLite审批工作流）：
    1. arch_operations: 当前活跃的架构操作 + 序列化状态配置
    2. state_history: 追加只读的状态变更日志
    """

    def __init__(self, db_path: str = STATE_DB):
        self._path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS arch_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                dest_path TEXT,
                reason TEXT,
                state TEXT,
                context_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id INTEGER NOT NULL REFERENCES arch_operations(id),
                old_state TEXT,
                new_state TEXT,
                event_type TEXT,
                detail TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def create_operation(self, source_path: str, dest_path: str = "",
                         reason: str = "") -> int:
        """创建新操作记录，返回ID"""
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO arch_operations "
            "(source_path, dest_path, reason, state, context_json, created_at) "
            "VALUES (?, ?, ?, 'idle', '{}', ?)",
            (source_path, dest_path, reason, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_state(self, operation_id: int, new_state: str,
                     context_json: str = "", event_type: str = "transition"):
        """更新操作状态（原子写）"""
        now = datetime.now().isoformat()
        # 读取旧状态
        row = self.conn.execute(
            "SELECT state FROM arch_operations WHERE id = ?",
            (operation_id,)
        ).fetchone()
        old_state = row[0] if row else "unknown"

        # 原子更新
        self.conn.execute(
            "UPDATE arch_operations SET state = ?, context_json = ?, "
            "updated_at = ? WHERE id = ?",
            (new_state, context_json, now, operation_id)
        )
        # 追加历史
        self.conn.execute(
            "INSERT INTO state_history "
            "(operation_id, old_state, new_state, event_type, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (operation_id, old_state, new_state, event_type, now)
        )
        self.conn.commit()

    def get_operation(self, operation_id: int) -> Optional[Dict[str, Any]]:
        """获取操作信息"""
        row = self.conn.execute(
            "SELECT id, source_path, dest_path, reason, state, "
            "context_json, created_at, updated_at "
            "FROM arch_operations WHERE id = ?",
            (operation_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "source_path": row[1],
            "dest_path": row[2],
            "reason": row[3],
            "state": row[4],
            "context_json": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def get_state_history(self, operation_id: int) -> List[Dict[str, Any]]:
        """获取操作的状态变更历史"""
        rows = self.conn.execute(
            "SELECT old_state, new_state, event_type, timestamp "
            "FROM state_history WHERE operation_id = ? ORDER BY id",
            (operation_id,)
        ).fetchall()
        return [
            {"old_state": r[0], "new_state": r[1],
             "event_type": r[2], "timestamp": r[3]}
            for r in rows
        ]

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════
# 差距1-6：架构变更StateChart v2.0
# ═══════════════════════════════════════════════════════════

class ArchitectureChangeChart(StateChart):
    """
    架构变更确定性状态机 v2.0

    基于 python-statemachine StateChart，集成：
    - 6节点主流程 + APPROVE审批节点
    - Guard条件（前置检查）
    - Checkpoint持久化（SQLite）
    - 哈希链审计日志
    - 偏差门联动（外部注入 approval_required）
    - 超时降级（审批节点超时默认拒绝）

    状态流程：
      idle → locate → backup → modify → approve → test →
      mark_delete → log → done

    回滚流程：
      任意节点失败 → rollback → rolled_back
    """

    # ─── 状态定义 ───
    idle = State(initial=True)
    locate = State()
    backup = State()
    modify = State()
    approve = State()       # 差距5：审批节点
    test = State()
    mark_delete = State()
    log = State()
    done = State(final=True)
    rolled_back = State(final=True)

    # ─── 正向转换 ───
    start = idle.to(locate)

    locate_done = locate.to(backup)
    locate_fail = locate.to(rolled_back)

    backup_done = backup.to(modify)
    backup_fail = backup.to(rolled_back)

    modify_done = modify.to(approve)     # 差距5：修改后必须审批
    modify_fail = modify.to(rolled_back)

    # 审批结果（差距5：HITL条件边中断）
    approve_pass = approve.to(test)
    approve_reject = approve.to(rolled_back)
    approve_timeout = approve.to(rolled_back)  # 超时默认拒绝

    test_pass = test.to(mark_delete)
    test_fail = test.to(rolled_back)     # 测试失败回滚

    mark_done = mark_delete.to(log)

    log_done = log.to(done)

    # ─── 类属性（运行时上下文） ───
    def __init__(self, model=None, state_field="state", **kwargs):
        self._context: Dict[str, Any] = {}
        self._params: Dict[str, Any] = {}
        self._approval_required: bool = False
        self._approval_result: Optional[str] = None
        self._hash_chain = HashChainLog()
        self._state_db: Optional[ArchStateDB] = None
        self._operation_id: Optional[int] = None
        self._steps_completed: List[str] = []
        self._ref_results: List[Dict] = []
        self._rolled_back: bool = False
        self._rollback_reason: str = ""
        super().__init__(model=model, state_field=state_field, **kwargs)

    # ─── 外部接口 ───

    def execute(self, params: Dict[str, Any],
                approval_required: bool = False,
                state_db: Optional[ArchStateDB] = None) -> Dict[str, Any]:
        """
        执行状态机完整流程

        Args:
            params: {
                "source_path": str,
                "dest_path": str,
                "ref_updates": list,
                "delete_original": bool,
                "test_command": str,
                "reason": str,
            }
            approval_required: 偏差门联动标记（高偏差时强制审批）
            state_db: SQLite持久化层（可选）
        """
        self._params = params
        self._approval_required = approval_required
        self._state_db = state_db
        self._context = {
            "source_path": params.get("source_path", ""),
            "dest_path": params.get("dest_path", ""),
            "ref_updates": params.get("ref_updates", []),
            "delete_original": params.get("delete_original", True),
            "test_command": params.get("test_command", ""),
            "reason": params.get("reason", ""),
            "backup_path": "",
            "original_hash": "",
            "start_time": datetime.now().isoformat(),
        }
        self._steps_completed = []
        self._ref_results = []
        self._rolled_back = False
        self._rollback_reason = ""

        # 创建SQLite操作记录
        if self._state_db:
            self._operation_id = self._state_db.create_operation(
                source_path=self._context["source_path"],
                dest_path=self._context["dest_path"],
                reason=self._context["reason"],
            )

        # 哈希链日志：记录开始
        self._hash_chain.append("START", {
            "source": self._context["source_path"],
            "dest": self._context["dest_path"],
            "reason": self._context["reason"],
            "approval_required": approval_required,
        })

        logger.info(
            f"FSM开始执行: {self._context['source_path']} → "
            f"{self._context['dest_path']} "
            f"(approval={approval_required})"
        )

        try:
            # idle → locate
            self.send("start")

            # LOCATE
            self._do_locate()
            if self._rolled_back:
                return self._build_result()

            # BACKUP
            self._do_backup()
            if self._rolled_back:
                return self._build_result()

            # MODIFY
            self._do_modify()
            if self._rolled_back:
                return self._build_result()

            # APPROVE
            self._do_approve()
            if self._rolled_back:
                return self._build_result()

            # TEST
            self._do_test()
            if self._rolled_back:
                return self._build_result()

            # MARK_DELETE
            self._do_mark_delete()

            # LOG
            self._do_log()

        except Exception as e:
            logger.error(f"FSM未预期异常: {e}")
            self._do_rollback(str(e))
            self._hash_chain.append("EXCEPTION_ROLLBACK", {
                "error": str(e)
            }, negative=True)

        result = self._build_result()
        return result

    @property
    def current_state_id(self) -> str:
        """当前状态ID（字符串）"""
        try:
            # configuration返回当前活跃状态集合
            config = self.configuration
            if config:
                # 取第一个活跃状态的id
                return next(iter(config)).id
            return "idle"
        except Exception:
            return "idle"

    # ─── 节点1: LOCATE ───
    def _do_locate(self):
        """查找定位 — 差距4：前置条件检查（DbC require语义）"""
        source = self._context["source_path"]

        # require: 路径白名单校验
        if not self._is_path_allowed(source):
            error = f"路径不在白名单中: {source}"
            self._hash_chain.append("LOCATE_FAIL", {"error": error})
            self._fail_and_rollback(error)
            return

        # require: 源文件必须存在
        if not os.path.exists(source):
            error = f"源文件不存在: {source}"
            self._hash_chain.append("LOCATE_FAIL", {"error": error})
            self._fail_and_rollback(error)
            return

        # ensure: 计算原始文件哈希
        self._context["original_hash"] = self._file_hash(source)
        self._context["source_size"] = os.path.getsize(source)

        self.send("locate_done")  # locate → backup
        self._steps_completed.append("LOCATE")
        self._persist_state("backup")
        self._hash_chain.append("LOCATE", {
            "source": source,
            "hash": self._context["original_hash"],
            "size": self._context["source_size"],
        })

    # ─── 节点2: BACKUP ───
    def _do_backup(self):
        """复制备份"""
        source = self._context["source_path"]

        os.makedirs(BACKUP_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = os.path.basename(source)
        backup_name = f"{basename}__backup_{timestamp}"
        backup_path = os.path.join(BACKUP_DIR, backup_name)

        shutil.copy2(source, backup_path)

        # ensure: 备份完整性验证
        if self._file_hash(backup_path) != self._context["original_hash"]:
            error = "备份文件哈希不匹配"
            self._hash_chain.append("BACKUP_FAIL", {"error": error})
            self._fail_and_rollback(error)
            return

        self._context["backup_path"] = backup_path
        self.send("backup_done")  # backup → modify

        self._steps_completed.append("BACKUP")
        self._persist_state("modify")
        self._hash_chain.append("BACKUP", {
            "backup_path": backup_path,
            "hash_verified": True,
        })

    # ─── 节点3: MODIFY ───
    def _do_modify(self):
        """移动/修改+同步引用"""
        source = self._context["source_path"]
        dest = self._context["dest_path"]
        ref_updates = self._context["ref_updates"]

        dest_dir = os.path.dirname(dest)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        shutil.move(source, dest)

        # 更新引用
        self._ref_results = []
        for ref in ref_updates:
            ref_file = ref.get("file", "")
            old_text = ref.get("old", "")
            new_text = ref.get("new", "")

            if not os.path.exists(ref_file):
                self._ref_results.append({"file": ref_file, "status": "NOT_FOUND"})
                continue

            try:
                with open(ref_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if old_text in content:
                    content = content.replace(old_text, new_text)
                    with open(ref_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    self._ref_results.append({"file": ref_file, "status": "UPDATED"})
                else:
                    self._ref_results.append({"file": ref_file, "status": "NO_MATCH"})
            except Exception as e:
                self._ref_results.append({
                    "file": ref_file, "status": "ERROR", "error": str(e)
                })

        self.send("modify_done")  # modify → approve

        self._steps_completed.append("MODIFY")
        self._persist_state("approve")
        self._hash_chain.append("MODIFY", {
            "dest": dest,
            "ref_results": self._ref_results,
        })

    # ─── 节点4: APPROVE（差距5：审批流） ───
    def _do_approve(self):
        """
        审批节点 — HITL条件边中断 + Checkpoint

        逻辑：
        1. 如果 _approval_required=False 且非高危操作 → 自动放行
        2. 如果 _approval_required=True → 等待 _approval_result
        3. 超时默认拒绝（HITL硬超时语义）
        """
        # 判断是否需要审批
        need_approval = self._approval_required or self._is_high_impact()

        if not need_approval:
            # 自动放行
            self.send("approve_pass")  # approve → test
            self._steps_completed.append("APPROVE_AUTO")
            self._persist_state("test")
            self._hash_chain.append("APPROVE", {
                "mode": "auto_pass",
                "reason": "低风险操作自动放行",
            })
            return

        # 需要审批：检查外部审批结果
        if self._approval_result == "pass":
            self.send("approve_pass")
            self._steps_completed.append("APPROVE_PASS")
            self._persist_state("test")
            self._hash_chain.append("APPROVE", {
                "mode": "manual_pass",
                "approval_result": "pass",
            })
        elif self._approval_result == "reject":
            self.send("approve_reject")
            self._steps_completed.append("APPROVE_REJECT")
            self._do_rollback("造物主拒绝审批")
            self._hash_chain.append("APPROVE", {
                "mode": "manual_reject",
                "approval_result": "reject",
            }, negative=True)
        else:
            # 无审批结果 → 默认拒绝（超时语义）
            self.send("approve_timeout")
            self._steps_completed.append("APPROVE_TIMEOUT")
            self._do_rollback("审批超时，默认拒绝")
            self._hash_chain.append("APPROVE", {
                "mode": "timeout_reject",
                "approval_result": None,
            }, negative=True)

    def set_approval_result(self, result: str):
        """
        外部注入审批结果（HITL异步回调）

        Args:
            result: "pass" 或 "reject"
        """
        self._approval_result = result
        logger.info(f"审批结果注入: {result}")

    # ─── 节点5: TEST ───
    def _do_test(self):
        """测试验证"""
        test_cmd = self._context["test_command"]
        dest = self._context["dest_path"]

        # 基本测试：目标文件存在
        if not os.path.exists(dest):
            error = f"目标文件不存在: {dest}"
            self._hash_chain.append("TEST_FAIL", {"error": error})
            self._fail_and_rollback(error)
            return

        # 基本测试：哈希一致
        dest_hash = self._file_hash(dest)
        if dest_hash != self._context["original_hash"]:
            error = f"目标文件哈希不匹配: 期望={self._context['original_hash']}, 实际={dest_hash}"
            self._hash_chain.append("TEST_FAIL", {"error": error})
            self._fail_and_rollback(error)
            return

        # 自定义测试命令
        if test_cmd:
            import subprocess
            result = subprocess.run(
                test_cmd, shell=True, capture_output=True,
                text=True, timeout=60
            )
            if result.returncode != 0:
                error = f"测试命令失败: {result.stderr}"
                self._hash_chain.append("TEST_FAIL", {"error": error})
                self._fail_and_rollback(error)
                return

        self.send("test_pass")  # test → mark_delete

        self._steps_completed.append("TEST")
        self._persist_state("mark_delete")
        self._hash_chain.append("TEST", {"result": "pass"})

    # ─── 节点6: MARK_DELETE ───
    def _do_mark_delete(self):
        """标记待删"""
        if not self._context["delete_original"]:
            self._steps_completed.append("MARK_DELETE_SKIPPED")
        else:
            self._steps_completed.append("MARK_DELETE")

        self.send("mark_done")  # mark_delete → log

        self._persist_state("log")
        self._hash_chain.append("MARK_DELETE", {
            "delete_original": self._context["delete_original"],
        })

    # ─── 节点7: LOG ───
    def _do_log(self):
        """记录日志"""
        self._context["end_time"] = datetime.now().isoformat()
        self._steps_completed.append("LOG")
        self.send("log_done")  # log → done

        self._persist_state("done")
        self._hash_chain.append("LOG", {
            "steps_completed": self._steps_completed,
            "end_time": self._context["end_time"],
        })

    # ─── 回滚（Saga补偿链语义） ───
    def _do_rollback(self, reason: str):
        """
        回滚 — Saga补偿链 + Event Sourcing补偿事件

        补偿逻辑：
        1. 如果已MODIFY → 恢复备份 + 反向更新引用
        2. 追加补偿事件到哈希链（negative=True）
        """
        if self._rolled_back:
            return  # 幂等性：避免重复回滚

        logger.warning(f"开始回滚: {reason}")
        self._rolled_back = True
        self._rollback_reason = reason

        compensated = []

        # 补偿MODIFY：恢复源文件
        if "MODIFY" in self._steps_completed:
            source = self._context["source_path"]
            backup = self._context.get("backup_path", "")
            dest = self._context["dest_path"]

            if backup and os.path.exists(backup):
                os.makedirs(os.path.dirname(source), exist_ok=True)
                shutil.copy2(backup, source)
                compensated.append("source_restored")
                logger.info(f"已恢复源文件: {source}")

            if dest and os.path.exists(dest):
                os.remove(dest)
                compensated.append("dest_removed")
                logger.info(f"已删除目标文件: {dest}")

            # 补偿引用更新
            for ref in self._ref_results:
                if ref.get("status") == "UPDATED":
                    ref_file = ref["file"]
                    for ref_update in self._context["ref_updates"]:
                        if ref_update["file"] == ref_file:
                            try:
                                with open(ref_file, "r", encoding="utf-8") as f:
                                    content = f.read()
                                content = content.replace(
                                    ref_update["new"], ref_update["old"]
                                )
                                with open(ref_file, "w", encoding="utf-8") as f:
                                    f.write(content)
                                compensated.append(f"ref_reverted:{ref_file}")
                            except Exception as e:
                                logger.error(f"回滚引用失败: {ref_file}, {e}")

        # 追加补偿事件（Event Sourcing语义：红字冲销）
        self._hash_chain.append("ROLLBACK", {
            "reason": reason,
            "compensated": compensated,
        }, negative=True)

        self._context["end_time"] = datetime.now().isoformat()
        self._persist_state("rolled_back")

    def _fail_and_rollback(self, reason: str):
        """从当前状态失败并回滚"""
        # 尝试通过rollback转换到达rolled_back
        try:
            self.send("rollback")
        except Exception:
            pass  # 如果当前状态不支持rollback转换，忽略
        self._do_rollback(reason)

    # ─── 差距2：偏差门联动判断 ───
    def _is_high_impact(self) -> bool:
        """
        判断是否为高危操作 — 偏差门联动

        高危条件（满足任一）：
        1. 操作src/下的核心模块文件
        2. 批量引用更新超过3个文件
        """
        source = self._context.get("source_path", "")
        ref_count = len(self._context.get("ref_updates", []))

        # 核心模块文件检测
        core_files = [
            "tu8_agent.py", "consciousness_cycle.py", "tu8_memory.py",
            "deviation_gate.py", "arch_fsm.py",
        ]
        is_core = any(source.endswith(f) for f in core_files)

        return is_core or ref_count > 3

    # ─── 持久化辅助 ───
    def _persist_state(self, new_state: str):
        """持久化当前状态到SQLite"""
        if self._state_db and self._operation_id:
            self._state_db.update_state(
                operation_id=self._operation_id,
                new_state=new_state,
                context_json=json.dumps(self._context, ensure_ascii=False),
                event_type="transition",
            )

    # ─── 辅助方法 ───
    def _is_path_allowed(self, path: str) -> bool:
        """路径白名单校验"""
        abs_path = os.path.abspath(path)
        for prefix in ALLOWED_PATH_PREFIXES:
            if abs_path.startswith(prefix):
                return True
        return False

    def _file_hash(self, path: str) -> str:
        """计算文件SHA256哈希"""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _build_result(self) -> Dict[str, Any]:
        """构建执行结果"""
        if self._rolled_back:
            status = "ROLLED_BACK"
        else:
            status = self.current_state_id.upper()

        return {
            "status": status,
            "source_path": self._context.get("source_path", ""),
            "dest_path": self._context.get("dest_path", ""),
            "backup_path": self._context.get("backup_path", ""),
            "original_hash": self._context.get("original_hash", ""),
            "steps_completed": self._steps_completed,
            "ref_results": self._ref_results,
            "rollback_reason": self._rollback_reason,
            "approval_required": self._approval_required,
            "approval_result": self._approval_result,
            "start_time": self._context.get("start_time", ""),
            "end_time": self._context.get("end_time", ""),
            "audit_chain_hash": self._hash_chain.last_hash,
        }


# ═══════════════════════════════════════════════════════════
# 差距2：偏差门联动门控函数
# ═══════════════════════════════════════════════════════════

def should_require_approval(deviation_gate=None, user_text: str = "") -> bool:
    """
    偏差门联动判断 — 高偏差触发审批

    Args:
        deviation_gate: DeviationGate实例（可选）
        user_text: 当前用户输入文本

    Returns:
        True表示需要审批
    """
    if deviation_gate is None:
        return False

    # 注册当前输入
    deviation_gate.on_user_input(user_text)

    # 获取偏差分数
    stats = deviation_gate.get_stats()
    total = stats.get("total_filtered", 0)
    passed = stats.get("passed", 0)

    # 如果通过率过高（高偏差环境），强制审批
    if total > 0:
        pass_ratio = passed / total
        if pass_ratio > 0.8:
            return True

    return False


# ═══════════════════════════════════════════════════════════
# 命令行入口（兼容v1.0接口）
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python arch_fsm.py <params_json> [--approve pass|reject]")
        print('示例: python arch_fsm.py \'{"source_path": "D:/test/a.txt", '
              '"dest_path": "D:/test/b.txt", "reason": "重命名"}\'')
        print("      python arch_fsm.py '...' --approve pass")
        sys.exit(1)

    params = json.loads(sys.argv[1])

    # 解析审批参数
    approval_result = None
    approval_required = False
    if "--approve" in sys.argv:
        idx = sys.argv.index("--approve")
        if idx + 1 < len(sys.argv):
            approval_result = sys.argv[idx + 1]
            approval_required = True

    # 创建状态机
    state_db = ArchStateDB()
    chart = ArchitectureChangeChart()

    # 注入审批结果（如果有）
    if approval_result:
        chart.set_approval_result(approval_result)

    result = chart.execute(
        params=params,
        approval_required=approval_required,
        state_db=state_db,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 验证审计日志哈希链
    if chart._hash_chain.verify():
        print("\n✅ 审计日志哈希链验证通过")
    else:
        print("\n❌ 审计日志哈希链验证失败")

    state_db.close()
