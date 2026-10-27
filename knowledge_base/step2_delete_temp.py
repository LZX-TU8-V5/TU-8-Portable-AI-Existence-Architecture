#!/usr/bin/env python3
"""第二步：删除安全的临时脚本（无引用）"""
import os
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')
safety_path = os.path.join(kb_root, 'safety_check.json')

# 加载安全检查结果
with open(safety_path, encoding='utf-8') as f:
    safety = json.load(f)

print('=== 第二步：删除安全的临时脚本 ===\n')

# 获取安全可删除的文件列表
safe_modules = safety['safe_to_move']
print(f'安全检查通过：{len(safe_modules)} 个模块可安全删除\n')

deleted = []
failed = []

for module in safe_modules:
    # 查找对应的文件
    found = False
    for root, dirs, files in os.walk(workspace):
        # 跳过知识库目录
        if 'knowledge_base' in root:
            continue
        for fname in files:
            if fname == f'{module}.py':
                fpath = os.path.join(root, fname)
                try:
                    os.remove(fpath)
                    relpath = os.path.relpath(fpath, workspace)
                    deleted.append(relpath)
                    print(f'  [DELETED] {relpath}')
                    found = True
                    break
                except Exception as e:
                    failed.append((relpath, str(e)))
                    print(f'  [FAILED] {relpath}: {e}')
                    found = True
                    break
        if found:
            break
    
    if not found:
        print(f'  [SKIP] 未找到模块: {module}')

print(f'\n=== 第二步完成 ===')
print(f'成功删除: {len(deleted)} 个')
print(f'失败: {len(failed)} 个')

if failed:
    print('\n失败的文件:')
    for f, e in failed:
        print(f'  - {f}: {e}')

# 保存操作日志
log = {
    'step': 2,
    'action': 'delete_temp_scripts',
    'deleted': deleted,
    'failed': failed,
    'skipped_not_found': len(safe_modules) - len(deleted) - len(failed),
}
log_path = os.path.join(kb_root, 'step2_log.json')
with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f'\n日志已保存: {log_path}')
print('\n下一步：执行第三步（归档未引用的临时文件）')
