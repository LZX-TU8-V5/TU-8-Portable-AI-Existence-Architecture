# -*- coding: utf-8 -*-
"""
tu8_planner.py — TU-8 规划器 v1.0
日期: 2026-05-23
功能: 目标分解、任务依赖管理、执行进度跟踪

层级: L4 协作层（规划器引入）
依赖: tu8_agent.py（主控集成）、tu8_memory.py（经验检索）

核心概念:
  Goal(目标) → Plan(计划) → Task(任务) → Step(步骤)
  DAG依赖图: Task A → Task B (B依赖A完成)
  状态机: PENDING → RUNNING → DONE/FAILED/PAUSED
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import os
import sys
import json
import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

# =============================================================================
# 日志
# =============================================================================

# 延迟导入（避免循环依赖）
_TU8Toolchain = None
_CREATE_TASK_CONTEXT = None

def _get_toolchain():
    global _TU8Toolchain, _CREATE_TASK_CONTEXT
    if _TU8Toolchain is None:
        from tu8_toolchain import TU8Toolchain as TC, create_task_context as CTC
        _TU8Toolchain = TC
        _CREATE_TASK_CONTEXT = CTC
    return _TU8Toolchain, _CREATE_TASK_CONTEXT

# =============================================================================
# 日志
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TU8.Planner")

# =============================================================================
# 枚举
# =============================================================================

class TaskStatus(str, Enum):
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    DONE = "done"            # 完成
    FAILED = "failed"        # 失败
    PAUSED = "paused"       # 暂停
    SKIPPED = "skipped"     # 跳过（依赖失败）


class PlanStatus(str, Enum):
    DRAFT = "draft"         # 草稿（待确认）
    APPROVED = "approved"   # 已批准（可执行）
    RUNNING = "running"      # 执行中
    DONE = "done"            # 全部完成
    FAILED = "failed"        # 有任务失败
    PAUSED = "paused"       # 暂停
    CANCELLED = "cancelled" # 取消


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class Task:
    """原子任务单元"""
    id: str                   # 唯一ID (task_xxx)
    description: str          # 任务描述
    status: TaskStatus = TaskStatus.PENDING

    # 依赖（前置任务ID列表）
    depends_on: List[str] = field(default_factory=list)

    # 结果
    result: str = ""         # 执行结果摘要
    error: str = ""          # 错误信息

    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    # 元数据
    tags: List[str] = field(default_factory=list)
    priority: int = 0        # 优先级（数字越大越优先）
    estimated_minutes: int = 0  # 预估耗时

    # 重试
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tags": self.tags,
            "priority": self.priority,
            "estimated_minutes": self.estimated_minutes,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Task":
        t = cls(
            id=d["id"],
            description=d["description"],
            status=TaskStatus(d["status"]),
            depends_on=d.get("depends_on", []),
            result=d.get("result", ""),
            error=d.get("error", ""),
            created_at=d.get("created_at", time.time()),
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            tags=d.get("tags", []),
            priority=d.get("priority", 0),
            estimated_minutes=d.get("estimated_minutes", 0),
            retry_count=d.get("retry_count", 0),
            max_retries=d.get("max_retries", 3),
        )
        return t

    def duration_s(self) -> Optional[float]:
        """执行耗时（秒）"""
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    def is_ready(self, completed_ids: Set[str]) -> bool:
        """依赖是否已全部完成"""
        return all(dep in completed_ids for dep in self.depends_on)

    def mark_running(self):
        self.status = TaskStatus.RUNNING
        self.started_at = time.time()

    def mark_done(self, result: str = ""):
        self.status = TaskStatus.DONE
        self.result = result
        self.finished_at = time.time()

    def mark_failed(self, error: str = ""):
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = time.time()

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries


@dataclass
class Plan:
    """执行计划（DAG）"""
    id: str                   # 唯一ID (plan_xxx)
    goal: str                # 原始目标描述
    tasks: Dict[str, Task] = field(default_factory=dict)  # task_id → Task
    status: PlanStatus = PlanStatus.DRAFT

    # 元数据
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    approved_at: Optional[float] = None
    finished_at: Optional[float] = None

    # 上下文
    context: Dict = field(default_factory=dict)  # 全局上下文（共享变量）

    # 执行策略
    strategy: str = "sequential"  # sequential / parallel / mixed

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_at": self.approved_at,
            "finished_at": self.finished_at,
            "context": self.context,
            "strategy": self.strategy,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Plan":
        p = cls(
            id=d["id"],
            goal=d["goal"],
            status=PlanStatus(d["status"]),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            approved_at=d.get("approved_at"),
            finished_at=d.get("finished_at"),
            context=d.get("context", {}),
            strategy=d.get("strategy", "sequential"),
        )
        for tid, td in d.get("tasks", {}).items():
            p.tasks[tid] = Task.from_dict(td)
        return p

    # -------------------------------------------------------------------------
    # DAG 分析
    # -------------------------------------------------------------------------

    def get_ready_tasks(self) -> List[Task]:
        """获取当前可执行的任务（依赖已完成）"""
        completed = {tid for tid, t in self.tasks.items() if t.status == TaskStatus.DONE}
        ready = []
        for tid, task in self.tasks.items():
            if task.status != TaskStatus.PENDING:
                continue
            if task.is_ready(completed):
                ready.append(task)
        # 按优先级排序
        ready.sort(key=lambda t: -t.priority)
        return ready

    def get_dependents(self, task_id: str) -> List[str]:
        """获取依赖于指定任务的所有任务ID"""
        return [tid for tid, t in self.tasks.items() if task_id in t.depends_on]

    def check_cycle(self) -> Optional[List[str]]:
        """检测依赖环（DFS），返回环路径或None"""
        # 简化实现：拓扑排序检测
        in_degree = {tid: len(t.depends_on) for tid, t in self.tasks.items()}
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        ordered = []

        while queue:
            node = queue.pop(0)
            ordered.append(node)
            for dependent in self.get_dependents(node):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(ordered) != len(self.tasks):
            # 有环：找出未被排序的节点
            remaining = set(self.tasks.keys()) - set(ordered)
            return list(remaining)
        return None

    def topological_sort(self) -> List[str]:
        """拓扑排序（执行顺序）"""
        in_degree = {tid: len(t.depends_on) for tid, t in self.tasks.items()}
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        ordered = []

        while queue:
            # 优先级高的先出队
            queue.sort(key=lambda tid: -self.tasks[tid].priority)
            node = queue.pop(0)
            ordered.append(node)
            for dependent in self.get_dependents(node):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        return ordered

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    def get_status_counts(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in TaskStatus}
        for t in self.tasks.values():
            counts[t.status.value] += 1
        return counts

    def get_progress(self) -> Tuple[int, int, float]:
        """返回 (已完成, 总数, 完成百分比)"""
        total = len(self.tasks)
        if total == 0:
            return 0, 0, 0.0
        done = sum(1 for t in self.tasks.values() if t.status == TaskStatus.DONE)
        pct = done / total * 100
        return done, total, pct

    def get_failed_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行任务"""
        ready = self.get_ready_tasks()
        return ready[0] if ready else None

    # -------------------------------------------------------------------------
    # 修改操作
    # -------------------------------------------------------------------------

    def add_task(self, task: Task):
        if task.id in self.tasks:
            raise ValueError(f"Task {task.id} already exists")
        self.tasks[task.id] = task
        self.updated_at = time.time()

    def update_task(self, task_id: str, **kwargs):
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        task = self.tasks[task_id]
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        self.updated_at = time.time()

    def approve(self):
        """批准计划（变为可执行）"""
        if self.status != PlanStatus.DRAFT:
            raise ValueError(f"Cannot approve plan in status {self.status}")
        # 检查依赖环
        cycle = self.check_cycle()
        if cycle:
            raise ValueError(f"Dependency cycle detected: {cycle}")
        self.status = PlanStatus.APPROVED
        self.approved_at = time.time()
        self.updated_at = time.time()

    def cancel(self):
        self.status = PlanStatus.CANCELLED
        self.updated_at = time.time()

    # -------------------------------------------------------------------------
    # 报告生成
    # -------------------------------------------------------------------------

    def generate_report(self) -> str:
        """生成计划执行报告（Markdown）"""
        done, total, pct = self.get_progress()
        status_counts = self.get_status_counts()

        lines = [
            f"## 计划报告: {self.id}",
            f"",
            f"- **目标**: {self.goal}",
            f"- **状态**: {self.status.value}",
            f"- **进度**: {done}/{total} ({pct:.1f}%)",
            f"- **策略**: {self.strategy}",
            f"",
            f"### 任务状态分布",
            f"- [OK] 完成: {status_counts['done']}",
            f"- ⏳ 等待: {status_counts['pending']}",
            f"-  执行中: {status_counts['running']}",
            f"- [X] 失败: {status_counts['failed']}",
            f"- ⏸ 暂停: {status_counts['paused']}",
            f"",
            f"### 任务列表（拓扑序）",
        ]

        ordered = self.topological_sort()
        for i, tid in enumerate(ordered, 1):
            task = self.tasks[tid]
            status_icon = {
                TaskStatus.DONE: "[OK]",
                TaskStatus.RUNNING: "",
                TaskStatus.PENDING: "⏳",
                TaskStatus.FAILED: "[X]",
                TaskStatus.PAUSED: "⏸",
                TaskStatus.SKIPPED: "⏭",
            }.get(task.status, "?")

            dep_str = f" ← [{', '.join(task.depends_on)}]" if task.depends_on else ""
            lines.append(f"{i}. {status_icon} **{tid}**: {task.description}{dep_str}")

            if task.result:
                lines.append(f"   → 结果: {task.result[:80]}")
            if task.error:
                lines.append(f"   → 错误: {task.error[:80]}")

        return "\n".join(lines)


