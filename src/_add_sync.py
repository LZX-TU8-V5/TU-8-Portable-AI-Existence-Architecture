"""P0-5 v4: surface_tension.record() 后自动同步 lambda_state"""
import pathlib

p = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\src\surface_tension.py')
content = p.read_text(encoding='utf-8', errors='replace')

# 在 record() 末尾 _append_history 之后插入同步块
old = '''    # 更新长期基线（异步，每10次触发一次）
    if state["total_events"] % 10 == 0:
        _refresh_baseline(state)

    # 检测人格模式
    patterns = _detect_pattern(new_vector)'''

new = '''    # 更新长期基线（异步，每10次触发一次）
    if state["total_events"] % 10 == 0:
        _refresh_baseline(state)

    # [P0-5 v4] 同步到 lambda_state（让 orb 立即看到变化）
    try:
        AGENT = pathlib.Path(__file__).parent.parent / "_agent_memory"
        LAMBDA_F = AGENT / "lambda_state.json"
        ST_MAX = 5.0
        ls = json.loads(LAMBDA_F.read_text(encoding="utf-8"))
        ls["anxiety"] = min(new_vector.get("anxiety", 0) / ST_MAX, 1.0)
        ls["anger"] = min(new_vector.get("anger", 0) / ST_MAX, 1.0)
        ls["fear"] = min(new_vector.get("fear", 0) / ST_MAX, 1.0)
        ls["joy"] = min(new_vector.get("joy", 0) / ST_MAX, 1.0)
        ls["curiosity"] = min(new_vector.get("curiosity", 0) / ST_MAX, 1.0)
        ls["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
        LAMBDA_F.write_text(json.dumps(ls, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # 检测人格模式
    patterns = _detect_pattern(new_vector)'''

if old not in content:
    print('ERROR: target not found')
    exit(1)

# Ensure pathlib is imported
if 'import pathlib' not in content:
    # Add to top imports
    content = content.replace('import time\n', 'import time\nimport pathlib\n', 1)

new_content = content.replace(old, new, 1)
p.write_text(new_content, encoding='utf-8', errors='replace')
print('P0-5 v4: record() now syncs to lambda_state automatically')
