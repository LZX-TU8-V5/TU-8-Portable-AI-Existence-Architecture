"""
Phase 2.5 测试：统一词汇库

测试目标：
1. 词汇加载
2. 查询接口
3. 修改接口
4. 搜索功能
5. 统计功能
"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vocabulary_manager import VocabularyManager


def test_vocab_loading():
    """测试词汇加载"""
    print("=== 测试词汇加载 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        # 验证词汇文件已创建
        vocab_dir = os.path.join(temp_dir, "memory", "vocabulary")
        assert os.path.exists(vocab_dir)
        print(f"[PASS] 词汇目录已创建")

        # 验证所有词汇文件
        expected_files = [
            "core.json",
            "hooks.json",
            "scenes.json",
            "events.json",
            "anchors.json",
            "user_preferences.json"
        ]

        for filename in expected_files:
            filepath = os.path.join(vocab_dir, filename)
            assert os.path.exists(filepath), f"{filename} 不存在"
            print(f"[PASS] {filename} 已创建")

    finally:
        shutil.rmtree(temp_dir)


def test_get_vocabulary():
    """测试查询接口"""
    print("\n=== 测试查询接口 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        # 测试 get()
        phase = vocab.get("core.phases", "AWAKE")
        assert phase == "awake"
        print(f"[PASS] get('core.phases', 'AWAKE') = {phase}")

        seal_type = vocab.get("core.seal_types", "ORIGIN")
        assert seal_type == "origin"
        print(f"[PASS] get('core.seal_types', 'ORIGIN') = {seal_type}")

        # 测试 get_all()
        phases = vocab.get_all("core.phases")
        assert "AWAKE" in phases
        assert "LIGHT_SLEEP" in phases
        print(f"[PASS] get_all('core.phases') = {len(phases)} 个词汇")

        # 测试 get_list()
        keywords = vocab.get_list("events.event_keywords")
        assert "记住" in keywords
        assert "重要" in keywords
        print(f"[PASS] get_list('events.event_keywords') = {len(keywords)} 个词汇")

    finally:
        shutil.rmtree(temp_dir)


def test_add_remove():
    """测试添加/删除接口"""
    print("\n=== 测试添加/删除接口 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        # 添加词汇
        success = vocab.add("hooks.trigger_hooks", "简洁", "用户偏好简洁风格")
        assert success
        print(f"[PASS] 添加词汇成功")

        # 查询添加的词汇
        value = vocab.get("hooks.trigger_hooks", "简洁")
        assert value == "用户偏好简洁风格"
        print(f"[PASS] 查询添加的词汇: 简洁 = {value}")

        # 删除词汇
        success = vocab.remove("hooks.trigger_hooks", "简洁")
        assert success
        print(f"[PASS] 删除词汇成功")

        # 验证已删除
        value = vocab.get("hooks.trigger_hooks", "简洁")
        assert value is None
        print(f"[PASS] 验证词汇已删除")

    finally:
        shutil.rmtree(temp_dir)


def test_search():
    """测试搜索功能"""
    print("\n=== 测试搜索功能 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        # 搜索 "awake"
        results = vocab.search("awake")
        assert len(results) > 0
        print(f"[PASS] 搜索 'awake': 找到 {len(results)} 个结果")

        # 搜索 "记住"
        results = vocab.search("记住")
        assert len(results) > 0
        print(f"[PASS] 搜索 '记住': 找到 {len(results)} 个结果")

        # 限定类别搜索
        results = vocab.search("awake", category="core")
        assert len(results) > 0
        print(f"[PASS] 限定类别搜索 'core.awake': 找到 {len(results)} 个结果")

    finally:
        shutil.rmtree(temp_dir)


def test_stats():
    """测试统计功能"""
    print("\n=== 测试统计功能 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        stats = vocab.get_stats()

        assert stats["total_categories"] == 6
        print(f"[PASS] 总类别数: {stats['total_categories']}")

        for category, count in stats["categories"].items():
            print(f"  - {category}: {count} 个词条")

    finally:
        shutil.rmtree(temp_dir)


def test_reload():
    """测试重载功能"""
    print("\n=== 测试重载功能 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        # 添加词汇
        vocab.add("user_preferences.preferences", "测试词汇", "测试值")
        print(f"[PASS] 添加测试词汇")

        # 重载
        vocab.reload()
        print(f"[PASS] 重载词汇库")

        # 验证词汇仍然存在
        value = vocab.get("user_preferences.preferences", "测试词汇")
        assert value == "测试值"
        print(f"[PASS] 验证重载后词汇仍存在")

    finally:
        shutil.rmtree(temp_dir)


def test_integration():
    """测试集成场景"""
    print("\n=== 测试集成场景 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        vocab = VocabularyManager(workspace_path=temp_dir)

        # 场景 1：检测事件关键词
        text = "这个很重要，你要记住"
        keywords = vocab.get_list("events.event_keywords")

        detected = []
        for keyword in keywords:
            if keyword in text:
                detected.append(keyword)

        assert len(detected) >= 2
        print(f"[PASS] 检测到事件关键词: {detected}")

        # 场景 2：识别场景
        text = "我们来重构这段代码"
        scene_keywords = vocab.get_all("events.scene_keywords")

        detected_scene = None
        for scene, keywords in scene_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    detected_scene = scene
                    break

        assert detected_scene == "dev"
        print(f"[PASS] 识别到场景: {detected_scene}")

        # 场景 3：添加用户偏好钩子
        vocab.add("hooks.trigger_hooks", "简洁", "用户偏好简洁风格")
        vocab.add("hooks.trigger_hooks", "安全", "用户强调安全性")

        hooks = vocab.get_all("hooks.trigger_hooks")
        assert "简洁" in hooks
        assert "安全" in hooks
        print(f"[PASS] 添加用户偏好钩子: {len(hooks)} 个")

    finally:
        shutil.rmtree(temp_dir)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 2.5 测试：统一词汇库")
    print("=" * 60)

    test_vocab_loading()
    test_get_vocabulary()
    test_add_remove()
    test_search()
    test_stats()
    test_reload()
    test_integration()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
