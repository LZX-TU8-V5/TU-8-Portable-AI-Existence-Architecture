"""inject_pain_monitor.py — 将 CognitivePainMonitor 接入 tu8_agent.py"""
AGENT_PY = r"C:\Users\qq366410837\.qclaw\workspace\src\tu8_agent.py"

with open(AGENT_PY, "r", encoding="utf-8") as f:
    content = f.read()

# 1. 导入（在 IntuitionEngine 后面）
old_import = "        IntuitionEngine = None\n\ntry:\n    from tu8_safety import SafetyCircuit"
new_import = (
    "        IntuitionEngine = None\n\n"
    "try:\n"
    "    from .cognitive_pain_monitor import CognitivePainMonitor\n"
    "except ImportError:\n"
    "    try:\n"
    "        from cognitive_pain_monitor import CognitivePainMonitor\n"
    "    except ImportError:\n"
    "        CognitivePainMonitor = None\n\n"
    "try:\n"
    "    from tu8_safety import SafetyCircuit"
)
assert old_import in content, "旧导入文本不匹配"
content = content.replace(old_import, new_import)
print("[1/3] 导入完成")

# 2. 初始化（在 self._turn_count = 0 前插入）
old_init = (
    "        self._turn_count = 0\n"
    "        self._session_start = time.time()"
)
new_init = (
    "        # === [认知差距监控器] 初始化 ===\n"
    "        self._pain_monitor = None\n"
    "        if CognitivePainMonitor:\n"
    "            try:\n"
    '                pain_log = str(self.workspace / "memory" / "pain_log.jsonl")\n'
    "                self._pain_monitor = CognitivePainMonitor(log_path=pain_log)\n"
    '                logger.info(f"[PainMonitor] 初始化完成, log_path={pain_log}")\n'
    "            except Exception as e:\n"
    '                logger.warning(f"[PainMonitor] 初始化失败: {e}")\n'
    "\n"
    "        self._turn_count = 0\n"
    "        self._session_start = time.time()"
)
assert old_init in content, "旧初始化文本不匹配"
content = content.replace(old_init, new_init)
print("[2/3] 初始化完成")

# 3. 在 respond 返回前监控（找到 return AgentResponse( 行，在其前插入）
# 目标：在生成 response 后检查不确定性
old_return = "        # === 返回结果 ===\n        return AgentResponse("
new_return = (
    "        # === [认知差距监控器] 记录不确定性 ===\n"
    "        if self._pain_monitor:\n"
    "            try:\n"
    "                self._pain_monitor.monitor_uncertainty(\n"
    '                    context=f"Turn #{self._turn_count}: {user_input[:50]}",\n'
    "                    confidence=0.8  # 默认高置信，后续可接收外部评估\n"
    "                )\n"
    "            except Exception as e:\n"
    '                logger.debug(f"[PainMonitor] 记录异常: {e}")\n'
    "\n"
    "        # === 返回结果 ===\n"
    "        return AgentResponse("
)
assert old_return in content, "旧返回文本不匹配"
content = content.replace(old_return, new_return)
print("[3/3] 监控注入完成")

with open(AGENT_PY, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] tu8_agent.py 更新完成")
