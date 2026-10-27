#!/usr/bin/env python3
"""第一步：移动测试文件到 tests/ 目录"""
import os
import shutil
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
analysis_path = os.path.join(kb_root, 'file_analysis.json')

# 加载分析结果
with open(analysis_path, encoding='utf-8') as f:
    results = json.load(f)

# 创建 tests 目录
tests_dir = os.path.join(workspace, 'tests')
os.makedirs(tests_dir, exist_ok=True)

print('=== 第一步：移动测试文件 ===\n')

# 获取所有 TEST 类别的文件
test_files = [r for r in results if r['category'] == '03_TEST']
print(f'找到 {len(test_files)} 个测试文件\n')

moved = []
failed = []

for r in test_files:
    fpath = r['file']
    relpath = r['relative_path']
    fname = os.path.basename(fpath)
    
    if not os.path.exists(fpath):
        print(f'  [SKIP] 文件不存在: {relpath}')
        continue
    
    # 目标路径
    target_path = os.path.join(tests_dir, fname)
    
    # 如果目标已存在，添加序号
    if os.path.exists(target_path):
        base, ext = os.path.splitext(fname)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(tests_dir, f'{base}_{counter}{ext}')
            counter += 1
    
    try:
        shutil.move(fpath, target_path)
        moved.append((relpath, os.path.relpath(target_path, workspace)))
        print(f'  [MOVED] {relpath} -> {os.path.relpath(target_path, workspace)}')
    except Exception as e:
        failed.append((relpath, str(e)))
        print(f'  [FAILED] {relpath}: {e}')

print(f'\n=== 第一步完成 ===')
print(f'成功移动: {len(moved)} 个')
print(f'失败: {len(failed)} 个')

if failed:
    print('\n失败的文件:')
    for f, e in failed:
        print(f'  - {f}: {e}')

# 保存操作日志
log = {
    'step': 1,
    'action': 'move_test_files',
    'moved': moved,
    'failed': failed,
}
log_path = os.path.join(kb_root, 'step1_log.json')
with open(log_path, 'w', encoding='utf-8') as f:
    import json
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f'\n日志已保存: {log_path}')
print('\n下一步：确认测试文件移动后，执行第二步（删除临时脚本）')
