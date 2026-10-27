#!/usr/bin/env python3
"""
手动修复 knowledge/index.md 中的引用
计算从 knowledge/index.md 到新位置的正确相对路径
"""
import os

workspace = r'D:\qq366410837\.qclaw\workspace'
fpath = os.path.join(workspace, 'knowledge', 'index.md')

# 新位置映射
new_paths = {
    'ARCHITECTURE_FULL_SPECTRUM.md': '../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_FULL_SPECTRUM.md',
    'ARCHITECTURE_GAP_ANALYSIS.md': '../knowledge_base/knowledge/01_DESIGN/ARCHITECTURE_GAP_ANALYSIS.md',
    'four_chain_coupling_architecture.md': '../knowledge_base/knowledge/01_DESIGN/four_chain_coupling_architecture.md',
    'BRAIN_VS_TU8_COMPARISON.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/BRAIN_VS_TU8_COMPARISON.md',
    'EXTERNAL_ADVICE_SPACETIME_MEMORY.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/EXTERNAL_ADVICE_SPACETIME_MEMORY.md',
    'module_references.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/module_references.md',
    'P0_强类型契约_手术报告.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/P0_强类型契约_手术报告.md',
    'P1_Token经济学_手术报告.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/P1_Token经济学_手术报告.md',
    'SPACETIME_SENSE_HUMAN_VS_AI.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/SPACETIME_SENSE_HUMAN_VS_AI.md',
    'STARTUP_PIPELINE_DESIGN.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/STARTUP_PIPELINE_DESIGN.md',
    '四链条架构_结构分析.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/四链条架构_结构分析.md',
    '钢印三维张量定义_修改预研.md': '../knowledge_base/knowledge/02_IMPLEMENTATION/钢印三维张量定义_修改预研.md',
    'EXTERNAL_SURGERY_REVIEW.md': '../knowledge_base/knowledge/03_REVIEW/EXTERNAL_SURGERY_REVIEW.md',
    'REVIEW_2026-05-28.md': '../knowledge_base/knowledge/03_REVIEW/REVIEW_2026-05-28.md',
    'OPEN_SOURCE_GUIDANCE.md': '../knowledge_base/knowledge/04_GUIDE/OPEN_SOURCE_GUIDANCE.md',
    'workspace_file_audit_report.md': '../knowledge_base/knowledge/05_ARCHIVE/workspace_file_audit_report.md',
}

print('=== 修复 knowledge/index.md ===\n')

# 读取文件
with open(fpath, encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# 修复引用
fixed_lines = []
for line in lines:
    new_line = line
    for doc_name, new_relpath in new_paths.items():
        if f'docs/{doc_name}' in new_line:
            new_line = new_line.replace(f'docs/{doc_name}', new_relpath)
            print(f'  [FIXED] {doc_name} -> {new_relpath}')
    fixed_lines.append(new_line)

# 写回文件
with open(fpath, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print(f'\n[OK] 已修复 knowledge/index.md')
print('\n验证修复结果...')

# 验证
with open(fpath, encoding='utf-8', errors='ignore') as f:
    content = f.read()

import re
broken = []
for doc_name, new_relpath in new_paths.items():
    if new_relpath in content:
        # 验证路径是否存在
        abs_path = os.path.normpath(os.path.join(os.path.dirname(fpath), new_relpath))
        if not os.path.exists(abs_path):
            broken.append((doc_name, abs_path))

if broken:
    print(f'[FAIL] {len(broken)} 个引用仍损坏:')
    for doc, path in broken:
        print(f'  - {doc}: {path}')
else:
    print('[OK] 所有引用有效！')

print('\n下一步：测试核心功能，确认无误后删除 docs/ 源文件')
