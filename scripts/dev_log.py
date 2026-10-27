#!/usr/bin/env python3
"""
dev_log.py - 开发复盘工作流命令行工具 v2.0

用法:
    python dev_log.py add "模块名：错误描述"           # 添加 [未完成]
    python dev_log.py done <ID>                       # 标记 [已完成]
    python dev_log.py done <ID> --force               # 强制完成（跳过冷静期）
    python dev_log.py rollback <ID>                   # 标记 [已回滚]
    python dev_log.py reflect <ID>                     # 交互式复盘（5 Why）
    python dev_log.py reflect <ID> "根因" "措施"      # 快速复盘
    python dev_log.py list                             # 列出今日条目
    python dev_log.py clean                            # 一键整理碎片文件
    python dev_log.py gc                               # 清理 30 天以上未引用文件
    python dev_log.py status                           # 查看所有状态统计

新增功能 v2.0:
    -冷静期机制：完成后需 24 小时观察期才能归档
    -5 Why 根因分析：强制结构化复盘
    -Git 联动：回滚/归档自动执行 Git 操作
    -知识图谱：复盘自动追加到 L2_方法论/
    -clean 命令：一键整理碎片文件
    -gc 命令：数据湖 TTL 自动清理
"""

import sys
import os
import io
import shutil
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========== 配置 ==========
WORKSPACE = os.environ.get('QCLOW_WORKSPACE', r'D:\qq366410837\.qclaw\workspace')
MEMORY_DIR = Path(WORKSPACE) / 'memory'
ARCHIVE_DIR = Path(WORKSPACE) / '归档'
TEMP_DIR = Path(WORKSPACE) / '临时_整理中转'
KB_DIR = Path(WORKSPACE) / 'knowledge' / 'TU-8'
L2_METHOD_DIR = KB_DIR / 'L2' / '方法论'

# 冷静期（小时）
COOLDOWN_HOURS = 24

# 碎片文件模式
FRAGMENT_PATTERNS = [
    'task-summary_*.md',
    'task-summary-*.md',
    'task_*.md',
    'temp_*.md',
    '*_backup*.md',
    '*absorption*.md',
    '_token*.md',
    '_log*.md',
]


def get_today_file() -> Path:
    """获取当日日志文件"""
    today = datetime.now().strftime('%Y-%m-%d')
    return MEMORY_DIR / f'{today}.md'


def generate_id() -> str:
    """生成唯一ID（时间戳+序号）"""
    return datetime.now().strftime('%Y%m%d%H%M%S')


