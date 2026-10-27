#!/usr/bin/env python3
"""检查代码是否打开引用文件"""
import os
import re

workspace = r'D:\qq366410837\.qclaw\workspace'
tu8_dir = os.path.join(workspace, 'knowledge', 'TU-8')

print('=== 检查代码是否打开引用文件 ===\n')

# 检查 Python 文件中是否有 open() 调用
py_files = []
for root, dirs, files in os.walk(tu8_dir):
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

print(f'扫描 {len(py_files)} 个 Python 文件...\n')

open_calls = {}

for fpath in py_files:
    relpath = os.path.relpath(fpath, tu8_dir)
    
    try:
        with open(fpath, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 查找 open( 调用 (更简单的正则)
        pattern = r'open\(["\'](.*?)["\']'
        matches = re.findall(pattern, content)
        
        if matches:
            open_calls[relpath] = matches
    
    except Exception as e:
        pass

# 显示结果
if open_calls:
    print(f'找到 {len(open_calls)} 个文件有 open() 调用:\n')
    
    for f, calls in list(open_calls.items())[:10]:
        print(f'文件: {f}')
        for call in calls[:5]:
            print(f'  open("{call}")')
        if len(calls) > 5:
            print(f'  ... 还有 {len(calls)-5} 个')
        print()
else:
    print('[OK] 未找到 open() 调用')
    print('这意味着：代码可能不直接打开文件，或者通过其他方式引用')