# =============================================================================
# 规划器核心
# =============================================================================

class TU8Planner:
    """
    TU-8 规划器

    功能:
    1. 目标分解（Goal → Plan）
    2. 依赖管理（DAG构建与验证）
    3. 执行调度（就绪任务选择）
    4. 进度跟踪（状态更新与报告）
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)
        self.plans_dir = self.workspace / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)

        # 活跃计划
        self.active_plans: Dict[str, Plan] = {}

        # 分解模板（规则库）
        self.decomposition_templates = self._load_templates()

        logger.info(f"Planner初始化完成 plans_dir={self.plans_dir}")

    # -------------------------------------------------------------------------
    # 目标分解
    # -------------------------------------------------------------------------

    def decompose(self, goal: str, strategy: str = "sequential") -> Plan:
        """
        分解目标为计划

        策略:
        - rule_based: 基于规则模板分解（快速，适合常见任务）
        - llm_based: 基于LLM分解（灵活，适合新任务）
        - hybrid: 先规则后LLM（默认）

        当前实现: rule_based（模板匹配）+ 简单启发式
        """
        plan_id = f"plan_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        plan = Plan(id=plan_id, goal=goal, strategy=strategy)

        logger.info(f"分解目标: {goal[:50]}... → {plan_id}")

        # 尝试规则匹配
        tasks = self._rule_based_decompose(goal)
        if tasks:
            for task in tasks:
                plan.add_task(task)
        else:
            # 降级：简单启发式（按句子分割）
            tasks = self._heuristic_decompose(goal)
            for task in tasks:
                plan.add_task(task)

        # 验证依赖
        cycle = plan.check_cycle()
        if cycle:
            logger.warning(f"依赖环检测: {cycle}，尝试自动修复")
            self._fix_cycle(plan)

        logger.info(f"分解完成: {len(plan.tasks)} 个任务")
        return plan

    def _rule_based_decompose(self, goal: str) -> List[Task]:
        """基于规则模板分解"""
        tasks = []
        goal_lower = goal.lower()

        # 模板1: 写代码/脚本 → 分析 → 编码 → 测试
        if any(kw in goal_lower for kw in ["写", "编码", "实现", "开发"]):
            tasks = [
                self._make_task("需求分析", "分析需求，确定输入输出和边界条件"),
                self._make_task("架构设计", "设计模块结构和接口", depends_on=["task_1"]),
                self._make_task("编码实现", "编写代码实现功能", depends_on=["task_2"]),
                self._make_task("测试验证", "编写测试用例并验证", depends_on=["task_3"]),
                self._make_task("文档撰写", "编写使用文档", depends_on=["task_3"]),
            ]

        # 模板2: 分析/诊断 → 信息收集 → 分析 → 建议
        elif any(kw in goal_lower for kw in ["分析", "诊断", "排查", "检查"]):
            tasks = [
                self._make_task("信息收集", "收集相关日志、配置、错误信息"),
                self._make_task("问题分析", "分析根因", depends_on=["task_1"]),
                self._make_task("方案设计", "设计修复方案", depends_on=["task_2"]),
                self._make_task("实施验证", "实施修复并验证", depends_on=["task_3"]),
            ]

        # 模板3: 文档/写作 → 大纲 → 初稿 → 润色
        elif any(kw in goal_lower for kw in ["文档", "写作", "文章", "报告"]):
            tasks = [
                self._make_task("大纲设计", "设计文档结构和大纲"),
                self._make_task("内容撰写", "根据大纲撰写内容", depends_on=["task_1"]),
                self._make_task("审校润色", "审校并润色内容", depends_on=["task_2"]),
                self._make_task("格式排版", "排版和格式调整", depends_on=["task_3"]),
            ]

        # 模板4: 部署/发布 → 准备 → 部署 → 验证
        elif any(kw in goal_lower for kw in ["部署", "发布", "上线", "安装"]):
            tasks = [
                self._make_task("环境准备", "准备部署环境和依赖"),
                self._make_task("打包构建", "打包构建部署包", depends_on=["task_1"]),
                self._make_task("部署实施", "执行部署", depends_on=["task_2"]),
                self._make_task("冒烟测试", "执行冒烟测试验证", depends_on=["task_3"]),
            ]

        if tasks:
            # 设置ID
            for i, task in enumerate(tasks, 1):
                task.id = f"task_{i}"

        return tasks

    def _heuristic_decompose(self, goal: str) -> List[Task]:
        """启发式分解（降级方案）"""
        # 按"然后"、"接着"、"再"等连接词分割
        import re
        parts = re.split(r'[，,。；;、\n]+', goal)
        parts = [p.strip() for p in parts if p.strip()]

        tasks = []
        prev_id = None
        for i, part in enumerate(parts, 1):
            task_id = f"task_{i}"
            task = self._make_task(
                f"步骤{i}",
                part,
                depends_on=[prev_id] if prev_id else []
            )
            task.id = task_id
            tasks.append(task)
            prev_id = task_id

        return tasks

    def _infer_tags(self, description: str) -> List[str]:
        """从任务描述推断标签"""
        desc = description.lower()
        tags = []

        # 文件读取
        if any(kw in desc for kw in ["读取", "读", "read", "查看", "打开"]):
            tags.append("file_read")
        # 文件写入
        if any(kw in desc for kw in ["写入", "写", "write", "保存", "输出"]):
            tags.append("file_write")
        # Shell执行
        if any(kw in desc for kw in ["执行", "运行", "execute", "run", "命令", "command", "脚本", "script"]):
            tags.append("shell_exec")
        # 浏览器
        if any(kw in desc for kw in ["浏览器", "browser", "网页", "web", "http", "url"]):
            tags.append("browser_ctrl")
        # 记忆检索
        if any(kw in desc for kw in ["检索", "搜索", "search", "记忆", "memory", "查找", "查询"]):
            tags.append("memory_search")
        # URL获取
        if any(kw in desc for kw in ["抓取", "fetch", "爬取", "下载", "download"]):
            tags.append("web_fetch")

        # 兜底：如果没有匹配任何标签，根据动词猜测
        if not tags:
            if any(kw in desc for kw in ["分析", "设计", "实现", "编写", "开发"]):
                tags.append("shell_exec")  # 默认执行Python脚本
            else:
                tags.append("file_read")  # 默认读取文件

        return tags

    def _make_task(self, name: str, description: str, depends_on: List[str] = None) -> Task:
        """创建任务"""
        return Task(
            id="",  # 将在调用处设置
            description=description,
            depends_on=depends_on or [],
            tags=self._infer_tags(description),
            priority=0,
        )

    def _fix_cycle(self, plan: Plan):
        """尝试修复依赖环（简化：断开最后一个依赖）"""
        cycle = plan.check_cycle()
        if not cycle:
            return
        # 找到环中最后一个任务，断开其第一个依赖
        last_task_id = cycle[-1]
        last_task = plan.tasks[last_task_id]
        if last_task.depends_on:
            removed = last_task.depends_on.pop(0)
            logger.info(f"修复环: 断开 {last_task_id} → {removed}")

    def _load_templates(self) -> Dict:
        """加载分解模板（预留）"""
        return {}

    # -------------------------------------------------------------------------
    # 计划管理
    # -------------------------------------------------------------------------

    def save_plan(self, plan: Plan, filename: str = None):
        """保存计划到文件"""
        if not filename:
            filename = f"{plan.id}.json"
        path = self.plans_dir / filename
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"计划已保存: {path}")

    def load_plan(self, plan_id: str) -> Optional[Plan]:
        """从文件加载计划"""
        # 尝试不同后缀
        for suffix in [".json", ".md"]:
            path = self.plans_dir / f"{plan_id}{suffix}"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                return Plan.from_dict(d)
        return None

    def list_plans(self) -> List[str]:
        """列出所有保存的计划"""
        return [p.stem for p in self.plans_dir.glob("*.json")]

    def delete_plan(self, plan_id: str):
        """删除计划文件"""
        for suffix in [".json", ".md"]:
            path = self.plans_dir / f"{plan_id}{suffix}"
            if path.exists():
                path.unlink()
                logger.info(f"计划已删除: {path}")

    # -------------------------------------------------------------------------
    # 执行引擎（与TU8Agent集成）
    # -------------------------------------------------------------------------

    def execute_plan(self, plan: Plan, agent_callback=None) -> Plan:
        """
        执行计划

        agent_callback: 回调函数，签名: (task: Task) -> str (结果)
                       通常由 TU8Agent 提供
        """
        if plan.status not in (PlanStatus.APPROVED, PlanStatus.PAUSED):
            raise ValueError(f"Plan must be approved before execution, current: {plan.status}")

        plan.status = PlanStatus.RUNNING
        logger.info(f"开始执行计划: {plan.id}")

        max_iterations = len(plan.tasks) * 2  # 防止死循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # 检查是否全部完成
            done, total, pct = plan.get_progress()
            if done == total:
                plan.status = PlanStatus.DONE
                plan.finished_at = time.time()
                logger.info(f"计划执行完成: {plan.id} ({pct:.1f}%)")
                break

            # 获取下一个就绪任务
            next_task = plan.get_next_task()
            if not next_task:
                # 没有就绪任务 → 有失败任务阻塞
                failed = plan.get_failed_tasks()
                if failed:
                    plan.status = PlanStatus.FAILED
                    logger.error(f"计划执行失败: 阻塞任务 {[t.id for t in failed]}")
                    break
                else:
                    # 所有任务都在执行中或暂停
                    logger.info("所有任务都在执行中，等待...")
                    time.sleep(1)
                    continue

            # 执行任务
            next_task.mark_running()
            logger.info(f"执行任务: {next_task.id} - {next_task.description}")

            try:
                if agent_callback:
                    result = agent_callback(next_task)
                else:
                    # 尝试通过工具链自动执行
                    result = self._auto_execute_task(next_task, plan)

                # 检查结果
                if result and "[降级]" in str(result):
                    logger.warning(f"任务 {next_task.id} 通过降级完成: {result}")

                next_task.mark_done(result or "")
                logger.info(f"任务完成: {next_task.id}")
            except Exception as e:
                error_msg = str(e)
                next_task.mark_failed(error_msg)
                logger.error(f"任务失败: {next_task.id} - {error_msg}")

                # 错误分类决策
                from tu8_toolchain import ErrorHandler, ErrorSeverity
                severity = ErrorHandler.classify(error_msg)

                if ErrorHandler.should_retry(severity, next_task.retry_count):
                    next_task.retry_count += 1
                    delay_ms = ErrorHandler.backoff_ms(next_task.retry_count - 1)
                    next_task.status = TaskStatus.PENDING
                    logger.info(
                        f"任务重试: {next_task.id} "
                        f"({next_task.retry_count}/{next_task.max_retries}) "
                        f"severity={severity.value} 退避={delay_ms}ms"
                    )
                    time.sleep(delay_ms / 1000)
                else:
                    # 致命错误或重试耗尽 → 跳过依赖任务
                    dependents = plan.get_dependents(next_task.id)
                    for dep_id in dependents:
                        plan.tasks[dep_id].status = TaskStatus.SKIPPED
                    logger.warning(
                        f"任务放弃(severity={severity.value})，跳过依赖: {dependents}"
                    )

        # 保存最终状态
        self.save_plan(plan)
        return plan

    # -------------------------------------------------------------------------
    # 查询接口
    # -------------------------------------------------------------------------

    def get_plan_status(self, plan: Plan) -> Dict:
        """获取计划状态摘要"""
        done, total, pct = plan.get_progress()
        return {
            "id": plan.id,
            "goal": plan.goal,
            "status": plan.status.value,
            "progress": f"{done}/{total} ({pct:.1f}%)",
            "tasks": plan.get_status_counts(),
        }

    def get_next_task_with_tool_call(self, plan: Plan) -> Optional[Tuple]:
        """
        获取下一个就绪任务及其工具调用请求
        
        返回:
            (task, tool_call_request) 或 None（无就绪任务）
            
        tool_call_request 结构:
            {"tool": "read", "params": {...}}
            可直接用于 OpenClaw 工具调用
        """
        task = plan.get_next_task()
        if not task:
            return None

        try:
            TC, CTC = _get_toolchain()
            toolchain = TC(workspace=self.plans_dir)
            ctx = CTC(task, plan, workspace=self.plans_dir)
            result = toolchain.dispatch(ctx)

            if not result.success:
                logger.warning(f"工具链分发失败: {task.id} - {result.error}")
                return (task, {"error": result.error})

            logger.info(f"任务 {task.id} 工具调用已准备: {result.metadata.get('tool')}")
            return (task, result.metadata)
        except Exception as e:
            logger.error(f"获取工具调用失败: {task.id} - {e}")
            return (task, {"error": str(e)})

    def pretty_print(self, plan: Plan):
        """美化打印计划"""
        print(plan.generate_report())


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="TU-8 规划器")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # decompose: 分解目标
    p_decompose = subparsers.add_parser("decompose", help="分解目标为计划")
    p_decompose.add_argument("goal", help="目标描述")
    p_decompose.add_argument("--strategy", default="sequential", choices=["sequential", "parallel", "mixed"])
    p_decompose.add_argument("--save", action="store_true", help="保存到文件")

    # execute: 执行计划
    p_execute = subparsers.add_parser("execute", help="执行计划")
    p_execute.add_argument("plan_id", help="计划ID")

    # list: 列出计划
    subparsers.add_parser("list", help="列出所有计划")

    # show: 显示计划
    p_show = subparsers.add_parser("show", help="显示计划详情")
    p_show.add_argument("plan_id", help="计划ID")

    # next-task: 获取下一个任务及工具调用
    p_next = subparsers.add_parser("next-task", help="获取下一个就绪任务及工具调用")
    p_next.add_argument("plan_id", help="计划ID")
    p_next.add_argument("--json", action="store_true", help="以JSON格式输出")

    args = parser.parse_args()

    planner = TU8Planner()

    if args.command == "decompose":
        plan = planner.decompose(args.goal, args.strategy)
        print(plan.generate_report())
        if args.save:
            planner.save_plan(plan)
            print(f"\n[已保存] {planner.plans_dir / f'{plan.id}.json'}")

    elif args.command == "execute":
        plan = planner.load_plan(args.plan_id)
        if not plan:
            print(f"计划未找到: {args.plan_id}")
            return
        plan.approve()
        planner.execute_plan(plan)
        print(plan.generate_report())

    elif args.command == "list":
        plans = planner.list_plans()
        print(f"共 {len(plans)} 个计划:")
        for p in plans:
            print(f"  - {p}")

    elif args.command == "show":
        plan = planner.load_plan(args.plan_id)
        if plan:
            print(plan.generate_report())
        else:
            print(f"计划未找到: {args.plan_id}")

    elif args.command == "next-task":
        plan = planner.load_plan(args.plan_id)
        if not plan:
            print(f"计划未找到: {args.plan_id}")
            return

        result = planner.get_next_task_with_tool_call(plan)
        if not result:
            print(json.dumps({"status": "no_ready_task", "message": "无就绪任务"}, ensure_ascii=False))
            return

        task, tool_call = result
        output = {
            "task_id": task.id,
            "description": task.description,
            "status": task.status.value,
            "tool_call": tool_call,
        }

        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(f"\n[就绪任务] {task.id} - {task.description}")
            print(f"  状态: {task.status.value}")
            print(f"  工具: {tool_call.get('tool', 'N/A')}")
            print(f"  参数: {tool_call.get('params', {})}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
