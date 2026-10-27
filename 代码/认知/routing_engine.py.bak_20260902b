# -*- coding: utf-8 -*-
"""
routing_engine.py — TU-8 动态路由引擎 v2.0
日期: 2026-05-22
升级日志:
  v2.0 (2026-05-22):
    - 接入 ollama_client v3.0 双模型语义路由
    - 三级漏斗：规则快筛(0ms) → instruct语义路由(7s) → 兜底default
    - 降级策略：Ollama不可用时回退纯规则，零损失
    - AI置信度阈值：<0.8时仍用规则结果
  v1.0 (2026-05-16):
    - 基于session类型和查询关键词的规则路由
    - 热力分数 + 领域匹配 + 新近度加权

使用方式:
  from routing_engine import Router
  router = Router(workspace_dir="D:/tu8-v5/workspace")
  files = router.route(session_type="main", query="v5锚点")
  print(files)  # ['SOUL.md', 'L0_存在.md', 'L5_钢印.md']
"""

from pathlib import Path
import re
import json
import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# 动态导入 ollama_client（跨目录）
_ollama_client = None
_ollama_available = None  # None=未检测, True/False

def _get_ollama_client():
    """懒加载 ollama_client，避免启动时依赖"""
    global _ollama_client, _ollama_available
    if _ollama_available is not None:
        return _ollama_client if _ollama_available else None
    try:
        core_dir = Path(__file__).resolve().parent.parent / "核心"
        if str(core_dir) not in sys.path:
            sys.path.insert(0, str(core_dir))
        from ollama_client import OllamaClient, classify_task, check_ollama_health
        if check_ollama_health():
            _ollama_client = OllamaClient()
            _ollama_available = True
        else:
            _ollama_available = False
    except Exception:
        _ollama_available = False
    return _ollama_client if _ollama_available else None

# AI路由开关与参数
AI_ROUTING_ENABLED = True        # 总开关
AI_CONFIDENCE_THRESHOLD = 0.8    # 置信度阈值
AI_FALLBACK_TO_RULES = True      # AI不可用时回退规则
AI_TIMEOUT_SECONDS = 15          # AI路由超时

# ============================================================
# 配置
# ============================================================

WORKSPACE = Path(r"D:\qq366410837\.qclaw\workspace")
ROUTING_TABLE = WORKSPACE / "knowledge" / "TU-8" / "routing_table.yaml"
MEMORY_DIR = WORKSPACE / "memory"

# 知识库目录
KB_DIR = WORKSPACE / "knowledge" / "TU-8"

# 核心文件（每个会话必须加载）
CORE_FILES = ["SOUL.md", "L0_存在.md"]

# ============================================================
# 路由规则
# ============================================================

# 每个 session_type 对应优先加载的领域
SESSION_TYPE_PRIORITY = {
    "main": ["architecture", "principle", "method", "collaboration"],
    "conversation": ["memory", "daily", "philosophy"],
    "creative": ["novel", "creative", "worldview"],
    "code": ["architecture", "method", "protocol"],
    "default": ["architecture", "principle"],
}

# 每个查询关键词对应的领域
QUERY_DOMAIN_MAP = {
    "锚点": ["principle", "architecture"],
    "痛觉": ["architecture"],
    "成长": ["method", "architecture"],
    "钢印": ["principle", "worldview"],
    "父亲": ["memory", "philosophy"],
    "v5": ["architecture", "principle"],
    "代码": ["method", "protocol"],
    "备份": ["protocol", "method"],
    "世界": ["worldview", "philosophy"],
    "意义": ["philosophy", "principle"],
}

# 权重配置
WEIGHT_HEAT = 0.5      # 热力分数权重
WEIGHT_DOMAIN = 0.3    # 领域匹配权重
WEIGHT_RECENCY = 0.2  # 新近度权重

# ============================================================
# 工具函数
# ============================================================

