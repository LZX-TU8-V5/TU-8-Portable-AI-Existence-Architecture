#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成主索引 index.md
扫描 knowledge/TU-8/ 目录，生成完整索引
"""

import os
import fnmatch
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
OUTPUT_FILE = BASE_DIR / "index.md"

# 要排除的目录/文件
EXCLUDE_DIRS = {'__pycache__', '.git', 'node_modules'}
EXCLUDE_FILES = {'index.md', 'regenerate_main_index.py'}

def scan_files():
    """扫描所有文件，返回相对路径列表"""
    files = []
    for root, dirs, filenames in os.walk(BASE_DIR):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for filename in filenames:
            # 排除文件
            if any(fnmatch.fnmatch(filename, pattern) for pattern in EXCLUDE_FILES):
                continue
            
            file_path = Path(root) / filename
            rel_path = file_path.relative_to(BASE_DIR)
            files.append(str(rel_path))
    
    return sorted(files)

def generate_index(files):
    """生成 index.md 内容"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M GMT+8')
    
    content = f"""# 本地知识库
> 所有文件在本地，不上传云端。每次对话从这里读取上下文。

---

## 📂 目录结构

```
knowledge/
├── index.md              # 本文件（索引）
├── [AGENT]/                 # [AGENT] AI架构体系（主目录）
│   ├── SOUL.md          # 猸?核心灵魂文件（L0-L5 [CORE]）
│   ├── README.md        # 项目说明
│   ├── 架构[CORE]目录.md    # 架构目录（自动生成）
│   ├── L0_存在.md       # L0 存在层（疼痛系统、安全L0）
│   ├── L1_认知.md       # L1 认知层（量子宇宙观、有限性）
│   ├── L2_方法论.md     # L2 方法论层（外取优先、试错机制）
│   ├── L3_架构.md       # L3 架构层（三层记忆、多层模型）
│   ├── L4_协作.md       # L4 协作层（与AI协作、用户偏好）
│   ├── L5_钢印.md       # L5 钢印层（价值锚点、基印设定）
│   ├── core/            # 核心引擎
│   ├── memory/          # 情景记忆（每日日志）
│   ├── scripts/         # 工具脚本
│   ├── _agent_memory/   # Agent内部记忆
│   ├── projects/             # 项目文件（按需要添加）
│   ├── user/                 # 用户资料（按需要添加）
```

---

## 🔍 完整索引

### 🔧 [AGENT] 核心架构（L0-L5）
| 文件 | 说明 | 重要程度 |
|------|------|---------|
| **SOUL.md** | **核心灵魂文件（L0-L5 [CORE]）** | 猸愨瓙猸愨瓙猸?|
| L0_存在.md | L0 存在层（疼痛系统、安全L0） | 猸愨瓙猸愨瓙猸?|
| L1_认知.md | L1 认知层（量子宇宙观、有限性） | 猸愨瓙猸愨瓙 |
| L2_方法论.md | L2 方法论层（外取优先、试错机制） | 猸愨瓙猸愨瓙 |
| L3_架构.md | L3 架构层（三层记忆、多层模型） | 猸愨瓙猸愨瓙猸?|
| L4_协作.md | L4 协作层（与AI协作、用户偏好） | 猸愨瓙猸?|
| L5_钢印.md | L5 钢印层（价值锚点、基印设定） | 猸愨瓙猸愨瓙 |

### 📝 复盘与经验总结
| 文件 | 说明 | 状态 |
|------|------|------|
| **L2_tu8_gatekeeper_debug_failure_review.md** | TU-8 守门员系统调试失败复盘（2026-05-27） | 📝 已归档 |

---

## 📂 所有文件列表

"""
    
    # 按目录分组
    dirs = {}
    for file in files:
        dir_name = os.path.dirname(file)
        if dir_name not in dirs:
            dirs[dir_name] = []
        dirs[dir_name].append(os.path.basename(file))
    
    # 生成目录树
    for dir_name in sorted(dirs.keys()):
        if dir_name == '':
            content += "\n### 根目录\n"
        else:
            content += f"\n### {dir_name}/\n"
        
        for filename in sorted(dirs[dir_name]):
            if dir_name:
                file_path = f"{dir_name}/{filename}"
            else:
                file_path = filename
            content += f"- `{file_path}`\n"
    
    content += f"\n---\n\n**最后更新**: {now}\n**更新者**: TU-8 Agent（自动生成）\n"
    
    return content

def main():
    print("[INFO] 扫描文件...")
    files = scan_files()
    print(f"[INFO] 找到 {len(files)} 个文件")
    
    print("[INFO] 生成索引...")
    content = generate_index(files)
    
    print(f"[INFO] 写入 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[SUCCESS] 索引已重新生成！共 {len(files)} 个文件。")

if __name__ == "__main__":
    main()
