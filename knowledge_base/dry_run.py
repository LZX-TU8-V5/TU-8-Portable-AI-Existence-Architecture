#!/usr/bin/env python3
"""干运行 - 显示文件整理操作但不实际执行"""
import os
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
analysis_path = os.path.join(kb_root, 'file_analysis.json')

# 加载分析结果
with open(analysis_path, encoding='utf-8') as f:
    results = json.load(f)

print('=== 文件整理干运行报告 ===\n')

# 统计各类操作
plan = {
    'ARCHIVE_SMALL': [],  # 归档小文件
    'ARCHIVE_LARGE': [],  # 归档大文件
    'DELETE': [],         # 删除临时文件
    'MOVE_TEST': [],      # 移动测试文件
    'KEEP_CORE': [],     # 保留核心文件
    'SKIP_MISSING': [],  # 跳过不存在的文件
}

for r in results:
    fpath = r['file']
    relpath = r['relative_path']
    size_kb = r['size'] / 1024
    cat = r['category']
    
    if not os.path.exists(fpath):
        plan['SKIP_MISSING'].append(relpath)
        continue
    
    if cat == '04_TEMP':
        if size_kb < 10 and (os.path.basename(fpath).startswith('_') or 'temp' in fpath.lower()):
            plan['DELETE'].append(relpath)
        else:
            plan['ARCHIVE_LARGE' if size_kb >= 100 else 'ARCHIVE_SMALL'].append(relpath)
    elif cat == '03_TEST':
        plan['MOVE_TEST'].append(relpath)
    elif cat == '00_CORE':
        plan['KEEP_CORE'].append(relpath)

# 输出报告
print('1. 将删除的临时文件（小文件）:')
for f in plan['DELETE'][:20]:
    print(f'   - {f}')
if len(plan['DELETE']) > 20:
    print(f'   ... 还有 {len(plan["DELETE"])-20} 个')

print(f'\n2. 将归档的临时文件:')
print(f'   - 小文件 (<100KB): {len(plan["ARCHIVE_SMALL"])} 个')
print(f'   - 大文件 (>=100KB): {len(plan["ARCHIVE_LARGE"])} 个')

print(f'\n3. 将移动的测试文件: {len(plan["MOVE_TEST"])} 个')
for f in plan['MOVE_TEST'][:10]:
    print(f'   - {f}')

print(f'\n4. 将保留的核心文件: {len(plan["KEEP_CORE"])} 个')

print(f'\n5. 跳过的缺失文件: {len(plan["SKIP_MISSING"])} 个')

print('\n=== 操作统计 ===')
print(f'删除: {len(plan["DELETE"])} 个')
print(f'归档: {len(plan["ARCHIVE_SMALL"]) + len(plan["ARCHIVE_LARGE"])} 个')
print(f'移动: {len(plan["MOVE_TEST"])} 个')
print(f'保留: {len(plan["KEEP_CORE"])} 个')
print(f'跳过: {len(plan["SKIP_MISSING"])} 个')
print(f'总计: {len(results)} 个')

print('\n（这是干运行，未实际执行操作）')
print('确认后执行 file_operations.py 进行实际操作...')