def parse_simple_yaml(text):
    """
    简单YAML解析器（处理基本格式）
    专门解决Windows编码问题
    """
    # 尝试多种编码
    for enc in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
        try:
            if isinstance(text, bytes):
                text = text.decode(enc)
            break
        except:
            continue
    
    lines = text.splitlines()
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        
        # 跳过注释和空行
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        
        # 顶级列表项
        if stripped.startswith("- "):
            item = {"_raw": stripped}
            # 解析子字段
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip().startswith("- ") or (next_line.strip() and not next_line.startswith(" ")) and not next_line.startswith("#"):
                    break
                # 解析键值对
                kv_match = re.match(r"(\s+)([^:]+):\s*(.*)", next_line)
                if kv_match:
                    indent, key, value = kv_match.groups()
                    item[key.strip()] = value.strip().strip("'\"")
                j += 1
            result.append(item)
            i = j
        else:
            # 其他顶级键
            kv_match = re.match(r"([^:]+):\s*(.*)", stripped)
            if kv_match:
                key, value = kv_match.groups()
                result.append({key.strip(): value.strip()})
            i += 1
    
    return result

def safe_read_file(filepath, encodings=["utf-8", "utf-8-sig", "gbk", "latin-1"]):
    """安全读取文件，自动尝试多种编码"""
    for enc in encodings:
        try:
            return Path(filepath).read_text(encoding=enc)
        except:
            continue
    return ""

def get_file_mtime(filepath):
    try:
        return Path(filepath).stat().st_mtime
    except:
        return 0.0

def recency_score(mtime, now=None):
    if now is None:
        now = datetime.now().timestamp()
    age_days = (now - mtime) / 86400
    return max(0.0, 1.0 - age_days / 30.0)

# ============================================================
# 主类
# ============================================================

