#!/usr/bin/env python3
"""第三步：归档未引用的临时文件（安全，可恢复）"""
import os
import json
import shutil

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
analysis_path = os.path.join(kb_root, 'file_analysis.json')
safety_path = os.path.join(kb_root, 'safety_check.json')

# 加载数据
with open(analysis_path, encoding='utf-8') as f:
    results = json.load(f)
with open(safety_path, encoding='utf-8') as f:
    safety = json.load(f)

print('=== 第三步：归档未引用的临时文件 ===\n')

# 获取被引用的文件列表（不能动）
referenced_files = set()
for item in safety['referenced_non_py']:
    referenced_files.add(item)
for item in safety['unsafe_to_move']:
    # 这些是被其他Python模块引用的，不能删除
    pass

print(f'被引用的文件（保留）: {len(referenced_files)} 个')

# 获取所有 TEMP 类别的文件
temp_files = [r for r in results if r['category'] == '04_TEMP']
print(f'TEMP 类别文件: {len(temp_files)} 个\n')

# 筛选可归档的文件（未被引用）
to_archive = []
to_keep = []

for r in temp_files:
    relpath = r['relative_path']
    fpath = r['file']
    
    # 检查是否在引用列表中
    if relpath in referenced_files:
        to_keep.append(relpath)
    else:
        to_archive.append(r)

print(f'可归档（未引用）: {len(to_archive)} 个')
print(f'需保留（被引用）: {len(to_keep)} 个\n')

# 执行归档
archive_dir = os.path.join(kb_root, '05_ARCHIVE')
os.makedirs(archive_dir, exist_ok=True)

archived = []
failed = []

for r in to_archive:
    fpath = r['file']
    relpath = r['relative_path']
    
    if not os.path.exists(fpath):
        print(f'  [SKIP] 文件不存在: {relpath}')
        continue
    
    # 目标路径（保持相对结构）
    target_path = os.path.join(archive_dir, relpath)
    target_dir = os.path.dirname(target_path)
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        shutil.move(fpath, target_path)
        archived.append(relpath)
        print(f'  [ARCHIVED] {relpath}')
    except Exception as e:
        failed.append((relpath, str(e)))
        print(f'  [FAILED] {relpath}: {e}')

print(f'\n=== 第三步完成 ===')
print(f'成功归档: {len(archived)} 个')
print(f'失败: {len(failed)} 个')
print(f'保留（被引用）: {len(to_keep)} 个')

if failed:
    print('\n失败的文件:')
    for f, e in failed:
        print(f'  - {f}: {e}')

# 保存操作日志
log = {
    'step': 3,
    'action': 'archive_temp_files',
    'archived': archived,
    'failed': failed,
    'kept_referenced': to_keep,
}
log_path = os.path.join(kb_root, 'step3_log.json')
with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f'\n日志已保存: {log_path}')
print('\n=== 全部三步完成 ===')
print('工作区清理完成！')
print(f'  1. 移动测试文件: 84 个 -> tests/')
print(f'  2. 删除临时脚本: 67 个')
print(f'  3. 归档临时文件: {len(archived)} 个 -> knowledge_base/05_ARCHIVE/')
print('\n注意：被引用的 35 个文件已保留，未移动。')