def run_git(cmd: List[str], cwd: str = None) -> tuple:
    """执行 Git 命令"""
    try:
        result = subprocess.run(
            ['git'] + cmd,
            cwd=cwd or WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, '', 'Git not found'
    except Exception as e:
        return -1, '', str(e)


def check_cooldown(entry_id: str) -> bool:
    """检查是否过了冷静期"""
    md_file = get_today_file()
    if not md_file.exists():
        return True
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找完成时间
    pattern = rf"## \[{entry_id}\] \[已完成\]"
    match = re.search(pattern, content)
    if not match:
        return True
    
    # 提取时间戳（从 ID）
    try:
        completed_time = datetime.strptime(entry_id, '%Y%m%d%H%M%S')
        elapsed = datetime.now() - completed_time
        return elapsed.total_seconds() >= COOLDOWN_HOURS * 3600
    except:
        return True


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
    print(f"💡 后续命令: python dev_log.py done {entry_id}")
    return entry_id


def cmd_done(entry_id: str, force: bool = False):
    """标记为 [已完成]"""
    md_file = get_today_file()
    
    if not md_file.exists():
        print(f"❌ 日志文件不存在: {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查冷静期
    if not force and not check_cooldown(entry_id):
        remaining = COOLDOWN_HOURS
        print(f"⏳ 冷静期检查：条目 {entry_id} 完成未满 {COOLDOWN_HOURS} 小时")
        print(f"💡 强制完成: python dev_log.py done {entry_id} --force")
        return
    
    old_pattern = f"## [{entry_id}] [未完成]"
    new_pattern = f"## [{entry_id}] [已完成]"
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        
        # 追加修复方案模板
        addendum = """
- 修复方案：待补充
- 验证结果：待补充
- 完成时间：{now}
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
    print(f"⏳ 冷静期 {COOLDOWN_HOURS} 小时后可执行 reflect 归档")
    print(f"💡 复盘命令: python dev_log.py reflect {entry_id}")


def cmd_rollback(entry_id: str):
    """标记为 [已回滚]，并触发 Git 回滚"""
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
    
    # Git 联动
    print("\n🔧 Git 联动（可选）：")
    print("1) 跳过（直接回车）")
    print("2) 查看最近提交")
    print("3) 执行 git reset --hard")
    
    choice = input("选择 > ").strip()
    if choice == '2':
        code, out, err = run_git(['log', '--oneline', '-5'])
        print(out or err)
    elif choice == '3':
        commit = input("输入 commit hash（前6位）: ").strip()
        if commit:
            code, out, err = run_git(['reset', '--hard', commit[:6]])
            if code == 0:
                print(f"✅ 已执行 git reset --hard {commit[:6]}")
            else:
                print(f"❌ Git 操作失败: {err}")


def cmd_reflect(entry_id: str, root_cause: str = None, improvement: str = None):
    """添加复盘分析（5 Why 强制结构化）"""
    md_file = get_today_file()
    
    if not md_file.exists():
        print(f"❌ 日志文件不存在: {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if f"## [{entry_id}] [已完成]" not in content:
        print(f"❌ 条目 {entry_id} 状态不是 [已完成]，无法复盘")
        return
    
    # 检查冷静期
    if not check_cooldown(entry_id):
        remaining = COOLDOWN_HOURS
        print(f"⏳ 冷静期检查：完成未满 {COOLDOWN_HOURS} 小时，无法归档")
        print(f"💡 强制归档: python dev_log.py reflect {entry_id} --force")
        return
    
    # 5 Why 交互式输入
    print("\n" + "="*50)
    print("🔍 5 Why 根因分析（强制结构化）")
    print("="*50)
    
    if not root_cause:
        print("\n📌 现象：为什么报错？")
        phenomenon = input("> ").strip()
        
        print("\n📌 直接原因：为什么发生？")
        direct = input("> ").strip()
        
        print("\n📌 根本原因：为什么存在这个漏洞？")
        root = input("> ").strip()
        
        print("\n📌 改进措施：如何避免再次发生？")
        improvement = input("> ").strip()
        
        print("\n📌 知识沉淀：需要更新到哪个知识文件？")
        print("   示例: L2_方法论/上下文管理.md")
        kb_file = input("> ").strip()
        
        root_cause = f"现象: {phenomenon} | 直接原因: {direct} | 根本原因: {root}"
    
    # 插入复盘分析
    addendum = f"""
## 复盘分析
- 根因分析：{root_cause}
- 改进措施：{improvement}
- 归档时间：{datetime.now().strftime('%Y-%m-%d %H:%M GMT+8')}
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
    
    print(f"\n✅ 已添加复盘分析: {entry_id}")
    
    # Git 联动 - 自动 commit
    print("\n🔧 Git 联动：")
    print("1) 跳过（直接回车）")
    print("2) 自动 commit")
    
    choice = input("选择 > ").strip()
    if choice == '2':
        # 提取关键词
        keywords = improvement[:20] if improvement else "bug"
        msg = f"docs: 归档 Bug #{entry_id} - {keywords}"
        
        code, out, err = run_git(['add', '.'])
        if code == 0:
            code, out, err = run_git(['commit', '-m', msg])
            if code == 0:
                print(f"✅ 已提交: {msg}")
            else:
                print(f"❌ Commit 失败: {err}")
        else:
            print(f"❌ Add 失败: {err}")
    
    # 知识图谱 - 双向链接
    if improvement:
        print("\n📚 知识图谱更新：")
        print("1) 跳过（直接回车）")
        print("2) 追加到 L2_方法论/经验沉淀.md")
        
        choice = input("选择 > ").strip()
        if choice == '2':
            kb_target = KB_DIR / 'L2' / '方法论' / '经验沉淀.md'
            kb_target.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件不存在，创建它
            if not kb_target.exists():
                kb_target.write_text("# 经验沉淀\n\n", encoding='utf-8')
            
            # 追加引用
            entry = f"""
### {entry_id} - {datetime.now().strftime('%Y-%m-%d')}
- 根因：{root_cause}
- 改进：{improvement}
- 来源：[memory/{md_file.name}](#{entry_id})
"""
            with open(kb_target, 'a', encoding='utf-8') as f:
                f.write(entry)
            
            print(f"✅ 已追加到: {kb_target}")


def cmd_clean():
    """一键整理碎片文件"""
    print("\n" + "="*50)
    print("🧹 一键整理碎片文件")
    print("="*50)
    
    # 确保目录存在
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {'archived': 0, 'temp': 0, 'skipped': 0}
    
    # 扫描碎片文件
    for pattern in FRAGMENT_PATTERNS:
        for f in Path(WORKSPACE).glob(pattern):
            if f.name in ['SOUL.md', 'MEMORY.md', 'task_log.md']:
                results['skipped'] += 1
                continue
            
            # 决策：归档还是临时
            if 'task-summary' in f.name or '_backup' in f.name or 'SOUL_v' in f.name:
                dest = ARCHIVE_DIR
                results['archived'] += 1
            else:
                dest = TEMP_DIR
                results['temp'] += 1
            
            # 移动
            try:
                shutil.move(str(f), str(dest / f.name))
                print(f"  📦 {f.name} -> {dest.name}/")
            except Exception as e:
                print(f"  ⚠️ 移动失败 {f.name}: {e}")
    
    print(f"\n✅ 整理完成！")
    print(f"   归档: {results['archived']} 个")
    print(f"   临时: {results['temp']} 个")
    print(f"   跳过: {results['skipped']} 个")
    
    # 显示待处理
    print(f"\n📋 归档目录: {ARCHIVE_DIR} ({len(list(ARCHIVE_DIR.glob('*')))} 个)")
    print(f"📋 临时目录: {TEMP_DIR} ({len(list(TEMP_DIR.glob('*')))} 个)")


def cmd_gc():
    """数据湖 TTL 清理 - 清理 30 天以上未引用文件"""
    print("\n" + "="*50)
    print("🗑️ 数据湖 TTL 清理（30 天）")
    print("="*50)
    
    cutoff = datetime.now() - timedelta(days=30)
    deleted = 0
    
    for f in ARCHIVE_DIR.glob('*'):
        if f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                print(f"  🗑️ 删除: {f.name} (最后修改: {mtime.strftime('%Y-%m-%d')})")
                f.unlink()
                deleted += 1
    
    # 清理空目录
    for d in ARCHIVE_DIR.iterdir():
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            print(f"  🧹 删除空目录: {d.name}")
    
    print(f"\n✅ 清理完成！共删除 {deleted} 个文件")


def cmd_status():
    """查看所有状态统计"""
    print("\n" + "="*50)
    print("📊 开发复盘状态统计")
    print("="*50)
    
    stats = {'未完成': 0, '已完成': 0, '已回滚': 0, '已归档': 0}
    
    # 扫描所有 memory/*.md
    for md_file in MEMORY_DIR.glob('*.md'):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(md_file, 'r', encoding='gbk') as f:
                    content = f.read()
            except:
                continue
        
        for status in stats.keys():
            pattern = rf"## \[\d+\] \[{status}\]"
            stats[status] += len(re.findall(pattern, content))
    
    print(f"\n📈 总体统计:")
    for status, count in stats.items():
        emoji = {'未完成': '🔴', '已完成': '🟡', '已回滚': '⚫', '已归档': '🟢'}[status]
        print(f"   {emoji} {status}: {count}")
    
    # 冷静期提示
    print(f"\n⏳ 冷静期: {COOLDOWN_HOURS} 小时")
    
    # 目录状态
    print(f"\n📁 目录状态:")
    print(f"   归档: {len(list(ARCHIVE_DIR.glob('*')))} 个")
    print(f"   临时: {len(list(TEMP_DIR.glob('*')))} 个")


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
    
    # 解析 --force 标志
    force = '--force' in sys.argv
    argv = [a for a in sys.argv if a != '--force']
    
    if cmd == 'add' and len(argv) >= 3:
        desc = ' '.join(argv[2:])
        cmd_add(desc)
    elif cmd == 'done' and len(argv) >= 3:
        cmd_done(argv[2], force)
    elif cmd == 'rollback' and len(argv) >= 3:
        cmd_rollback(argv[2])
    elif cmd == 'reflect' and len(argv) >= 3:
        root = argv[3] if len(argv) >= 4 else None
        improve = argv[4] if len(argv) >= 5 else None
        cmd_reflect(argv[2], root, improve)
    elif cmd == 'clean':
        cmd_clean()
    elif cmd == 'gc':
        cmd_gc()
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'list':
        cmd_list()
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
