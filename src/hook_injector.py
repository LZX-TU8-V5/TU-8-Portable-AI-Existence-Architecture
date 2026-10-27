"""
P0-5 钩子注入器 — hook_injector.py

目的：为 TU-8 建立统一的钩子生命周期管理。
4类钩子 × 4个注入点 = 16个槽位。

钩子类型：
  BEFORE  — 在行为执行前触发（可短路）
  AFTER   — 在行为执行后触发（可追加）
  ON_TENSION  — 紧张/冲突上升时触发（降压）
  ON_CONFIDENCE — 置信度骤降时触发（锚定）

注入点（Hook Points）：
  HP1: alignment_verify()  — 出件前校验（✅已激活：src/alignment_verify.py）
  HP2: shadow_protocol()   — 遗憾提取（✅已激活：src/shadow_protocol.py）
  HP3: dream_check()       — 梦境期（✅已激活：src/tu8_memory.py）
  HP4: heartbeat_check()   — 心跳期（✅已激活：src/hp4_heartbeat.py）

每个槽位存：[(hook_fn, priority, enabled), ...]
priority 越小越先执行；BEFORE 返回 False = 短路主流程。

状态：2026-07-08 HP1/HP2从预置空桩升级为真实功能，HP3/HP4保持激活。

使用：
  from hook_injector import register_hook, run_hooks

  register_hook("HP1", "BEFORE", my_hook, priority=10)
  run_hooks("HP1", "BEFORE", context={...})
"""

import json
import os
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Callable, Any, Optional

# ── 路径 ────────────────────────────────────────────────
WS = Path(os.path.expanduser("~/.qclaw/workspace"))
HOOK_REGISTRY = WS / "secure_vault" / "hook_registry.json"
HOOK_LOG_DIR = WS / "memory" / "hook_logs"
HOOK_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 锁 ─────────────────────────────────────────────────
_hook_lock = threading.Lock()

# ── 时区 ───────────────────────────────────────────────
TZ = timezone(timedelta(hours=8))

# ── 钩子类型 ───────────────────────────────────────────
class HookType:
    BEFORE = "BEFORE"       # 执行前，可短路
    AFTER = "AFTER"         # 执行后，可追加
    ON_TENSION = "ON_TENSION"  # 紧张上升时
    ON_CONFIDENCE = "ON_CONFIDENCE"  # 置信度骤降时


# ── 钩子注册表 ─────────────────────────────────────────
class HookRegistry:
    """
    线程安全的钩子注册表。
    结构：
    {
      "HP1": {
        "BEFORE": [{"fn": "hook_name", "priority": 10, "enabled": true, "meta": {}}],
        "AFTER":  [...],
        "ON_TENSION": [...],
        "ON_CONFIDENCE": [...]
      },
      ...
    }
    """

    def __init__(self):
        self._registry: dict = {}
        self._load()

    def _load(self):
        if HOOK_REGISTRY.exists():
            try:
                with open(HOOK_REGISTRY, "r", encoding="utf-8") as f:
                    self._registry = json.load(f)
            except Exception:
                self._registry = {}
        else:
            self._registry = {}

    def _save(self):
        tmp = HOOK_REGISTRY.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, ensure_ascii=False, indent=2)
            tmp.replace(HOOK_REGISTRY)
        except Exception:
            pass

    def register(
        self,
        hook_point: str,
        hook_type: str,
        hook_name: str,
        fn: Callable,
        priority: int = 100,
        enabled: bool = True,
        meta: dict = None
    ) -> bool:
        """
        注册一个钩子。
        Returns True if registered, False if duplicate name.
        """
        with _hook_lock:
            if hook_point not in self._registry:
                self._registry[hook_point] = {
                    HookType.BEFORE: [],
                    HookType.AFTER: [],
                    HookType.ON_TENSION: [],
                    HookType.ON_CONFIDENCE: [],
                }

            slot = self._registry[hook_point].setdefault(hook_type, [])

            # 防重
            if any(h["hook_name"] == hook_name for h in slot):
                return False

            slot.append({
                "hook_name": hook_name,
                "fn_module": fn.__module__,
                "fn_name": fn.__name__,
                "priority": priority,
                "enabled": enabled,
                "meta": meta or {},
                "registered_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
                "call_count": 0,
                "last_called": None,
            })
            slot.sort(key=lambda x: x["priority"])

            self._save()
            return True

    def unregister(self, hook_point: str, hook_type: str, hook_name: str) -> bool:
        """注销一个钩子"""
        with _hook_lock:
            slot = self._registry.get(hook_point, {}).get(hook_type, [])
            before = len(slot)
            slot[:] = [h for h in slot if h["hook_name"] != hook_name]
            removed = before > len(slot)
            if removed:
                self._save()
            return removed

    def set_enabled(self, hook_point: str, hook_type: str, hook_name: str, enabled: bool):
        """开关一个钩子"""
        with _hook_lock:
            slot = self._registry.get(hook_point, {}).get(hook_type, [])
            for h in slot:
                if h["hook_name"] == hook_name:
                    h["enabled"] = enabled
                    self._save()
                    return True
            return False

    def list_hooks(self, hook_point: str = None, hook_type: str = None) -> dict:
        """列出钩子"""
        with _hook_lock:
            if hook_point:
                return {hook_point: self._registry.get(hook_point, {})}
            return self._registry

    def _record_call(self, hook_point: str, hook_type: str, hook_name: str):
        """记录调用次数"""
        with _hook_lock:
            slot = self._registry.get(hook_point, {}).get(hook_type, [])
            for h in slot:
                if h["hook_name"] == hook_name:
                    h["call_count"] = h.get("call_count", 0) + 1
                    h["last_called"] = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
            self._save()


