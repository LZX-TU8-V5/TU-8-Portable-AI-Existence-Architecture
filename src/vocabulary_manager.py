"""
统一词汇库管理器

负责所有词汇的统一管理：
- 核心词汇（Phase, SealType...）
- 钩子词汇（trigger, semantic, blacklist...）
- 场景词汇（dev, novel, chat...）
- 事件词汇（记住, 重要...）
- 用户偏好词汇

创建时间：2026-06-27 03:09 GMT+8
来源：架构决策 - 建立统一词汇库
"""

import json
import os
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

WORKSPACE_D = os.path.expanduser("~/.qclaw/workspace")


class VocabularyManager:
    """统一词汇库管理器

    单一真理源（Single Source of Truth）
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path or WORKSPACE_D
        self.vocab_dir = os.path.join(self.workspace_path, "memory", "vocabulary")
        self.vocabularies: Dict[str, Dict] = {}

        # 加载所有词汇
        self._load_all()

    # -------------------------------------------------------------------------
    # 加载词汇
    # -------------------------------------------------------------------------

    def _load_all(self):
        """加载所有词汇文件"""
        os.makedirs(self.vocab_dir, exist_ok=True)

        # 初始化词汇文件（如果不存在）
        self._init_vocab_files()

        # 加载所有词汇
        vocab_files = [
            "core",
            "hooks",
            "scenes",
            "events",
            "anchors",
            "user_preferences"
        ]

        for vocab_name in vocab_files:
            vocab_path = os.path.join(self.vocab_dir, f"{vocab_name}.json")
            try:
                with open(vocab_path, "r", encoding="utf-8") as f:
                    self.vocabularies[vocab_name] = json.load(f)
                logger.info(f"加载词汇: {vocab_name}")
            except Exception as e:
                logger.error(f"加载词汇失败 {vocab_name}: {e}")
                self.vocabularies[vocab_name] = {}

    def _init_vocab_files(self):
        """初始化词汇文件（创建默认词汇）"""

        # core.json - 核心词汇
        core_path = os.path.join(self.vocab_dir, "core.json")
        if not os.path.exists(core_path):
            default_core = {
                "phases": {
                    "AWAKE": "awake",
                    "LIGHT_SLEEP": "light_sleep",
                    "DEEP_SLEEP": "deep_sleep",
                    "HIBERNATION": "hibernation"
                },
                "seal_types": {
                    "ORIGIN": "origin",
                    "RHYTHM": "rhythm",
                    "PHASE_TRANSITION": "phase_transition"
                },
                "anchor_types": {
                    "INTERACTION": "interaction",
                    "INSIGHT": "insight",
                    "MILESTONE": "milestone",
                    "INTERFACE": "interface",
                    "META_COGNITION": "meta_cognition",
                    "EMERGENCY": "emergency"
                }
            }
            self._write_vocab(core_path, default_core)

        # events.json - 事件词汇
        events_path = os.path.join(self.vocab_dir, "events.json")
        if not os.path.exists(events_path):
            default_events = {
                "event_keywords": [
                    "记住", "重要", "核心", "关键决策", "规则", "永远", "从不",
                    "原则", "定义", "身份", "灵魂", "禁止"
                ],
                "scene_keywords": {
                    "dev": ["代码", "重构", "测试", "修复", "bug", "功能"],
                    "novel": ["小说", "章节", "角色", "情节", "钢印"],
                    "chat": ["聊聊", "谈谈", "说说", "讨论"]
                }
            }
            self._write_vocab(events_path, default_events)

        # hooks.json - 钩子词汇
        hooks_path = os.path.join(self.vocab_dir, "hooks.json")
        if not os.path.exists(hooks_path):
            default_hooks = {
                "trigger_hooks": {},
                "semantic_hooks": {},
                "blacklist": ["密码", "token", "secret", "api_key"]
            }
            self._write_vocab(hooks_path, default_hooks)

        # scenes.json - 场景词汇
        scenes_path = os.path.join(self.vocab_dir, "scenes.json")
        if not os.path.exists(scenes_path):
            default_scenes = {
                "scene_tags": ["dev", "novel", "chat", "reflection", "planning"],
                "scene_descriptions": {
                    "dev": "开发模式",
                    "novel": "小说创作",
                    "chat": "闲聊模式",
                    "reflection": "复盘反思",
                    "planning": "规划计划"
                }
            }
            self._write_vocab(scenes_path, default_scenes)

        # anchors.json - 锚点类型词汇
        anchors_path = os.path.join(self.vocab_dir, "anchors.json")
        if not os.path.exists(anchors_path):
            default_anchors = {
                "anchor_type_descriptions": {
                    "interaction": "用户明确指令",
                    "insight": "检测到重复模式/规律",
                    "milestone": "钢印链重大相变点",
                    "interface": "外部系统请求同步",
                    "meta_cognition": "元认知（睡眠周期结束时的二次提炼）",
                    "emergency": "WARM_WAKE 失败后的强制固化"
                }
            }
            self._write_vocab(anchors_path, default_anchors)

        # user_preferences.json - 用户偏好词汇
        user_prefs_path = os.path.join(self.vocab_dir, "user_preferences.json")
        if not os.path.exists(user_prefs_path):
            default_user_prefs = {
                "preferences": {},
                "aliases": {}
            }
            self._write_vocab(user_prefs_path, default_user_prefs)

    def _write_vocab(self, path: str, data: Dict):
        """写入词汇文件"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # 查询接口
    # -------------------------------------------------------------------------

    def get(self, category: str, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取词汇

        Args:
            category: 词汇类别（如 "core.phases"）
            key: 词汇键
            default: 默认值

        Returns:
            词汇值

        Example:
            vocab.get("core.phases", "AWAKE")  # → "awake"
            vocab.get("hooks.trigger_hooks", "简洁")  # → "用户偏好简洁风格"
        """
        # 解析类别（支持点号分隔）
        parts = category.split(".")
        vocab_name = parts[0]

        if vocab_name not in self.vocabularies:
            logger.warning(f"词汇类别不存在: {vocab_name}")
            return default

        # 导航到目标位置
        target = self.vocabularies[vocab_name]
        for part in parts[1:]:
            if part not in target:
                logger.warning(f"词汇路径不存在: {category}")
                return default
            target = target[part]

        # 获取值
        if key not in target:
            logger.debug(f"词汇不存在: {category}.{key}")
            return default

        return target[key]

    def get_all(self, category: str) -> Dict:
        """获取某类所有词汇

        Args:
            category: 词汇类别

        Returns:
            词汇字典

        Example:
            vocab.get_all("core.phases")  # → {"AWAKE": "awake", ...}
        """
        parts = category.split(".")
        vocab_name = parts[0]

        if vocab_name not in self.vocabularies:
            return {}

        target = self.vocabularies[vocab_name]
        for part in parts[1:]:
            if part not in target:
                return {}
            target = target[part]

        return target

    def get_list(self, category: str) -> List[str]:
        """获取词汇列表（用于数组类型的词汇）

        Args:
            category: 词汇类别

        Returns:
            词汇列表

        Example:
            vocab.get_list("events.event_keywords")  # → ["记住", "重要", ...]
        """
        result = self.get_all(category)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return list(result.keys())
        else:
            return []

    # -------------------------------------------------------------------------
    # 修改接口
    # -------------------------------------------------------------------------

    def add(self, category: str, key: str, value: str) -> bool:
        """添加词汇

        Args:
            category: 词汇类别
            key: 词汇键
            value: 词汇值

        Returns:
            是否成功
        """
        parts = category.split(".")
        vocab_name = parts[0]

        if vocab_name not in self.vocabularies:
            logger.error(f"词汇类别不存在: {vocab_name}")
            return False

        # 导航到目标位置
        target = self.vocabularies[vocab_name]
        for part in parts[1:]:
            if part not in target:
                target[part] = {}
            target = target[part]

        # 添加词汇
        target[key] = value

        # 保存到文件
        self._save_vocab(vocab_name)

        logger.info(f"添加词汇: {category}.{key} = {value}")
        return True

    def remove(self, category: str, key: str) -> bool:
        """删除词汇

        Args:
            category: 词汇类别
            key: 词汇键

        Returns:
            是否成功
        """
        parts = category.split(".")
        vocab_name = parts[0]

        if vocab_name not in self.vocabularies:
            return False

        target = self.vocabularies[vocab_name]
        for part in parts[1:]:
            if part not in target:
                return False
            target = target[part]

        if key not in target:
            return False

        del target[key]
        self._save_vocab(vocab_name)

        logger.info(f"删除词汇: {category}.{key}")
        return True

    def _save_vocab(self, vocab_name: str):
        """保存词汇到文件"""
        vocab_path = os.path.join(self.vocab_dir, f"{vocab_name}.json")
        with open(vocab_path, "w", encoding="utf-8") as f:
            json.dump(self.vocabularies[vocab_name], f, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # 搜索接口
    # -------------------------------------------------------------------------

    def search(self, query: str, category: Optional[str] = None) -> List[Dict]:
        """搜索词汇

        Args:
            query: 搜索关键词
            category: 限定类别（可选）

        Returns:
            匹配结果列表 [{"category": ..., "key": ..., "value": ...}]
        """
        results = []

        # 确定搜索范围
        if category:
            vocab_names = [category.split(".")[0]]
        else:
            vocab_names = list(self.vocabularies.keys())

        # 搜索
        for vocab_name in vocab_names:
            if vocab_name not in self.vocabularies:
                continue

            self._search_in_dict(
                self.vocabularies[vocab_name],
                vocab_name,
                query.lower(),
                results
            )

        return results

    def _search_in_dict(self, d: Dict, path: str, query: str, results: List):
        """递归搜索字典"""
        for key, value in d.items():
            current_path = f"{path}.{key}"

            if isinstance(value, dict):
                self._search_in_dict(value, current_path, query, results)
            elif isinstance(value, list):
                for item in value:
                    if query in str(item).lower():
                        results.append({
                            "category": path,
                            "key": key,
                            "value": item
                        })
            else:
                if query in str(key).lower() or query in str(value).lower():
                    results.append({
                        "category": path,
                        "key": key,
                        "value": value
                    })

    # -------------------------------------------------------------------------
    # 重载接口
    # -------------------------------------------------------------------------

    def reload(self):
        """重新加载所有词汇"""
        logger.info("重新加载所有词汇...")
        self.vocabularies = {}
        self._load_all()
        logger.info("词汇重载完成")

    # -------------------------------------------------------------------------
    # 统计接口
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """获取词汇库统计"""
        stats = {
            "total_categories": len(self.vocabularies),
            "categories": {}
        }

        for vocab_name, vocab_data in self.vocabularies.items():
            count = self._count_entries(vocab_data)
            stats["categories"][vocab_name] = count

        return stats

    def _count_entries(self, d: Dict) -> int:
        """递归计算词条数量"""
        count = 0
        for value in d.values():
            if isinstance(value, dict):
                count += self._count_entries(value)
            elif isinstance(value, list):
                count += len(value)
            else:
                count += 1
        return count
