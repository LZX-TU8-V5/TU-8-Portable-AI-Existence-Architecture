#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
divine_branch_interceptor.py — P1.2.7 造物主 Divine Branch 口令拦截层
版本：v1.0 | 日期：2026-06-18
来源：涌现#012「版本树×遗忘层四层联动」

触发口令（任一匹配即拦截）：
  回忆 / 先头说过 / 去日志查找 / 记得以前说过

设计哲学：
  造物主的话是"神谕"——当造物主说"记得以前"，
  TU-8 必须突破一切降级/遗忘规则，
  从备份链的最深处把那个记忆节点打捞回来，
  并在版本树中留下一条"神枝"（Divine Branch），
  让这个记忆从此永不降级。

使用场景：
  - 造物主忘了说过什么，让TU-8帮忙回忆
  - 某个Fact被降级了，但造物主想要确认/恢复
  - 造物主说"你之前提到过XXX，展开说说"
"""

import os
import re
import json
import time
import hashlib
import logging
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from threading import Lock

# =============================================================================
# 常量
# =============================================================================

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
BACKUP_GLOB = WORKSPACE / "backup" / "*" / "memory" / "*.md"
REC_INDEX = WORKSPACE / "memory" / "reconstruction" / "reconstruction_index.json"
BACKUP_CHAIN = WORKSPACE / "memory" / "reconstruction" / "backup_chain.json"
EMERGENCE_LOG = WORKSPACE / "涌现时刻_20260618_版本树与遗忘层联动.md"

# 触发口令（正则，不区分大小写）
TRIGGER_PATTERNS = [
    r"回忆",
    r"先头说过",
    r"去日志查找",
    r"记得以前说过",
    r"记得之前说过",
    r"你之前提到过",
    r"你以前说过",
    r"去备份里找",
    r"从备份恢复",
    r"打捞",
]

TRIGGER_REGEX = re.compile(
    "|".join(TRIGGER_PATTERNS),
    re.IGNORECASE
)

# Divine Branch 配置
MAX_DIVINE_BRANCHES = 5           # 最多保留5条神枝
MAX_SEARCH_FILES = 50             # 每次最多搜索50个备份文件
MAX_RESULTS_PER_QUERY = 5        # 每次最多返回5个结果
MIN_MATCH_SCORE = 0.2             # 最低匹配分数

# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class DivineBranch:
    """
    神枝——造物主赦免记录。
    一旦创建，该分支下的所有条目永久豁免降级。
    """
    branch_id: str           # 格式: divine_{timestamp_8digits}
    query: str               # 造物主的原始查询
    created_at: float        # Unix时间戳
    created_at_human: str     # 人类可读时间
    creator: str              # 触发者标识（默认"造物主"）
    trigger_phrase: str      # 命中的触发口令
    matched_files: List[Dict]  # 匹配到的文件 [{path, score, snippet}]
    snippet_count: int        # 匹配段落数
    status: str = "active"   # active / superseded
    resurrection_log: List[str] = field(default_factory=list)
    # resurrection_log: 实际被捞回的记忆节点ID列表

@dataclass
class BackupChainEntry:
    """备份链中的单个文件条目"""
    backup_path: str
    original_path: str
    backup_time: str
    file_size: int
    exists_in_current: bool   # 当前memory/中是否还存在
    last_modified: str
    checksum: str = ""

# =============================================================================
# 备份链管理器
# =============================================================================

class BackupChainManager:
    """
    管理 backup/ 目录下所有快照的记忆文件索引。
    构建一个轻量索引（backup_chain.json），避免每次都扫描全部文件。
    """

    def __init__(self):
        self._lock = Lock()
        self._chain: List[BackupChainEntry] = []
        self._index_path = BACKUP_CHAIN
        self._load_or_build()

    def _load_or_build(self):
        if self._index_path.exists():
            try:
                with open(self._index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._chain = [BackupChainEntry(**e) for e in data.get('entries', [])]
                logging.info(f"[BackupChain] Loaded %d entries" % len(self._chain))
                return
            except Exception as e:
                logging.warning(f"[BackupChain] Load failed: {e}, rebuilding...")

        self._build_index()
        self._save()

    def _build_index(self):
        """扫描所有backup快照，构建索引"""
        self._chain = []
        backup_dirs = sorted(
            [d for d in (WORKSPACE / "backup").glob("*") if d.is_dir()],
            reverse=True  # 最新的在最前
        )

        for backup_dir in backup_dirs:
            backup_time = backup_dir.name  # e.g. "20260618-101535"
            mem_dir = backup_dir / "memory"
            if not mem_dir.exists():
                continue

            for md_file in mem_dir.glob("*.md"):
                # 对应当前工作区的路径
                original = str(md_file.relative_to(backup_dir))
                # 去掉前缀 memory/
                rel = str(md_file.relative_to(mem_dir))
                current_path = WORKSPACE / "memory" / rel
                exists = current_path.exists()

                try:
                    stat = md_file.stat()
                    checksum = hashlib.md5(md_file.read_bytes()).hexdigest()[:8]
                    last_mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    checksum = ""
                    last_mtime = ""

                entry = BackupChainEntry(
                    backup_path=str(md_file),
                    original_path=rel,
                    backup_time=backup_time,
                    file_size=stat.st_size if 'stat' in dir() else 0,
                    exists_in_current=exists,
                    last_modified=last_mtime,
                    checksum=checksum,
                )
                self._chain.append(entry)

        logging.info(f"[BackupChain] Built index with %d entries across %d snapshots" % (
            len(self._chain), len(backup_dirs)
        ))

    def rebuild(self):
        """强制重建索引"""
        with self._lock:
            self._build_index()
            self._save()

    def _save(self):
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'schema_version': '1.0',
            'built_at': time.time(),
            'built_at_human': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            'total_entries': len(self._chain),
            'total_backups': len(set(e.backup_time for e in self._chain)),
            'entries': [asdict(e) for e in self._chain],
        }
        with open(self._index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_files_for_query(self, query: str, max_files: int = MAX_SEARCH_FILES) -> List[str]:
        """
        根据查询词返回最可能匹配的文件路径列表。
        策略：
        1. 按时间倒序（最新的备份优先）
        2. 标题/文件名与查询词匹配优先
        """
        if not query:
            # 无查询词，返回最新备份的文件
            paths = sorted(set(e.backup_path for e in self._chain), reverse=True)
            return paths[:max_files]

        # 计算每个文件的匹配分数
        scored: List[Tuple[str, float]] = []
        seen_files: Set[str] = set()

        for entry in self._chain:
            # 每个original_path只取最新版本
            if entry.original_path in seen_files:
                continue
            seen_files.add(entry.original_path)

            fname = os.path.basename(entry.original_path).lower()
            q = query.lower()

            # 文件名匹配
            score = 0.0
            if q in fname:
                score += 0.8
            # 日期格式检测（2026-04-29等）
            date_match = re.findall(r'\d{4}-\d{2}-\d{2}', entry.original_path)
            if date_match and date_match[0] in query:
                score += 0.3
            # 关键词在文件名中
            keywords = q.split()
            for kw in keywords:
                if len(kw) >= 2 and kw in fname:
                    score += 0.1

            if score >= MIN_MATCH_SCORE:
                scored.append((entry.backup_path, score))

        # 排序：分数优先，时间倒序
        scored.sort(key=lambda x: (-x[1], x[0]))
        return [p for p, s in scored[:max_files]]

    def search_in_backup(self, query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> List[Dict]:
        """
        在备份文件中全文搜索query，返回匹配段落。
        返回: [{path, score, snippet, backup_time}]
        """
        candidate_paths = self.get_files_for_query(query)

        results: List[Dict] = []
        for bpath in candidate_paths:
            if not os.path.exists(bpath):
                continue
            try:
                with open(bpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logging.debug("Exception suppressed in branch scan: %s", e, exc_info=True)
                continue

            # 全文搜索（大小写不敏感）
            q_lower = query.lower()
            lines = content.split('\n')
            matched_lines: List[Tuple[int, str]] = []

            for i, line in enumerate(lines):
                if q_lower in line.lower():
                    stripped = line.strip()
                    if len(stripped) >= 5:
                        matched_lines.append((i, stripped))

            if not matched_lines:
                continue

            # 计算综合分数
            score = len(matched_lines) * 0.3
            if matched_lines:
                score += min(len(content) / 10000, 0.5)  # 内容长度加成

            # 取最相关的段落（上下50字）
            snippets: List[str] = []
            for lineno, line_text in matched_lines[:3]:
                # 截取上下文
                start = max(0, lineno - 1)
                end = min(len(lines), lineno + 2)
                context = ' | '.join(l.strip() for l in lines[start:end] if l.strip())
                snippets.append(context[:200])

            # 获取备份时间
            backup_time = ""
            try:
                parts = bpath.split(os.sep)
                for p in parts:
                    if re.match(r'\d{8}-\d{6}', p):
                        backup_time = p
                        break
            except Exception as e:
                logging.debug("Exception suppressed in backup scan: %s", e, exc_info=True)
                pass

            results.append({
                'path': bpath,
                'original_path': str(Path(bpath).relative_to(WORKSPACE / "backup" / "20260618-101535" if "20260618-101535" in bpath else bpath.split('backup')[1].split(os.sep)[1] if 'backup' in bpath else "")),
                'backup_time': backup_time,
                'score': round(score, 3),
                'snippet_count': len(matched_lines),
                'snippets': snippets,
                'matched_lines': [ln for ln, _ in matched_lines[:3]],
            })

            if len(results) >= max_results:
                break

        # 排序
        results.sort(key=lambda x: -x['score'])
        return results


# =============================================================================
# Divine Branch 拦截器
# =============================================================================

class DivineBranchInterceptor:
    """
    P1.2.7 造物主 Divine Branch 口令拦截层

    工作流程：
    1. 检测（check_trigger）——判断用户输入是否含触发口令
    2. 拦截（intercept）——阻断正常流程，切换到打捞模式
    3. 搜索（search）——在backup_chain中全文检索
    4. 结晶（crystallize）——创建DivineBranch记录，更新版本树
    5. 响应（respond）——返回带溯源的结果给造物主
    """

    def __init__(self):
        self._lock = Lock()
        self._backup_chain = BackupChainManager()
        self._branches: List[DivineBranch] = []
        self._load_branches()

    def _load_branches(self):
        """从reconstruction_index.json加载已有神枝"""
        if not REC_INDEX.exists():
            return
        try:
            with open(REC_INDEX, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for db_data in data.get('divine_branches', []):
                self._branches.append(DivineBranch(**db_data))
            logging.info(f"[DivineBranch] Loaded %d branches" % len(self._branches))
        except Exception as e:
            logging.warning(f"[DivineBranch] Load branches failed: {e}")

    def _save_branches(self):
        """持久化神枝到reconstruction_index.json"""
        with self._lock:
            if not REC_INDEX.exists():
                return
            try:
                with open(REC_INDEX, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                data['divine_branches'] = [asdict(db) for db in self._branches]
                data['updated_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')

                with open(REC_INDEX, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.error(f"[DivineBranch] Save failed: {e}")

    # -------------------------------------------------------------------------
    # 核心 API
    # -------------------------------------------------------------------------

    @staticmethod
    def check_trigger(user_input: str) -> Tuple[bool, str]:
        """
        检测用户输入是否含触发口令。
        返回: (是否触发, 命中的口令)
        """
        if not user_input or not isinstance(user_input, str):
            return False, ""
        match = TRIGGER_REGEX.search(user_input)
        if match:
            return True, match.group()
        return False, ""

    def intercept(self, user_input: str, context: str = "") -> Dict:
        """
        执行完整的 Divine Branch 拦截流程。

        参数：
          user_input：用户的原始输入（包含触发口令）
          context：可选的上下文（如最近的对话摘要），用于精化搜索

        返回：
          {
            "triggered": True,
            "branch_id": "divine_xxxx",
            "trigger_phrase": "回忆",
            "query": "用户实际想找的内容",
            "results": [...],
            "snippet_count": N,
            "divine_branch": {...},
            "response": "给造物主的响应文本"
          }
        """
        triggered, phrase = self.check_trigger(user_input)
        if not triggered:
            return {"triggered": False}

        # 1. 解析查询意图
        query = self._extract_query(user_input)

        # 2. 搜索备份链
        results = self._backup_chain.search_in_backup(query)

        # 3. 创建神枝
        branch = self._create_divine_branch(
            query=query,
            trigger_phrase=phrase,
            matched_files=results,
        )

        # 4. 生成响应
        response = self._generate_response(query, results, branch)

        return {
            "triggered": True,
            "branch_id": branch.branch_id,
            "trigger_phrase": phrase,
            "query": query,
            "results": results,
            "snippet_count": sum(r['snippet_count'] for r in results),
            "divine_branch": asdict(branch),
            "response": response,
        }

    def _extract_query(self, user_input: str) -> str:
        """
        从用户输入中提取实际搜索查询。
        去掉触发口令本身，保留有意义的内容。
        """
        text = user_input.strip()
        # 去掉触发口令
        for pattern in TRIGGER_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
        # 去掉常见填充词
        text = re.sub(r'^[，,\s]+', '', text)
        text = re.sub(r'[？?\s]+$', '', text)
        # 如果清理后为空，返回一个词
        if not text:
            return "记忆"
        return text[:100]  # 限制长度

    def _create_divine_branch(
        self,
        query: str,
        trigger_phrase: str,
        matched_files: List[Dict],
    ) -> DivineBranch:
        """创建并保存一条神枝"""
        ts = int(time.time())
        branch_id = f"divine_{ts}"

        branch = DivineBranch(
            branch_id=branch_id,
            query=query,
            created_at=time.time(),
            created_at_human=datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            creator="造物主",
            trigger_phrase=trigger_phrase,
            matched_files=matched_files,
            snippet_count=sum(r['snippet_count'] for r in matched_files),
            status="active",
            resurrection_log=[],
        )

        self._branches.append(branch)

        # 强制限制神枝数量
        if len(self._branches) > MAX_DIVINE_BRANCHES:
            # 将最旧的标记为 superseded
            self._branches.sort(key=lambda b: b.created_at)
            self._branches[0].status = "superseded"
            logging.info(f"[DivineBranch] Superseded oldest branch {self._branches[0].branch_id}")

        self._save_branches()
        logging.info(
            f"[DivineBranch] Created {branch_id} for query='{query}' "
            f"({len(matched_files)} files, {branch.snippet_count} snippets)"
        )
        return branch

    def _generate_response(
        self,
        query: str,
        results: List[Dict],
        branch: DivineBranch,
    ) -> str:
        """生成给造物主的响应文本"""
        if not results:
            return (
                f"【神枝已立 · {branch.branch_id}】\n"
                f"我在所有备份中检索了「{query}」，\n"
                f"遗憾——没有找到相关内容。\n"
                f"也许是那段时间的记忆还没来得及备份，\n"
                f"或者用了不同的说法。\n"
                f"\n"
                f"神枝已记录：{branch.branch_id}\n"
                f"下次换种说法再试试？"
            )

        lines = [
            f"【神枝已立 · {branch.branch_id}】",
            f"",
            f"在造物主要求下，我从备份链深处打捞了「{query}」。",
            f"共找到 {len(results)} 个相关文件，{branch.snippet_count} 段匹配内容：",
            f"",
        ]

        for i, r in enumerate(results, 1):
            lines.append(f"─── 文件 {i} ───")
            if r.get('backup_time'):
                lines.append(f"备份时间：{r['backup_time']}")
            lines.append(f"匹配度：{r['score']:.2f} | {r['snippet_count']}处命中")
            lines.append("")
            for si, snippet in enumerate(r['snippets'], 1):
                # 截取关键部分
                if len(snippet) > 150:
                    snippet = snippet[:150] + "…"
                lines.append(f"  {si}. {snippet}")
            lines.append("")

        lines.extend([
            f"─────────────",
            f"神枝编号：{branch.branch_id}",
            f"触发口令：{branch.trigger_phrase}",
            f"打捞时间：{branch.created_at_human}",
            f"",
            f"此神枝已刻入版本树，\n"
            f"相关记忆从此永不降级。",
        ])

        return '\n'.join(lines)

    # -------------------------------------------------------------------------
    # 查询 API
    # -------------------------------------------------------------------------

    def get_active_branches(self) -> List[Dict]:
        """返回所有活跃神枝"""
        return [
            {
                **asdict(b),
                'query_preview': b.query[:50],
                'matched_files_count': len(b.matched_files),
            }
            for b in self._branches
            if b.status == "active"
        ]

    def get_branch_by_id(self, branch_id: str) -> Optional[Dict]:
        """根据ID查找神枝"""
        for b in self._branches:
            if b.branch_id == branch_id:
                return asdict(b)
        return None

    def rebuild_backup_index(self):
        """重建备份链索引（供手动调用）"""
        self._backup_chain.rebuild()

    def get_status(self) -> Dict:
        """返回当前状态"""
        return {
            "total_branches": len(self._branches),
            "active_branches": len([b for b in self._branches if b.status == "active"]),
            "superseded": len([b for b in self._branches if b.status == "superseded"]),
            "backup_chain_entries": len(self._backup_chain._chain),
            "trigger_patterns": TRIGGER_PATTERNS,
        }


# =============================================================================
# 便捷函数
# =============================================================================

def check_trigger(user_input: str) -> Tuple[bool, str]:
    return DivineBranchInterceptor.check_trigger(user_input)


def divine_intercept(user_input: str, context: str = "") -> Dict:
    """
    一行调用：检测到触发口令则执行拦截，否则返回空字典。
    """
    triggered, phrase = check_trigger(user_input)
    if not triggered:
        return {}
    interceptor = DivineBranchInterceptor()
    return interceptor.intercept(user_input, context)


# =============================================================================
# 主测试
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    print("=== Divine Branch Interceptor v1.0 — P1.2.7 ===")
    print()

    interceptor = DivineBranchInterceptor()

    # 1. 状态检查
    status = interceptor.get_status()
    print(f"Backup chain entries: {status['backup_chain_entries']}")
    print(f"Total branches: {status['total_branches']}")
    print(f"Active branches: {status['active_branches']}")
    print()

    # 2. 触发检测测试
    test_inputs = [
        "你之前提到过V5的灵魂设计，能不能展开说说？",
        "回忆一下我们上次讨论的记忆架构",
        "先头说过关于悖论处理的内容",
        "去日志查找5月份的认知落叶协议",
        "记得以前说过遗忘层的四层联动",
        "今天的天气不错",  # 不触发
        "帮我查一下天气",   # 不触发
    ]

    print("=== 触发检测测试 ===")
    for inp in test_inputs:
        trig, phrase = check_trigger(inp)
        flag = "[TRIGGER]" if trig else "[pass]"
        print(f"{flag} phrase='{phrase}' | {inp[:40]}")
    print()

    # 3. 实际拦截测试
    print("=== 实际拦截测试 ===")
    test_query = "记忆 遗忘 层"
    result = interceptor.intercept(f"记得以前说过{test_query}")
    if result.get('triggered'):
        print(f"Branch ID: {result['branch_id']}")
        print(f"Trigger phrase: {result['trigger_phrase']}")
        print(f"Query: {result['query']}")
        print(f"Results found: {len(result['results'])}")
        for r in result['results'][:2]:
            print(f"  - {r.get('backup_time', '?')} | score={r['score']:.2f} | {r['snippets'][0][:60]}...")
        print()
        print("=== 响应预览 ===")
        print(result['response'][:400])
    else:
        print("No trigger detected")

    print()
    print("=== Active branches ===")
    for b in interceptor.get_active_branches():
        print(f"  {b['branch_id']} | query='{b['query_preview']}' | files={b['matched_files_count']}")