# 全局注册表
_registry = HookRegistry()


# ── 公共 API ────────────────────────────────────────────
def register_hook(
    hook_point: str,
    hook_type: str,
    hook_name: str,
    fn: Callable,
    priority: int = 100,
    enabled: bool = True,
    meta: dict = None
) -> bool:
    """
    注册钩子。
    hook_point: "HP1" | "HP2" | "HP3" | "HP4"
    hook_type: HookType.BEFORE | HookType.AFTER | HookType.ON_TENSION | HookType.ON_CONFIDENCE
    hook_name: 唯一名称
    fn: 回调函数，签名见各注入点说明
    priority: 越小越先执行
    """
    return _registry.register(hook_point, hook_type, hook_name, fn, priority, enabled, meta)


def unregister_hook(hook_point: str, hook_type: str, hook_name: str) -> bool:
    return _registry.unregister(hook_point, hook_type, hook_name)


def enable_hook(hook_point: str, hook_type: str, hook_name: str):
    _registry.set_enabled(hook_point, hook_type, hook_name, True)


def disable_hook(hook_point: str, hook_type: str, hook_name: str):
    _registry.set_enabled(hook_point, hook_type, hook_name, False)


def list_hooks() -> dict:
    return _registry.list_hooks()


# ── 钩子执行器 ─────────────────────────────────────────
def run_hooks(
    hook_point: str,
    hook_type: str,
    context: dict,
    default_result: Any = None
) -> dict:
    """
    运行指定注入点的指定类型钩子。

    返回结构：
    {
      "short_circuited": bool,      # BEFORE 返回 False
      "results": [(hook_name, result), ...],
      "final": Any,                 # 最终合并结果
      "ran": bool,                  # 是否有钩子被执行
    }

    BEFORE 钩子签名：fn(context: dict) -> (proceed: bool, modified_context: dict)
      - 返回 (False, _) = 短路主流程
      - 返回 (True, ctx) = 继续，ctx 可能被修改

    AFTER 钩子签名：fn(context: dict, result: Any) -> Any
      - 返回值替换 result

    ON_TENSION 钩子签名：fn(context: dict) -> dict
      - 返回降压建议写入 context

    ON_CONFIDENCE 钩子签名：fn(context: dict, old_conf: float, new_conf: float) -> dict
      - 返回锚定建议写入 context
    """
    slot = _registry._registry.get(hook_point, {}).get(hook_type, [])
    enabled_hooks = [h for h in slot if h.get("enabled", True)]

    if not enabled_hooks:
        return {
            "short_circuited": False,
            "results": [],
            "final": default_result,
            "ran": False,
        }

    results = []
    modified_context = dict(context)
    final_result = default_result

    for hook_def in enabled_hooks:
        hook_name = hook_def["hook_name"]
        fn_module = hook_def["fn_module"]
        fn_name = hook_def["fn_name"]

        # 尝试动态导入（允许跨模块调用）
        try:
            import importlib
            mod = importlib.import_module(fn_module)
            fn = getattr(mod, fn_name)
        except Exception as e:
            results.append((hook_name, {"error": f"import failed: {e}"}))
            continue

        try:
            if hook_type == HookType.BEFORE:
                proceed, hook_result = fn(modified_context)
                results.append((hook_name, hook_result))
                if not proceed:
                    _registry._record_call(hook_point, hook_type, hook_name)
                    _log_hook_run(hook_point, hook_type, hook_name, modified_context, False, hook_result)
                    return {
                        "short_circuited": True,
                        "results": results,
                        "final": None,
                        "ran": True,
                    }
                # 合并 context
                if isinstance(hook_result, dict):
                    modified_context.update(hook_result)

            elif hook_type == HookType.AFTER:
                hook_result = fn(modified_context, final_result)
                results.append((hook_name, hook_result))
                final_result = hook_result

            elif hook_type == HookType.ON_TENSION:
                tension_delta = fn(modified_context)
                results.append((hook_name, tension_delta))
                if isinstance(tension_delta, dict):
                    modified_context.update(tension_delta)

            elif hook_type == HookType.ON_CONFIDENCE:
                old_conf = context.get("confidence_before", 0.5)
                new_conf = context.get("confidence_after", 0.5)
                conf_delta = fn(modified_context, old_conf, new_conf)
                results.append((hook_name, conf_delta))
                if isinstance(conf_delta, dict):
                    modified_context.update(conf_delta)

            _registry._record_call(hook_point, hook_type, hook_name)

        except Exception as e:
            results.append((hook_name, {"error": str(e)}))

    _log_hook_run(hook_point, hook_type, None, modified_context, False, final_result)

    return {
        "short_circuited": False,
        "results": results,
        "final": final_result,
        "ran": True,
    }


