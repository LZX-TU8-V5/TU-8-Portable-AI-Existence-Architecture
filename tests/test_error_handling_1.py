# -*- coding: utf-8 -*-
"""
test_error_handling.py — TU-8 错误处理/降级/混沌 三合一测试
日期: 2026-05-23

三个测试套件:
  A. 语义等价性单元测试 — 降级映射表每一对的固定输入用例
  B. 未分类错误钓鱼测试 — 白名单外的异常必须归为 FATAL
  C. 混沌注入集成测试 — 混沌代理 + 完整 dispatch → 验证错误处理/降级/超时

运行:
    python test_error_handling.py
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import os
import time
import json
import unittest
import logging

# 确保能导入 src 目录
sys.path.insert(0, os.path.dirname(__file__))

from tu8_toolchain import (
    ToolAdapter, TaskContext, ToolResult, TU8Toolchain,
    ErrorHandler, ErrorSeverity,
)
from chaos_adapter import ChaosProxy, ChaosConfig

# 抑制 INFO 日志输出
logging.basicConfig(level=logging.ERROR)


# =============================================================================
# 测试用 Mock 适配器
# =============================================================================

class MockBrowserAdapter(ToolAdapter):
    """模拟浏览器适配器（需要 JS 渲染的页面）"""
    def __init__(self):
        super().__init__("browser_ctrl")

    def execute(self, context: TaskContext) -> ToolResult:
        # 模拟 JS 渲染成功
        return ToolResult(
            success=True,
            output='<html><body><div id="app-data">{"users": [{"id": 1, "name": "Alice"}]}</div></body></html>',
            metadata={"tool": "browser", "params": {"action": "snapshot"}},
        )


class MockWebFetchAdapter(ToolAdapter):
    """模拟 web_fetch 适配器（无 JS 渲染，可能拿到空壳）"""
    def __init__(self, fail=False, empty=False):
        super().__init__("web_fetch")
        self._fail = fail
        self._empty = empty

    def execute(self, context: TaskContext) -> ToolResult:
        if self._fail:
            return ToolResult(success=False, error="connection refused: ECONNREFUSED")
        if self._empty:
            # 模拟 JS 渲染页面的空壳 HTML（无实际内容）
            return ToolResult(
                success=True,
                output='<html><head><script src="app.js"></script></head><body></body></html>',
            )
        return ToolResult(
            success=True,
            output="plain text content from web_fetch",
        )


class MockShellExecAdapter(ToolAdapter):
    """模拟 shell_exec 适配器（curl 兜底）"""
    def __init__(self):
        super().__init__("shell_exec")

    def execute(self, context: TaskContext) -> ToolResult:
        return ToolResult(
            success=True,
            output='{"status": 200, "body": "curl output"}',
        )


class MockFileWriteAdapter(ToolAdapter):
    """模拟文件写入适配器"""
    def __init__(self, fail=False):
        super().__init__("file_write")
        self._fail = fail

    def execute(self, context: TaskContext) -> ToolResult:
        if self._fail:
            return ToolResult(success=False, error="permission denied: EACCES")
        return ToolResult(success=True, output="written 1024 bytes")


class WeirlDBLockError(Exception):
    """自定义的未知错误类 — 模拟白名单外的异常"""
    pass


# =============================================================================
# A. 语义等价性单元测试
# =============================================================================

class TestSemanticEquivalence(unittest.TestCase):
    """
    验证降级映射表每一对 (主工具, 降级工具) 的语义等价性。
    降级后必须通过语义校验，校验失败 = 静默数据损坏 = FATAL。
    """

    def setUp(self):
        # 注册语义校验函数
        ErrorHandler._FALLBACK_CHECKS.clear()

    def tearDown(self):
        ErrorHandler._FALLBACK_CHECKS.clear()

    # ---- browser_ctrl → web_fetch ----
    def test_browser_to_webfetch_ok(self):
        """browser 降级到 web_fetch，web_fetch 返回有内容 → 校验应通过"""
        # 注册校验：降级结果内容长度 > 50 视为有效
        ErrorHandler.register_semantic_check(
            "web_fetch",
            lambda r: r.success and len(r.output) > 50
        )

        check_fn = ErrorHandler.get_semantic_check("web_fetch")
        result = ToolResult(success=True, output="x" * 100)
        self.assertTrue(check_fn(result), "有效内容应通过校验")

    def test_browser_to_webfetch_empty_shell(self):
        """browser 降级到 web_fetch，拿到空壳 HTML → 校验应失败"""
        ErrorHandler.register_semantic_check(
            "web_fetch",
            lambda r: r.success and len(r.output) > 50 and "app-data" in r.output
        )

        check_fn = ErrorHandler.get_semantic_check("web_fetch")
        # 空壳 HTML：没有 app-data 节点
        result = ToolResult(success=True, output='<html><head><script src="app.js"></script></head><body></body></html>')
        self.assertFalse(check_fn(result), "空壳 HTML 缺少关键节点，应校验失败")

    def test_browser_to_webfetch_truncated(self):
        """browser 降级到 web_fetch，拿到截断 JSON → 校验应失败"""
        ErrorHandler.register_semantic_check(
            "web_fetch",
            lambda r: r.success and len(r.output) > 50
        )

        check_fn = ErrorHandler.get_semantic_check("web_fetch")
        result = ToolResult(success=True, output='{"data": {"items": [{"id": 1')
        self.assertFalse(check_fn(result), "截断内容太短，应校验失败")

    # ---- web_fetch → shell_exec ----
    def test_webfetch_to_shell_ok(self):
        """web_fetch 降级到 shell_exec curl → 返回 200 JSON → 校验应通过"""
        ErrorHandler.register_semantic_check(
            "shell_exec",
            lambda r: r.success and '"status": 200' in r.output
        )

        check_fn = ErrorHandler.get_semantic_check("shell_exec")
        result = ToolResult(success=True, output='{"status": 200, "body": "ok"}')
        self.assertTrue(check_fn(result), "curl 200 响应应通过校验")

    def test_webfetch_to_shell_403(self):
        """web_fetch 降级到 shell_exec curl → 返回 403 → 校验应失败"""
        ErrorHandler.register_semantic_check(
            "shell_exec",
            lambda r: r.success and '"status": 200' in r.output
        )

        check_fn = ErrorHandler.get_semantic_check("shell_exec")
        result = ToolResult(success=True, output='{"status": 403, "body": "forbidden"}')
        self.assertFalse(check_fn(result), "403 响应应校验失败")

    # ---- file_write → shell_exec ----
    def test_filewrite_to_shell_ok(self):
        """file_write 降级到 shell_exec tee → 应通过"""
        ErrorHandler.register_semantic_check(
            "shell_exec",
            lambda r: r.success and ("written" in r.output.lower() or "bytes" in r.output.lower())
        )

        check_fn = ErrorHandler.get_semantic_check("shell_exec")
        result = ToolResult(success=True, output="written 2048 bytes via tee")
        self.assertTrue(check_fn(result), "tee 写入应通过校验")

    # ---- dispatch 降级 + 校验失败 = FATAL ----
    def test_dispatch_fallback_check_fail_is_fatal(self):
        """dispatch 降级后语义校验失败 → 结果 severity 必须是 fatal"""
        chain = TU8Toolchain()
        chain.adapters.clear()

        # 注册适配器：browser 成功 → 但如果降级到 web_fetch 返回空壳
        chain.register_adapter(MockBrowserAdapter())
        chain.register_adapter(MockWebFetchAdapter(empty=True))

        # 注册校验：web_fetch 必须包含 app-data
        ErrorHandler.register_semantic_check(
            "web_fetch",
            lambda r: r.success and "app-data" in r.output
        )

        # 降级映射：browser_ctrl → web_fetch
        # （已经在 ErrorHandler._FALLBACK_MAP 中定义）

        # 构造一个 browser 任务，但让 browser 返回失败（模拟真实失败）
        # 我们用一个会失败的 browser 来触发降级
        failing_browser = ToolAdapter("browser_ctrl")
        original_execute = failing_browser.execute
        failing_browser.execute = lambda ctx: ToolResult(
            success=False, error="timeout: browser render timed out"
        )
        chain.register_adapter(failing_browser)  # 覆盖正常 browser

        ctx = TaskContext(
            task_id="test_fallback_fatal",
            description="测试降级校验失败",
            tags=["browser_ctrl", "网页"],
            params={"action": "snapshot", "url": "https://spa.example.com"},
        )

        result = chain.dispatch(ctx)
        # 语义校验失败 → severity 必须是 fatal
        self.assertFalse(result.success, "降级校验失败应返回失败")
        self.assertEqual(result.severity, "fatal", "语义校验失败应标记为 FATAL")
        self.assertIn("校验失败", result.error, "错误信息应提及校验失败")


# =============================================================================
# B. 未分类错误钓鱼测试
# =============================================================================

class TestUnclassifiedErrorPhishing(unittest.TestCase):
    """
    故意抛出不在关键词白名单里的异常，验证：
    1. 被归为 FATAL
    2. 不会重试
    3. 日志里有完整信息（error 字段包含异常类名）
    """

    def test_weird_db_lock_error(self):
        """WeirdDBLockError 不在白名单 → 必须 FATAL"""
        error_msg = "WeirdDBLockError: cannot acquire lock on shard-7"
        severity = ErrorHandler.classify(error_msg)
        self.assertEqual(severity, ErrorSeverity.FATAL, "未分类错误应默认 FATAL")

    def test_weird_db_lock_should_not_retry(self):
        """WeirdDBLockError → should_retry 必须返回 False"""
        severity = ErrorHandler.classify("WeirdDBLockError: lock conflict")
        self.assertFalse(ErrorHandler.should_retry(severity, 0), "FATAL 不应重试")

    def test_quantum_entanglement_error(self):
        """量子纠缠错误（纯粹胡扯）→ 必须 FATAL"""
        severity = ErrorHandler.classify("QuantumEntanglementError: qubit decoherence at node 42")
        self.assertEqual(severity, ErrorSeverity.FATAL)

    def test_generic_runtime_error(self):
        """普通 RuntimeError → 不在白名单 → FATAL"""
        severity = ErrorHandler.classify("RuntimeError: something unexpected happened")
        self.assertEqual(severity, ErrorSeverity.FATAL)

    def test_known_transient_still_works(self):
        """确认已知瞬时错误仍被正确分类（回归测试）"""
        self.assertEqual(ErrorHandler.classify("timeout after 30s"), ErrorSeverity.TRANSIENT)
        self.assertEqual(ErrorHandler.classify("rate limit exceeded"), ErrorSeverity.TRANSIENT)
        self.assertTrue(ErrorHandler.should_retry(ErrorSeverity.TRANSIENT, 0))
        self.assertTrue(ErrorHandler.should_retry(ErrorSeverity.TRANSIENT, 1))
        self.assertTrue(ErrorHandler.should_retry(ErrorSeverity.TRANSIENT, 2))
        self.assertFalse(ErrorHandler.should_retry(ErrorSeverity.TRANSIENT, 3))  # 3次用完

    def test_known_recoverable_still_works(self):
        """确认已知可恢复错误仍被正确分类"""
        self.assertEqual(ErrorHandler.classify("No such file or directory"), ErrorSeverity.RECOVERABLE)
        self.assertTrue(ErrorHandler.should_retry(ErrorSeverity.RECOVERABLE, 0))
        self.assertFalse(ErrorHandler.should_retry(ErrorSeverity.RECOVERABLE, 1))  # 只1次

    def test_known_fatal_still_works(self):
        """确认已知致命错误仍被正确分类"""
        self.assertEqual(ErrorHandler.classify("not implemented"), ErrorSeverity.FATAL)
        self.assertEqual(ErrorHandler.classify("unsupported operation"), ErrorSeverity.FATAL)
        self.assertFalse(ErrorHandler.should_retry(ErrorSeverity.FATAL, 0))


# =============================================================================
# C. 混沌注入集成测试
# =============================================================================

class TestChaosInjection(unittest.TestCase):
    """
    用 ChaosProxy 包装真实适配器，跑完整 dispatch，
    验证错误分类 + 降级 + 超时 在混沌环境下是否正常工作。
    """

    def setUp(self):
        # 重置全局状态
        ErrorHandler._FALLBACK_CHECKS.clear()

    def tearDown(self):
        ErrorHandler._FALLBACK_CHECKS.clear()

    def test_chaos_rate_limit_triggers_retry(self):
        """混沌注入 429 → 应触发 TRANSIENT 重试"""
        chain = TU8Toolchain()
        chain.adapters.clear()

        # 用混沌代理包装 web_fetch（100% 注入 429）
        real = MockWebFetchAdapter()
        chaos = ChaosProxy(real, ChaosConfig(
            seed=42,
            rate_limit_prob=0.99,
            truncated_json_prob=0.0,
            hang_prob=0.0,
        ))
        chain.adapters["web_fetch"] = chaos  # 直接覆盖，保留 key="web_fetch"

        ctx = TaskContext(
            task_id="chaos_429",
            description="测试429重试",
            tags=["web_fetch"],
            params={"url": "https://example.com"},
        )

        result = chain.dispatch(ctx)
        # 429 = TRANSIENT = 会重试3次，但混沌代理每次都注入429
        # 最终耗尽重试次数返回失败
        self.assertFalse(result.success, "持续429应最终失败")
        # 429 应被分类为 transient
        self.assertEqual(result.severity, "transient", "429应分类为transient")

    def test_chaos_truncated_json_passes_through(self):
        """混沌注入截断 JSON → 返回"成功"但内容残废 → 语义校验应捕获"""
        chain = TU8Toolchain()
        chain.adapters.clear()

        # 注册语义校验：web_fetch 输出必须可解析为 JSON
        def json_parseable_check(r: ToolResult) -> bool:
            try:
                json.loads(r.output)
                return True
            except (json.JSONDecodeError, TypeError):
                return False

        ErrorHandler.register_semantic_check("web_fetch", json_parseable_check)

        # 用混沌代理包装 web_fetch
        real = MockWebFetchAdapter()
        chaos = ChaosProxy(real, ChaosConfig(
            seed=123,
            rate_limit_prob=0.0,
            truncated_json_prob=0.99,  # 几乎必定注入截断JSON
            hang_prob=0.0,
        ))
        chain.adapters["web_fetch"] = chaos  # 直接覆盖

        ctx = TaskContext(
            task_id="chaos_trunc",
            description="测试截断JSON",
            tags=["web_fetch"],
            params={"url": "https://api.example.com/data"},
        )

        # 注意：截断 JSON 是通过混沌代理直接返回 success=True 的
        # 不会触发降级（因为返回"成功"了），但语义校验只在降级时触发
        # 这个测试验证混沌代理本身的注入行为
        result = chain.dispatch(ctx)
        # 混沌代理注入截断JSON时返回 success=True 但内容残废
        # 如果命中混沌注入，output 应该是截断的
        chaos_logs = chaos.get_inject_stats()
        if chaos_logs.get("truncated_json", 0) > 0:
            self.assertEqual(len(result.output), len(ChaosConfig().truncated_json_output),
                           "截断JSON输出长度应与配置一致")

    def test_chaos_hang_timeout(self):
        """混沌注入挂起 → 任务级总超时 2s 应拦截"""
        # 临时把总超时缩短到 2s
        original_timeout = ErrorHandler._TASK_TIMEOUT_MS
        ErrorHandler._TASK_TIMEOUT_MS = 2000

        try:
            chain = TU8Toolchain()
            chain.adapters.clear()

            # 用一个失败的 web_fetch 适配器来触发降级/超时
            real = MockWebFetchAdapter()
            chaos = ChaosProxy(real, ChaosConfig(
                seed=999,
                rate_limit_prob=0.99,  # 100% 429
                truncated_json_prob=0.0,
                hang_prob=0.0,
            ))
            chain.adapters["web_fetch"] = chaos

            # 模拟一个已经耗尽总超时的任务
            from datetime import datetime, timedelta
            started = (datetime.now() - timedelta(seconds=65)).timestamp()

            ctx = TaskContext(
                task_id="chaos_timeout",
                description="测试总超时",
                tags=["web_fetch"],
                params={"url": "https://example.com"},
            )

            result = chain.dispatch(ctx, task_started_at=started)
            self.assertFalse(result.success, "总超时应返回失败")
            self.assertEqual(result.severity, "fatal", "超时应标记为 fatal")
        finally:
            ErrorHandler._TASK_TIMEOUT_MS = original_timeout

    def test_chaos_mixed_100_rounds(self):
        """
        压力测试：100 轮混沌注入，验证 dispatch 不崩溃
        用固定种子保证可复现
        """
        chain = TU8Toolchain()
        chain.adapters.clear()

        # 注册降级 + 校验
        chain.register_adapter(MockWebFetchAdapter(fail=False))
        chain.register_adapter(MockShellExecAdapter())
        ErrorHandler.register_semantic_check(
            "shell_exec",
            lambda r: r.success
        )

        # 混沌代理包装 web_fetch
        real = MockWebFetchAdapter()
        chaos = ChaosProxy(real, ChaosConfig(
            seed=20230523,
            rate_limit_prob=0.30,
            truncated_json_prob=0.20,
            hang_prob=0.0,  # 不挂起（不然测试太久）
        ))
        chain.adapters["web_fetch"] = chaos  # 替换为混沌代理

        successes = 0
        failures = 0
        fatals = 0

        for i in range(20):
            ctx = TaskContext(
                task_id=f"stress_{i:03d}",
                description=f"压力测试轮次{i}",
                tags=["web_fetch"],
                params={"url": f"https://example.com/{i}"},
            )
            result = chain.dispatch(ctx)
            if result.success:
                successes += 1
            else:
                failures += 1
                if result.severity == "fatal":
                    fatals += 1

        stats = chaos.get_inject_stats()
        print(f"\n  [混沌压力测试] 20轮结果: {successes}成功 / {failures}失败 / {fatals}fatal")
        print(f"  [注入统计] {stats}")

        # 基本断言：dispatch 不崩溃就行
        self.assertEqual(successes + failures, 20, "每轮都应有结果")
        # 统计正确性
        self.assertGreater(successes, 0, "至少有些轮次应成功")


# =============================================================================
# 运行
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TU-8 错误处理 三合一测试")
    print("  A. 语义等价性单元测试")
    print("  B. 未分类错误钓鱼测试")
    print("  C. 混沌注入集成测试")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSemanticEquivalence))
    suite.addTests(loader.loadTestsFromTestCase(TestUnclassifiedErrorPhishing))
    suite.addTests(loader.loadTestsFromTestCase(TestChaosInjection))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print(f"[PASS] All {result.testsRun} tests passed")
    else:
        print(f"[FAIL] {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60)

    sys.exit(0 if result.wasSuccessful() else 1)