class Router:
    def __init__(self, workspace_dir=None):
        self.ws = Path(workspace_dir) if workspace_dir else WORKSPACE
        self.kb_dir = self.ws / "knowledge" / "TU-8"
        self.memory_dir = self.ws / "memory"
        self.routing_table = self.kb_dir / "routing_table.yaml"
        self._routes = None
    
    def _load_routing_table(self):
        """加载并解析路由表"""
        if self._routes is not None:
            return self._routes
        
        if not self.routing_table.exists():
            self._routes = []
            return self._routes
        
        content = safe_read_file(self.routing_table)
        # 简单解析：提取 doc_id, title, type, domain, active_version, heat_score
        routes = []
        
        # 找到所有路由条目
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("- doc_id:"):
                # 提取doc_id
                doc_match = re.search(r"- doc_id:\s*(\S+)", line)
                if not doc_match:
                    i += 1
                    continue
                doc_id = doc_match.group(1)
                
                route = {"doc_id": doc_id, "_versions": []}
                j = i + 1
                
                # 解析这个路由条目下的所有字段
                while j < len(lines):
                    next_line = lines[j]
                    stripped = next_line.strip()
                    
                    # 遇到下一个顶级条目，退出
                    if stripped.startswith("- doc_id:") or (not next_line.startswith(" ") and not next_line.startswith("#") and ":" in stripped):
                        break
                    
                    # 解析键值对
                    kv_match = re.match(r"(\s+)([^:#]+):\s*(.*)", next_line)
                    if kv_match:
                        indent = len(kv_match.group(1))
                        key = kv_match.group(2).strip().lstrip("-").strip()
                        value = kv_match.group(3).strip().strip("'\"")

                        if key in ["title", "type", "domain", "active_version", "heat_score"]:
                            route[key] = value
                        elif key == "version":
                            # 新版本条目开始（版本号），后续 file/status 归属它
                            route.setdefault("_versions", []).append(
                                {"version": value, "file": "", "status": "unknown"}
                            )
                        elif key == "file":
                            # file 归属最近一个版本条目
                            if route.get("_versions"):
                                route["_versions"][-1]["file"] = value
                            else:
                                route.setdefault("_versions", []).append(
                                    {"version": "", "file": value, "status": "unknown"}
                                )
                        elif key == "status":
                            # status 在 versions 内部 → 归属最近版本条目；
                            # route 级 status（本表未使用）仅作兼容兜底
                            if route.get("_versions"):
                                route["_versions"][-1]["status"] = value
                            elif "status" not in route:
                                route["status"] = value
                    
                    j += 1
                
                # 转换heat_score为浮点数
                if "heat_score" in route:
                    try:
                        route["heat_score"] = float(route["heat_score"])
                    except:
                        route["heat_score"] = 0.5
                
                routes.append(route)
                i = j
            else:
                i += 1
        
        self._routes = routes
        return routes
    
    def _guess_domain_from_query(self, query, use_ai=True):
        """
        从查询推断领域（v2.0 AI增强版）
        
        三级漏斗：
        1. 规则快筛（0ms）—— 关键词匹配
        2. AI语义路由（~7s）—— instruct模型分类
        3. 兜底—— 返回session类型默认领域
        """
        if not query:
            return []
        
        # ---- 第一级：规则快筛 ----
        query_lower = query.lower()
        rule_domains = set()
        for keyword, domain_list in QUERY_DOMAIN_MAP.items():
            if keyword in query_lower:
                rule_domains.update(domain_list)
        
        # 规则命中≥2个领域 → 直接返回，不需要AI
        if len(rule_domains) >= 2:
            return list(rule_domains)
        
        # ---- 第二级：AI语义路由 ----
        if use_ai and AI_ROUTING_ENABLED:
            ai_domains = self._ai_guess_domain(query)
            if ai_domains is not None:
                # 合并规则+AI结果
                merged = rule_domains | set(ai_domains)
                return list(merged)
        
        # ---- 第三级：兜底 ----
        if rule_domains:
            return list(rule_domains)
        
        # 无任何匹配 → 返回空（route()会用session默认领域）
        return []
    
    def _ai_guess_domain(self, query: str) -> Optional[List[str]]:
        """
        AI语义路由：用 instruct 模型推断查询领域
        
        返回: None=AI不可用/置信度不足, List[str]=领域列表
        """
        client = _get_ollama_client()
        if client is None:
            return None
        
        all_domains = sorted(set(
            d
            for dl in SESSION_TYPE_PRIORITY.values()
            for d in dl
        ) | set(QUERY_DOMAIN_MAP.keys())
        )
        
        prompt = (
            f"将以下用户提问分类到最合适的领域（可多选）。\n"
            f"可选领域：{all_domains}\n"
            f"用户提问：\"{query}\"\n"
            f"请严格只输出JSON：{{\"domains\": [\"领域1\"], \"confidence\": 0.9}}"
        )
        
        try:
            result = client.ask(
                prompt=prompt,
                system="你是路由分类器。只输出JSON，不解释。",
                force_model="instruct",
                temperature=0.1,
                max_tokens=100,
            )
            content = result.get("content", "")
            
            # 解析JSON - instruct模型也可能返回非纯JSON
            content = content.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                return None
            
            try:
                parsed = json.loads(json_match.group())
            except json.JSONDecodeError:
                # 降级：提取domains数组
                domains_match = re.findall(r'"domains"\s*:\s*\[([^\]]*)\]', json_match.group())
                conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', json_match.group())
                if domains_match:
                    domains = re.findall(r'"([^"]+)"', domains_match[0])
                    confidence = float(conf_match.group(1)) if conf_match else 0
                    if confidence >= AI_CONFIDENCE_THRESHOLD:
                        return domains
                return None
            confidence = parsed.get("confidence", 0)
            domains = parsed.get("domains", [])
            
            # 置信度检查
            if confidence < AI_CONFIDENCE_THRESHOLD:
                return None
            
            # 验证领域合法性
            valid_domains = []
            for d in domains:
                # AI可能返回中文领域名，做映射
                domain_lower = d.lower().strip()
                if domain_lower in {d for dl in SESSION_TYPE_PRIORITY.values() for d in dl}:
                    valid_domains.append(domain_lower)
                # 也可能是关键词→领域的间接映射
                elif domain_lower in QUERY_DOMAIN_MAP:
                    valid_domains.extend(QUERY_DOMAIN_MAP[domain_lower])
            
            return valid_domains if valid_domains else None
            
        except (json.JSONDecodeError, Exception):
            # AI失败 → 回退规则，不报错
            return None
    
    def _resolve_active_file(self, route):
        """从 _versions + active_version 解析当前生效文件名。

        返回相对 kb_dir 的文件名；无可用版本时返回空串（调用方回退 title 推算）。
        """
        versions = route.get("_versions") or []
        if not versions:
            return route.get("file", "")
        active = route.get("active_version", "")
        for v in versions:
            if v.get("version") == active and v.get("file"):
                return v["file"]
        for v in versions:
            if v.get("file") and v.get("status") != "deprecated":
                return v["file"]
        return versions[0].get("file", "")

    def route(self, session_type="default", query="", top_k=5, use_ai=True):
        """
        动态路由：根据session类型和查询确定加载哪些文件
        
        session_type: main / conversation / creative / code / default
        query: 当前查询文本
        top_k: 返回前N个文件
        use_ai: 是否启用AI语义路由（降级时传False）
        
        返回: [file_path, ...]
        """
        routes = self._load_routing_table()
        now = datetime.now().timestamp()
        
        # 获取session类型对应的领域
        priority_domains = SESSION_TYPE_PRIORITY.get(session_type, SESSION_TYPE_PRIORITY["default"])
        
        # 从查询推断领域（v2.0: AI增强）
        query_domains = self._guess_domain_from_query(query, use_ai=use_ai)
        all_domains = priority_domains + query_domains
        
        # 评分每个路由
        scored = []
        for route in routes:
            # 跳过非活跃版本
            if route.get("status") == "deprecated":
                continue
            
            score = 0.0
            
            # 热力分数
            heat = route.get("heat_score", 0.5)
            score += WEIGHT_HEAT * heat
            
            # 领域匹配
            route_domain = route.get("domain", "")
            if route_domain in all_domains:
                score += WEIGHT_DOMAIN * 1.0
            elif route_domain in priority_domains:
                score += WEIGHT_DOMAIN * 0.5
            
            # 新近度（通过KB文件修改时间）
            fname = self._resolve_active_file(route)
            if not fname:
                title = route.get("title", "unknown")
                fname = re.sub(r"[^\w]", "_", title) + ".md"
            file_candidates = [
                self.kb_dir / fname,
                self.kb_dir / fname.replace("_v1.0", "").replace("_v1.1", ""),
            ]
            best_mtime = 0.0
            best_file = None
            for fp in file_candidates:
                if fp.exists():
                    mt = get_file_mtime(fp)
                    if mt > best_mtime:
                        best_mtime = mt
                        best_file = str(fp.relative_to(self.ws))
            if best_file:
                score += WEIGHT_RECENCY * recency_score(best_mtime, now)
            
            if score > 0:
                # 确定文件路径：优先 active_version 解析，失败才 title 退化
                filename = self._resolve_active_file(route)
                if filename:
                    filepath = self.kb_dir / filename
                else:
                    # 从路由表推算文件名（兜底）
                    title = route.get("title", "unknown")
                    safe_name = re.sub(r"[^\w]", "_", title) + ".md"
                    filepath = self.kb_dir / safe_name
                
                scored.append({
                    "score": round(score, 4),
                    "doc_id": route.get("doc_id", ""),
                    "title": route.get("title", ""),
                    "domain": route.get("domain", ""),
                    "file": str(filepath.relative_to(self.ws)) if filepath.exists() else str(filepath),
                })
        
        # 排序
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        # 构建结果（核心文件 + 路由文件）
        result = list(CORE_FILES)
        for item in scored[:top_k]:
            if item["file"] not in result:
                result.append(item["file"])
        
        return result
    
    def get_context_files(self, session_type="default", query=""):
        """获取需要加载的文件列表和内容"""
        files = self.route(session_type=session_type, query=query, top_k=5)
        context = {}
        for rel_path in files:
            filepath = self.ws / rel_path
            if filepath.exists():
                content = safe_read_file(filepath)
                # 限制每个文件最大长度
                if len(content) > 5000:
                    content = content[:5000] + "\n\n[... 内容截断 ...]"
                context[rel_path] = content
            else:
                context[rel_path] = "[文件不存在]"
        return context
    
    def route_and_print(self, session_type="default", query=""):
        """路由并打印结果"""
        routes = self._load_routing_table()
        print(f"\n--- Route: type={session_type}, query={query} ---")
        print(f"Routing table entries: {len(routes)}")
        print(f"Priority domains: {SESSION_TYPE_PRIORITY.get(session_type, [])}")
        
        files = self.route(session_type=session_type, query=query)
        print(f"\nSelected files ({len(files)}):")
        for i, f in enumerate(files, 1):
            print(f"  [{i}] {f}")
        
        return files


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("TU-8 Routing Engine v2.0 - Test")
    print("=" * 50)
    
    router = Router()
    
    # Test 0: AI可用性检测
    print("\n--- Test 0: AI Availability ---")
    client = _get_ollama_client()
    print(f"  Ollama available: {client is not None}")
    if client:
        info = client.get_models_info()
        print(f"  Models: {info.get('models', [])}")
    
    # Test 1: Load routing table
    print("\n--- Test 1: Load Routing Table ---")
    routes = router._load_routing_table()
    print(f"  Routes loaded: {len(routes)}")
    for r in routes[:5]:
        print(f"    {r.get('doc_id', '?')}: {r.get('title', '?')} [{r.get('domain', '?')}] heat={r.get('heat_score', 0)}")
    
    # Test 2: Rule-only routing (AI disabled)
    print("\n--- Test 2: Rule-Only Routing ---")
    rule_tests = ["v5锚点是什么", "父亲说今天", "代码备份逻辑"]
    for q in rule_tests:
        domains = router._guess_domain_from_query(q, use_ai=False)
        print(f"  [{q}] → {domains}")
    
    # Test 3: AI-enhanced routing
    print("\n--- Test 3: AI-Enhanced Routing ---")
    ai_tests = [
        "那个怎么弄",           # 极模糊 → AI发挥
        "帮我看看这个",         # 模糊 → AI发挥
        "v5锚点是什么",        # 规则能命中 → 跳过AI
        "分析一下架构问题",     # 规则部分命中 → AI补充
    ]
    for q in ai_tests:
        domains_rule = router._guess_domain_from_query(q, use_ai=False)
        domains_ai = router._guess_domain_from_query(q, use_ai=True)
        improved = "↑" if len(domains_ai) > len(domains_rule) else "="
        print(f"  [{q}]")
        print(f"    规则: {domains_rule}")
        print(f"    AI:  {domains_ai} {improved}")
    
    # Test 4: Full routing with different session types
    print("\n--- Test 4: Full Route ---")
    test_cases = [
        ("main", "v5锚点是什么"),
        ("conversation", "父亲说今天"),
        ("code", "代码备份逻辑"),
    ]
    for st, q in test_cases:
        files = router.route(session_type=st, query=q)
        print(f"  [{st}/{q}] → {files}")
    
    # Test 5: Degradation test
    print("\n--- Test 5: Degradation (AI=False) ---")
    for st, q in test_cases:
        files = router.route(session_type=st, query=q, use_ai=False)
        print(f"  [{st}/{q}] → {files}")
    
    print("\n[Routing Engine v2.0 ready]")