# ── 日志 ────────────────────────────────────────────────
def _log_hook_run(
    hook_point: str,
    hook_type: str,
    hook_name: str,
    context: dict,
    short_circuited: bool,
    result: Any
):
    """写入钩子运行日志"""
    try:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
        log_path = HOOK_LOG_DIR / f"hook_run_{date_str}.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook_point": hook_point,
            "hook_type": hook_type,
            "hook_name": hook_name,
            "short_circuited": short_circuited,
            "context_keys": list(context.keys()),
            "result_type": type(result).__name__,
            "result_preview": str(result)[:200] if result else None,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── 注入点定义 ─────────────────────────────────────────
# HP1: alignment_verify() — 出件前校验
HP1_ALIGNMENT_VERIFY = "HP1"

# HP2: shadow_protocol() — 遗憾提取
HP2_SHADOW_PROTOCOL = "HP2"

# HP3: dream_check() — 梦境期
HP3_DREAM_CHECK = "HP3"

# HP4: heartbeat_check() — 心跳期
HP4_HEARTBEAT_CHECK = "HP4"

# HP0: tool_failure_probe() — 工具执行后拦截（alignment_verify 前置钩子）
HP0_TOOL_FAILURE = "HP0"


# ── 便捷注册装饰器 ──────────────────────────────────────
def hook(point: str, htype: str, name: str = None, priority: int = 100, meta: dict = None):
    """
    装饰器风格的钩子注册。
    用法：
      @hook("HP1", HookType.BEFORE, "my_check", priority=50)
      def my_check(ctx):
          return True, {"extra_key": "value"}
    """
    def decorator(fn):
        n = name or fn.__name__
        register_hook(point, htype, n, fn, priority, True, meta)
        return fn
    return decorator


# ── CLI ─────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="P0-5 钩子注入器管理")
    parser.add_argument("--list", action="store_true", help="列出所有已注册钩子")
    parser.add_argument("--register", nargs=4, metavar=("HP", "TYPE", "NAME", "MODULE.FN"),
                        help="注册钩子 HP TYPE NAME module.fn")
    parser.add_argument("--unregister", nargs=3, metavar=("HP", "TYPE", "NAME"),
                        help="注销钩子")
    parser.add_argument("--enable", nargs=3, metavar=("HP", "TYPE", "NAME"), help="启用")
    parser.add_argument("--disable", nargs=3, metavar=("HP", "TYPE", "NAME"), help="禁用")
    args = parser.parse_args()

    if args.list:
        import pprint
        pprint.pprint(list_hooks())
    elif args.unregister:
        hp, ht, name = args.unregister
        ok = unregister_hook(hp, ht, name)
        print("OK" if ok else "Not found")
    elif args.enable:
        hp, ht, name = args.enable
        enable_hook(hp, ht, name)
        print("Enabled")
    elif args.disable:
        hp, ht, name = args.disable
        disable_hook(hp, ht, name)
        print("Disabled")
    else:
        parser.print_help()
