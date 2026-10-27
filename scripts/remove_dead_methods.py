"""
Phase 6.4: 删除 consciousness_cycle.py 中的 7 个死方法
"""
import os, re

path = os.path.join(os.environ['USERPROFILE'], '.qclaw', 'workspace', 'src', 'consciousness_cycle.py')
backup_path = path + '.phase64.bak'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print(f'原始行数: {len(lines)}')

# 备份
with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'已备份到: {backup_path}')

# 找每个死方法的起止行（0-indexed）
def find_method_block(lines, method_name):
    for i, line in enumerate(lines):
        if re.match(r'\s+def ' + re.escape(method_name) + r'\(', line):
            start = i
            base_indent = len(line) - len(line.lstrip())
            end = i
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped.startswith('def ') or stripped.startswith('class '):
                    indent = len(lines[j]) - len(lines[j].lstrip())
                    if indent <= base_indent:
                        end = j - 1
                        break
                end = j
            return start, end
    return None, None

dead_methods = [
    '_incremental_sync',
    '_step_release',
    '_step_align',
    '_step_compress',
    '_step_freeze',
    '_should_wake_up',
    '_stop_memory_consumer',
]

# 删除（从后往前，避免行号偏移）
ranges_to_delete = []
for name in dead_methods:
    s, e = find_method_block(lines, name)
    if s is not None:
        ranges_to_delete.append((s, e, name))
        print(f'  {name}: L{s+1}-L{e+1} ({e-s+1} lines)')
    else:
        print(f'  {name}: NOT FOUND')

# 从后往前删除
ranges_to_delete.sort(key=lambda x: x[0], reverse=True)
total_deleted = 0
for s, e, name in ranges_to_delete:
    deleted_lines = e - s + 1
    total_deleted += deleted_lines
    del lines[s:e+1]
    print(f'  Deleted {name}: {deleted_lines} lines')

print(f'\n删除总行数: {total_deleted}')
print(f'剩余行数: {len(lines)}')

# 写回
new_content = '\n'.join(lines)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'\n已写入: {path}')

# 验证语法
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('语法验证: PASS')
except py_compile.PyCompileError as e:
    print(f'语法错误: {e}')
