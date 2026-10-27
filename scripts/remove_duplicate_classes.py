# 删除 consciousness_cycle.py 中的重复类定义
# 执行时间：2026-06-27 03:48

import os

file_path = r'C:\Users\qq366410837\.qclaw\workspace\src\consciousness_cycle.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 要删除的类
classes_to_remove = [
    'StateVector',
    'MicroSleepPayload',
    'Seal',
    'Note',
    'NoteCandidate'
]

# 标记要删除的区域
lines = content.split('\n')
new_lines = []
skip_until_next_class = False
removed_count = 0

i = 0
while i < len(lines):
    line = lines[i]

    # 检测 @dataclass 后跟目标类
    if line.strip().startswith('@dataclass'):
        # 检查下一行是否是目标类
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            for cls_name in classes_to_remove:
                if f'class {cls_name}' in next_line or f'class {cls_name}(' in next_line:
                    # 找到目标类，跳过直到下一个 class 或顶级定义
                    skip_until_next_class = True
                    removed_count += 1
                    print(f'标记删除: {cls_name}')
                    break

    if skip_until_next_class:
        # 检查是否到达下一个顶级 class 或 def
        if line.startswith('class ') and not any(f'class {cls}' in line for cls in classes_to_remove):
            skip_until_next_class = False
            new_lines.append(line)
        elif line.startswith('def ') and not line.startswith('    '):
            skip_until_next_class = False
            new_lines.append(line)
        # 否则跳过
    else:
        new_lines.append(line)

    i += 1

# 写回文件
new_content = '\n'.join(new_lines)

# 在"数据结构"注释后添加导入
import_section = '''# =============================================================================
# 数据结构 - 已提取到 cycle_types.py 和 seal_manager.py
# =============================================================================

# 以下类定义已移动到对应模块：
# - StateVector -> cycle_types.StateVector
# - MicroSleepPayload -> cycle_types.MicroSleepPayload
# - Seal -> seal_manager.Seal
# - Note -> cycle_types.CognitiveAnchor
# - NoteCandidate -> cycle_types.AnchorCandidate
#
# 保留向后兼容别名：

from cycle_types import StateVector, MicroSleepPayload, CognitiveAnchor, AnchorCandidate
from seal_manager import Seal

# 向后兼容别名
Note = CognitiveAnchor
NoteCandidate = AnchorCandidate
'''

# 替换原来的"数据结构"注释
new_content = new_content.replace(
    '# =============================================================================\n# 数据结构\n# =============================================================================',
    import_section
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'\n删除了 {removed_count} 个重复类定义')
print('已添加导入语句')
