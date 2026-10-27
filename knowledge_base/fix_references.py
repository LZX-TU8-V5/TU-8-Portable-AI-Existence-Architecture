#!/usr/bin/env python3
"""
修复引用 - 重新计算正确的相对路径
"""
import os
import json

workspace = r'D:\qq366410837\.qclaw\workspace'
kb_root = os.path.join(workspace, 'knowledge_base')

print('=== 修复引用 ===\n')

# 加载更新日志
log_path = os.path.join(kb_root, 'step2_update_log.json')
with open(log_path, encoding='utf-8') as f:
    log = json.load(f)

updated_files = log.get('updated', [])
print(f'需要处理 {len(updated_files)} 个文件\n')

# 新文档的位置映射
new_locations = {
    'ARCHITECTURE_FULL_SPECTRUM.md': 'knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_FULL_SPECTRUM.md',
    'ARCHITECTURE_GAP_ANALYSIS.md': 'knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_GAP_ANALYSIS.md',
    'four_chain_coupling_architecture.md': 'knowledge_base/knowledge/01_DESIGN/four_chain_coupling_architecture.md',
    'BRAIN_VS_TU8_COMPARISON.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/BRAIN_VS_TU8_COMPARISON.md',
    'EXTERNAL_ADVICE_SPACETIME_MEMORY.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/EXTERNAL_ADVICE_SPACETIME_MEMORY.md',
    'module_references.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/module_references.md',
    'P0_强类型契约_手术报告.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/P0_强类型契约_手术报告.md',
    'P1_Token经济学_手术报告.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/P1_Token经济学_手术报告.md',
    'SPACETIME_SENSE_HUMAN_VS_AI.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/SPACETIME_SENSE_HUMAN_VS_AI.md',
    'STARTUP_PIPELINE_DESIGN.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/STARTUP_PIPELINE_DESIGN.md',
    '四链条架构_结构分析.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/四链条架构_结构分析.md',
    '钢印三维张量定义_修改预研.md': 'knowledge_base/knowledge/02_IMPLEMENTATION/钢印三维张量定义_修改预研.md',
    'EXTERNAL_SURGERY_REVIEW.md': 'knowledge_base/knowledge/03_REVIEW/EXTERNAL_SURGERY_REVIEW.md',
    'REVIEW_2026-05-28.md': 'knowledge_base/knowledge/03_REVIEW/REVIEW_2026-05-28.md',
    'OPEN_SOURCE_GUIDANCE.md': 'knowledge_base/knowledge/04_GUIDE/OPEN_SOURCE_GUIDANCE.md',
    'workspace_file_audit_report.md': 'knowledge_base/knowledge/05_ARCHIVE/workspace_file_audit_report.md',
}

fixed = []
failed = []

for relpath in updated_files:
    fpath = os.path.join(workspace, relpath)
    
    if not os.path.exists(fpath):
        print(f'[SKIP] 文件不存在: {relpath}')
        continue
    
    try:
        with open(fpath, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 为每个文档计算正确的相对路径
        new_content = content
        for doc_name, new_relpath in new_locations.items():
            if doc_name in new_content:
                # 计算从当前文件到新位置的正确相对路径
                new_abs_path = os.path.join(workspace, new_relpath)
                correct_relpath = os.path.relpath(new_abs_path, os.path.dirname(fpath))
                correct_relpath = correct_relpath.replace('\\', '/')
                
                # 替换所有引用
                if doc_name in new_content:
                    # 找到包含 doc_name 的引用路径并替换
                    import re
                    # 匹配包含 doc_name 的相对路径
                    pattern = r'[^\s\)\]\}]+' + re.escape(doc_name)
                    # 更简单的方法：直接替换文件名前的路径
                    old_pattern = r'[^\s]+' + re.escape(doc_name)
                    # 直接用正确的相对路径替换
                    new_content = new_content.replace(doc_name, correct_relpath)
        
        # 写回文件
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        fixed.append(relpath)
        print(f'[FIXED] {relpath}')
    
    except Exception as e:
        failed.append((relpath, str(e)))
        print(f'[FAILED] {relpath}: {e}')

print(f'\n修复完成: {len(fixed)} 个文件')
if failed:
    print(f'失败: {len(failed)} 个')

# 验证修复
print('\n验证修复结果...')
import re

verify_passed = 0
verify_failed = 0

for relpath in fixed:
    fpath = os.path.join(workspace, relpath)
    
    with open(fpath, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 检查是否还有错误的引用
    for doc_name, new_relpath in new_locations.items():
        if doc_name in content:
            # 尝试解析引用
            lines = content.split('\n')
            for line in lines:
                if doc_name in line:
                    # 提取引用路径
                    match = re.search(r'[^\s\)\]\}]+\.md', line)
                    if match:
                        ref_path = match.group(0)
                        abs_ref = os.path.normpath(os.path.join(os.path.dirname(fpath), ref_path))
                        if not os.path.exists(abs_ref):
                            print(f'  [BROKEN] {relpath}: {ref_path}')
                            verify_failed += 1
                            break
            else:
                continue
            break
    else:
        verify_passed += 1

print(f'验证通过: {verify_passed} 个')
print(f'验证失败: {verify_failed} 个')

if verify_failed == 0:
    print('\n[OK] 所有引用已修复！')
    print('下一步：重新执行步骤3（测试）')
else:
    print('\n[FAIL] 仍有损坏的引用，需要手动修复')
