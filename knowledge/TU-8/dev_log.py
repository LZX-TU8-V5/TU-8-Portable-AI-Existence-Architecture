#!/usr/bin/env python3
"""
dev_log.py - 开发复盘工作流命令行工具

用法:
    python dev_log.py add "模块名：错误描述"
    python dev_log.py done <ID>
    python dev_log.py rollback <ID>
    python dev_log.py reflect <ID> "根因分析" "改进措施"
    python dev_log.py list
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# 配置
import sys
import os
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='_replace')

WORKSPACE = os.environ.get('QCLOW_WORKSPACE', r'D:\qq366410837\.qclaw\workspace')
MEMORY_DIR = Path(WORKSPACE) / 'memory'


def get_today_file() -> Path:
    """获取当日日志文件"""
    today = datetime.now().strftime('%Y-%m-%d')
    return MEMORY_DIR / f'{today}.md'


def generate_id() -> str:
    """生成唯一ID（时间戳+序号）"""
    return datetime.now().strftime('%Y%m%d%H%M%S')


def cmd_add(description: str):
    """添加 [未完成] 条目"""
    md_file = get_today_file()
    md_file.parent.mkdir(parents=True, exist_ok=True)
    
    entry_id = generate_id()
    now = datetime.now().strftime('%Y-%m-%d %H:%M GMT+8')
    
    content = f"""
## [{entry_id}] [未完成] {description}
- 时间：{now}
- 严重等级：P1
- 关联文件：待补充
- 现场快照：待补充
"""
    
    with open(md_file, 'a', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已添加 [未完成] 条目: {entry_id}")
    print(f"📁 位置: {md_file}")
    return entry_id


def cmd_done(entry_id: str):
    """标记为 [已完成]"""
    md_file = get_today_file()
    
    if not md_file.exists():
        print(f"❌ 日志文件不存在: {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_pattern = f"## [{entry_id}] [未完成]"
    new_pattern = f"## [{entry_id}] [已完成]"
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        
        # 追加修复方案模板
        addendum = """
- 修复方案：待补充
- 验证结果：待补充
"""
        # 找到该条目的位置并插入
        idx = content.find(f"## [{entry_id}]")
        next_double = content.find("\n## ", idx + 1)
        if next_double == -1:
            content += addendum
        else:
            content = content[:next_double] + addendum + content[next_double:]
    elif f"## [{entry_id}] [已回滚]" in content:
        content = content.replace(
            f"## [{entry_id}] [已回滚]",
            f"## [{entry_id}] [已完成]",
            1
        )
    else:
        print(f"❌ 未找到条目: {entry_id}")
        return
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已标记为 [已完成]: {entry_id}")


def cmd_rollback(entry_id: str):
    """标记为 [已回滚]"""
    md_file = get_today_file()
    
    if not md_file.exists():
        print(f"❌ 日志文件不存在: {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换状态
    old_statuses = [
        f"## [{entry_id}] [未完成]",
        f"## [{entry_id}] [已完成]"
    ]
    
    replaced = False
    for old in old_statuses:
        if old in content:
            content = content.replace(old, f"## [{entry_id}] [已回滚]", 1)
            replaced = True
            break
    
    if not replaced:
        print(f"❌ 未找到条目: {entry_id}")
        return
    
    # 追加回滚原因
    print("📝 请输入回滚原因（直接回车跳过）：")
    reason = input("> ").strip()
    if reason:
        addendum = f"\n- 回滚原因：{reason}"
        
        idx = content.find(f"## [{entry_id}] [已回滚]")
        next_double = content.find("\n## ", idx + 1)
        if next_double == -1:
            content += addendum
        else:
            content = content[:next_double] + addendum + content[next_double:]
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已标记为 [已回滚]: {entry_id}")


def cmd_reflect(entry_id: str, root_cause: str = None, improvement: str = None):
    """添加复盘分析"""
    md_file = get_today_file()
    
    if not md_file.exists():
        print(f"❌ 日志文件不存在: {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if f"## [{entry_id}] [已完成]" not in content:
        print(f"❌ 条目 {entry_id} 状态不是 [已完成]，无法复盘")
        return
    
    if not root_cause:
        root_cause = input("📝 根因分析：").strip()
    if not improvement:
        improvement = input("📝 改进措施：").strip()
    
    # 插入复盘分析
    addendum = f"""
## 复盘分析
- 根因分析：{root_cause}
- 改进措施：{improvement}
"""
    
    # 移除旧的 [已完成] 标记，改为 [已归档]
    content = content.replace(
        f"## [{entry_id}] [已完成]",
        f"## [{entry_id}] [已归档]",
        1
    )
    
    idx = content.find(f"## [{entry_id}] [已归档]")
    next_double = content.find("\n## ", idx + 1)
    if next_double == -1:
        content += addendum
    else:
        content = content[:next_double] + addendum + content[next_double:]
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已添加复盘分析: {entry_id}")


def cmd_list():
    """列出今日条目"""
    md_file = get_today_file()
    
    if not md_file.exists():
        print(f"📭 今日暂无日志: {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\n📋 {md_file.name} 条目列表:")
    print("-" * 50)
    
    for line in lines:
        if line.startswith("## ["):
            print(line.strip())
    print("-" * 50)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == 'add' and len(sys.argv) >= 3:
        desc = ' '.join(sys.argv[2:])
        cmd_add(desc)
    elif cmd == 'done' and len(sys.argv) >= 3:
        cmd_done(sys.argv[2])
    elif cmd == 'rollback' and len(sys.argv) >= 3:
        cmd_rollback(sys.argv[2])
    elif cmd == 'reflect' and len(sys.argv) >= 3:
        root = sys.argv[3] if len(sys.argv) >= 4 else None
        improve = sys.argv[4] if len(sys.argv) >= 5 else None
        cmd_reflect(sys.argv[2], root, improve)
    elif cmd == 'list':
        cmd_list()
    else:
        print(__doc__)


if __name__ == '__main__':
    main()