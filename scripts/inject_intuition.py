"""inject_intuition.py — 将直觉引擎结果注入 tu8_agent.py"""
import os

AGENT_PY = r"C:\Users\qq366410837\.qclaw\workspace\src\tu8_agent.py"
INJECT_AFTER = '[调度链] 穿皮完成'
INJECT_CODE = '''        
        # === [直觉引擎结果] 注入上下文 ===
        if intuition_result:
            intuition_hint = '[直觉预判: %s]' % intuition_result.response[:80]
            if assembly and hasattr(assembly, 'context_items'):
                assembly.context_items.insert(0, {
                    'role': 'system',
                    'content': intuition_hint,
                    'metadata': {'source': 'intuition', 'confidence': intuition_result.confidence}
                })
            logger.info('[Intuition] 预判已注入: %s' % intuition_hint[:50])
'''

with open(AGENT_PY, 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find(INJECT_AFTER)
if idx >= 0:
    # 找到该行末尾的换行符
    line_end = content.find('\n', idx)
    new_content = content[:line_end+1] + INJECT_CODE + content[line_end+1:]
    with open(AGENT_PY, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('[OK] 直觉引擎注入完成')
else:
    print('[WARN] 未找到目标位置，跳过')
