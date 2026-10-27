"""
version_tree.py - 版本树数据结构与初始化

用途：实现TU-8架构版本树
来源：涌现#017/#011（版本树初始化 + 造物主绝对确认权）

设计原则：
- 版本树记录架构演进历史
- 每个节点代表一个架构版本
- 支持分支（实验性分支）和合并（稳定分支）
- 造物主拥有绝对确认权（关键节点需要造物主确认）

版本号方案：
- 主版本：v1, v2, v3, ...（稳定分支）
- 子版本：v1.1, v1.2, ...（实验性分支）
- 补丁版本：v1.1.1, v1.1.2, ...（补丁）
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum
import time
import json
import os


class VersionStatus(Enum):
    """
    版本状态。
    """
    DRAFT = "draft"           # 草稿（实验性）
    PROPOSED = "proposed"     # 提议（待确认）
    CONFIRMED = "confirmed"   # 已确认（造物主确认）
    STABLE = "stable"         # 稳定（生产环境）
    DEPRECATED = "deprecated" # 已弃用


@dataclass
class VersionNode:
    """
    版本树节点。
    """
    version: str               # 版本号（如 "v1", "v1.1", "v1.1.1"）
    status: VersionStatus       # 版本状态
    created_at: float         # 创建时间戳
    confirmed_at: Optional[float] = None  # 确认时间戳
    confirmed_by: Optional[str] = None  # 确认者（造物主）
    parent: Optional[str] = None  # 父版本
    children: List[str] = field(default_factory=list)  # 子版本列表
    description: str = ""    # 版本描述
    changes: List[str] = field(default_factory=list)  # 变更列表
    metadata: Dict = field(default_factory=dict)  # 元数据

    def to_dict(self) -> dict:
        """
        转换为字典（用于JSON序列化）。
        """
        return {
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at,
            "confirmed_at": self.confirmed_at,
            "confirmed_by": self.confirmed_by,
            "parent": self.parent,
            "children": self.children,
            "description": self.description,
            "changes": self.changes,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'VersionNode':
        """
        从字典创建（用于JSON反序列化）。
        """
        return cls(
            version=data["version"],
            status=VersionStatus(data["status"]),
            created_at=data["created_at"],
            confirmed_at=data.get("confirmed_at"),
            confirmed_by=data.get("confirmed_by"),
            parent=data.get("parent"),
            children=data.get("children", []),
            description=data.get("description", ""),
            changes=data.get("changes", []),
            metadata=data.get("metadata", {})
        )


class VersionTree:
    """
    版本树管理器。

    维护版本树，支持创建、确认、分支、合并等操作。
    """

    def __init__(self, tree_path: Optional[str] = None):
        """
        初始化版本树。

        Args:
            tree_path: 版本树持久化文件路径（JSON）
        """
        self.tree_path = tree_path
        self.nodes: Dict[str, VersionNode] = {}
        self.root: Optional[str] = None  # 根版本

        # 加载持久化数据
        if tree_path and os.path.exists(tree_path):
            self.load()

    def create_version(
        self,
        version: str,
        parent: Optional[str] = None,
        description: str = "",
        changes: Optional[List[str]] = None,
        status: VersionStatus = VersionStatus.DRAFT
    ) -> VersionNode:
        """
        创建新版本。

        Args:
            version: 版本号
            parent: 父版本（None表示根版本）
            description: 版本描述
            changes: 变更列表
            status: 初始状态

        Returns:
            创建的版本节点
        """
        if version in self.nodes:
            raise ValueError(f"版本已存在: {version}")

        # 创建节点
        node = VersionNode(
            version=version,
            status=status,
            created_at=time.time(),
            parent=parent,
            description=description,
            changes=changes or []
        )

        # 添加到树
        self.nodes[version] = node

        if parent is None:
            # 根版本
            if self.root is not None:
                raise ValueError("根版本已存在")
            self.root = version
        else:
            # 添加到父节点的children
            if parent not in self.nodes:
                raise ValueError(f"父版本不存在: {parent}")
            self.nodes[parent].children.append(version)

        # 持久化
        self.save()

        return node

    def confirm_version(
        self,
        version: str,
        confirmed_by: str = "造物主"
    ) -> VersionNode:
        """
        确认版本（造物主绝对确认权）。

        Args:
            version: 版本号
            confirmed_by: 确认者（必须是"造物主"）

        Returns:
            更新后的版本节点
        """
        if version not in self.nodes:
            raise ValueError(f"版本不存在: {version}")

        node = self.nodes[version]

        # 检查权限（只有造物主可以确认）
        if confirmed_by != "造物主":
            raise PermissionError(f"只有造物主可以确认版本，当前用户: {confirmed_by}")

        # 更新状态
        node.status = VersionStatus.CONFIRMED
        node.confirmed_at = time.time()
        node.confirmed_by = confirmed_by

        # 持久化
        self.save()

        return node

    def promote_to_stable(self, version: str) -> VersionNode:
        """
        提升为稳定版本。

        Args:
            version: 版本号

        Returns:
            更新后的版本节点
        """
        if version not in self.nodes:
            raise ValueError(f"版本不存在: {version}")

        node = self.nodes[version]

        # 检查是否已经确认
        if node.status != VersionStatus.CONFIRMED:
            raise ValueError(f"版本未确认，不能提升为稳定版本: {version}")

        # 更新状态
        node.status = VersionStatus.STABLE

        # 持久化
        self.save()

        return node

    def get_version(self, version: str) -> Optional[VersionNode]:
        """
        获取版本节点。
        """
        return self.nodes.get(version)

    def get_children(self, version: str) -> List[VersionNode]:
        """
        获取子版本列表。
        """
        if version not in self.nodes:
            return []

        node = self.nodes[version]
        return [self.nodes[child] for child in node.children if child in self.nodes]

    def get_path_to_root(self, version: str) -> List[VersionNode]:
        """
        获取从指定版本到根版本的路径。
        """
        if version not in self.nodes:
            return []

        path = []
        current = version

        while current:
            node = self.nodes.get(current)
            if node is None:
                break
            path.append(node)
            current = node.parent

        return path

    def save(self):
        """
        持久化版本树到JSON文件。
        """
        if not self.tree_path:
            return

        os.makedirs(os.path.dirname(self.tree_path), exist_ok=True)

        data = {
            "root": self.root,
            "nodes": {v: node.to_dict() for v, node in self.nodes.items()}
        }

        with open(self.tree_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        """
        从JSON文件加载版本树。
        """
        if not self.tree_path or not os.path.exists(self.tree_path):
            return

        with open(self.tree_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.root = data.get("root")
        self.nodes = {
            v: VersionNode.from_dict(node_data)
            for v, node_data in data.get("nodes", {}).items()
        }


# CLI 测试入口
if __name__ == "__main__":
    print("=== 版本树测试 ===\n")

    # 创建版本树
    tree = VersionTree()

    # 创建根版本
    v1 = tree.create_version(
        version="v1",
        description="初始架构版本",
        changes=["创建SOUL.md", "创建AGENTS.md"]
    )
    print(f"创建根版本: {v1.version} (status={v1.status.value})")

    # 创建子版本（实验性）
    v1_1 = tree.create_version(
        version="v1.1",
        parent="v1",
        description="实验性分支：添加排除法",
        changes=["实现state_machine_dimensions.py", "实现elimination_rules.py"]
    )
    print(f"创建子版本: {v1_1.version} (status={v1_1.status.value})")

    # 确认版本（造物主绝对确认权）
    v1_1_confirmed = tree.confirm_version("v1.1", confirmed_by="造物主")
    print(f"确认版本: {v1_1_confirmed.version} (status={v1_1_confirmed.status.value})")

    # 提升为稳定版本
    v1_1_stable = tree.promote_to_stable("v1.1")
    print(f"提升为稳定版本: {v1_1_stable.version} (status={v1_1_stable.status.value})")

    # 获取路径
    path = tree.get_path_to_root("v1.1")
    print(f"\n路径到根版本: {' -> '.join([n.version for n in path])}")

    print("\n[OK] 测试通过")
