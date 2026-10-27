#!/usr/bin/env python3
"""执行文件整理操作 - 根据分析结果移动/归档/删除文件"""
import os
import json
import shutil
from datetime import datetime

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
analysis_path = os.path.join(kb_root, 'file_analysis.json')
index_path = os.path.join(kb_root, 'INDEX.json')

# 加载分析结果
with open(analysis_path, encoding='utf-8') as f:
    results = json.load(f)

# 创建归档目录
archive_root = os.path.join(kb_root, '05_ARCHIVE')
os.makedirs(archive_root, exist_ok=True)

# 统计操作
operations = {
    'ARCHIVE': 0,  # 归档（移到 knowledge_base/05_ARCHIVE/）
    'DELETE': 0,   # 删除（真正删除）
    'MOVE': 0,      # 移动（移到正确目录）
    'KEEP': 0,      # 保留（不操作）
    'SKIP': 0,      # 跳过（错误或不适用）
}

def archive_file(filepath, relpath):
    """归档文件到 knowledge_base/05_ARCHIVE/"""
    # 保持相对路径结构
    archive_path = os.path.join(archive_root, relpath)
    archive_dir = os.path.dirname(archive_path)
    os.makedirs(archive_dir, exist_ok=True)
    
    try:
        shutil.move(filepath, archive_path)
        operations['ARCHIVE'] += 1
        return True, archive_path
    except Exception as e:
        return False, str(e)

def delete_file(filepath):
    """删除文件"""
    try:
        os.remove(filepath)
        operations['DELETE'] += 1
        return True, None
    except Exception as e:
        return False, str(e)

# 按类别处理文件
print('=== 开始文件整理操作 ===\n')

# 1. 处理 TEMP 类别（195个文件）- 归档
temp_files = [r for r in results if r['category'] == '04_TEMP']
print(f'1. 处理 TEMP 文件 ({len(temp_files)} 个)...')

archived = []
for r in temp_files:
    fpath = r['file']
    relpath = r['relative_path']
    
    if not os.path.exists(fpath):
        operations['SKIP'] += 1
        continue
    
    # 判断：小文件(<10KB)且是临时脚本 -> 删除；其他 -> 归档
    size_kb = r['size'] / 1024
    fname = os.path.basename(fpath)
    
    if size_kb < 10 and (fname.startswith('_') or 'temp' in fname.lower()):
        success, msg = delete_file(fpath)
        if success:
            print(f'  DELETED: {relpath}')
        else:
            print(f'  DELETE FAILED: {relpath} - {msg}')
    else:
        success, msg = archive_file(fpath, relpath)
        if success:
            archived.append(relpath)
            print(f'  ARCHIVED: {relpath} -> {msg}')
        else:
            print(f'  ARCHIVE FAILED: {relpath} - {msg}')

print(f'  TEMP 处理完成: 归档 {operations["ARCHIVE"]} 个, 删除 {operations["DELETE"]} 个\n')

# 2. 处理 TEST 类别（84个文件）- 移到 tests/
test_dir = os.path.join(workspace, 'tests')
os.makedirs(test_dir, exist_ok=True)

test_files = [r for r in results if r['category'] == '03_TEST']
print(f'2. 处理 TEST 文件 ({len(test_files)} 个)...')

for r in test_files[:10]:  # 先处理前10个作示例
    fpath = r['file']
    relpath = r['relative_path']
    fname = os.path.basename(fpath)
    
    if not os.path.exists(fpath):
        operations['SKIP'] += 1
        continue
    
    target_path = os.path.join(test_dir, fname)
    
    try:
        shutil.move(fpath, target_path)
        operations['MOVE'] += 1
        print(f'  MOVED: {relpath} -> tests/{fname}')
    except Exception as e:
        print(f'  MOVE FAILED: {relpath} - {e}')

print(f'  TEST 处理示例完成: 移动 {operations["MOVE"]} 个\n')

# 保存操作日志
log = {
    'timestamp': datetime.now().isoformat(),
    'operations': operations,
    'total_files': len(results),
}
log_path = os.path.join(kb_root, 'operation_log.json')
with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print('=== 操作完成 ===')
print(f'归档: {operations["ARCHIVE"]} 个')
print(f'删除: {operations["DELETE"]} 个')
print(f'移动: {operations["MOVE"]} 个')
print(f'跳过: {operations["SKIP"]} 个')
print(f'\n操作日志已保存: {log_path}')
print('\n（示例运行，仅处理部分文件。确认后执行全部...）')
