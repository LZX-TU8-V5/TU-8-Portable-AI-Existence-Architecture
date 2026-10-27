#!/usr/bin/env python3
"""
引用安全检查器 - 确保移动文件不会破坏代码
"""
import os
import re
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
analysis_path = os.path.join(kb_root, 'file_analysis.json')

# 加载分析结果
with open(analysis_path, encoding='utf-8') as f:
    results = json.load(f)

print('=== 引用安全检查 ===\n')

# 1. 构建文件引用图
# 收集所有 .py 文件的 import 关系
py_files = {}
for r in results:
    fpath = r['file']
    if fpath.endswith('.py') and os.path.exists(fpath):
        fname = os.path.basename(fpath)
        module_name = os.path.splitext(fname)[0]
        py_files[module_name] = fpath

print(f'找到 {len(py_files)} 个 Python 模块')

# 2. 检查每个模块的引用
import_graph = {}
for module, fpath in py_files.items():
    try:
        with open(fpath, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 查找所有 import 语句
        imports = set()
        
        # from xxx import yyy
        for match in re.finditer(r'from\s+(\w+)\s+import', content):
            imports.add(match.group(1))
        
        # import xxx
        for match in re.finditer(r'^import\s+(\w+)', content, re.MULTILINE):
            imports.add(match.group(1))
        
        # 也检查动态导入或字符串引用
        # exec(f'import {xxx}')
        # __import__('xxx')
        
        import_graph[module] = imports
    except:
        import_graph[module] = set()

# 3. 反向引用：每个模块被谁引用
reverse_graph = {m: set() for m in py_files}
for module, imports in import_graph.items():
    for imp in imports:
        if imp in reverse_graph:
            reverse_graph[imp].add(module)

# 4. 分析计划移动的文件是否安全
print('\n分析 TEMP 类别的 Python 文件...')
temp_py_files = []
for r in results:
    if r['category'] == '04_TEMP' and r['file'].endswith('.py'):
        fname = os.path.basename(r['file'])
        module_name = os.path.splitext(fname)[0]
        temp_py_files.append(module_name)

print(f'TEMP 类别中有 {len(temp_py_files)} 个 Python 模块')

unsafe_to_move = []
safe_to_move = []
for module in temp_py_files:
    if module in reverse_graph and len(reverse_graph[module]) > 0:
        unsafe_to_move.append((module, reverse_graph[module]))
    else:
        safe_to_move.append(module)

print(f'\n安全可移动（无反向引用）: {len(safe_to_move)} 个')
print(f'不安全（有反向引用）: {len(unsafe_to_move)} 个')

if unsafe_to_move:
    print('\n不安全的文件（被其他模块引用）:')
    for module, referers in unsafe_to_move[:10]:
        print(f'  {module}.py <- {referers}')

# 5. 检查非 Python 文件的引用（.ps1, .md 等）
print('\n\n分析非 Python 文件的引用...')
non_py_files = []
for r in results:
    fpath = r['file']
    if r['category'] == '04_TEMP' and not fpath.endswith('.py') and os.path.exists(fpath):
        non_py_files.append(r)

print(f'TEMP 类别中有 {len(non_py_files)} 个非 Python 文件')

# 在这些文件中搜索是否被引用
referenced_files = set()
for r in results:
    fpath = r['file']
    if fpath.endswith('.py') and os.path.exists(fpath):
        try:
            with open(fpath, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # 检查是否引用了 TEMP 文件
            for temp_r in non_py_files:
                temp_fname = os.path.basename(temp_r['file'])
                if temp_fname in content:
                    referenced_files.add(temp_r['relative_path'])
        except:
            pass

if referenced_files:
    print('\n被引用的非 Python 文件（不安全）:')
    for f in referenced_files:
        print(f'  {f}')
else:
    print('\n未找到被引用的非 Python 文件')

# 6. 生成安全移动清单
print('\n\n=== 安全操作清单 ===')
print('\n[安全] 可直接删除（无任何引用）:')
for module in safe_to_move:
    fpath = py_files.get(module, '')
    if fpath:
        print(f'  - {os.path.basename(fpath)}')

print('\n[不安全] 需要先处理引用:')
for module, referers in unsafe_to_move:
    fpath = py_files.get(module, '')
    if fpath:
        print(f'  - {os.path.basename(fpath)} (被引用: {referers})')

# 保存检查结果
check_result = {
    'safe_to_move': safe_to_move,
    'unsafe_to_move': [{'module': m, 'referers': list(r)} for m, r in unsafe_to_move],
    'referenced_non_py': list(referenced_files),
}
check_path = os.path.join(kb_root, 'safety_check.json')
with open(check_path, 'w', encoding='utf-8') as f:
    json.dump(check_result, f, ensure_ascii=False, indent=2)

print(f'\n安全检查报告已保存: {check_path}')
