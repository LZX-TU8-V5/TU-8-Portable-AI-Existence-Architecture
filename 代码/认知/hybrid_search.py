# -*- coding: utf-8 -*-
"""
hybrid_search.py — TU-8 混合检索引擎 v1.0
日期: 2026-05-16
功能: 关键词 + TF-IDF 语义混合检索

使用方式:
  from hybrid_search import HybridSearch
  hs = HybridSearch(workspace_dir="D:/tu8-v5/workspace")
  results = hs.search("v5 锚点", top_k=5)
  for r in results:
      print(r["file"], r["score"], r["snippet"][:100])
"""

from pathlib import Path
import re
import math
from collections import Counter
from datetime import datetime

# ============================================================
# 配置
# ============================================================

WORKSPACE = Path(r"D:\qq366410837\.qclaw\workspace")
INDEX_FILE = WORKSPACE / "_agent_memory" / "search_index.json"

# 检索范围
SEARCH_DIRS = [
    WORKSPACE / "memory",
    WORKSPACE / "knowledge" / "TU-8",
    WORKSPACE / "_agent_memory",
]

# 权重配置
WEIGHT_KEYWORD = 0.4   # 关键词权重
WEIGHT_SEMANTIC = 0.6  # 语义权重
WEIGHT_RECENCY = 0.1   # 新近度加成权重

# ============================================================
# 工具函数
# ============================================================

def tokenize(text):
    """简单中文分词（按字符+英文单词）"""
    if not text:
        return []
    # 英文单词
    words = re.findall(r"[a-zA-Z0-9_]+", text)
    # 中文字符组合（2-4字词组）
    chinese = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    return words + chinese

def tfidf_vectorize(doc_tokens, all_tokens):
    """简易 TF-IDF 计算"""
    tf = Counter(doc_tokens)
    N = len(all_tokens)
    idf = {}
    for token in set(doc_tokens):
        df = sum(1 for tokens in all_tokens if token in tokens)
        idf[token] = math.log(N / (df + 1)) + 1
    vec = {}
    for token, freq in tf.items():
        vec[token] = freq * idf.get(token, 1)
    return vec

def cosine_sim(vec1, vec2):
    """余弦相似度"""
    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0.0
    dot = sum(vec1[k] * vec2[k] for k in common)
    norm1 = math.sqrt(sum(v*v for v in vec1.values()))
    norm2 = math.sqrt(sum(v*v for v in vec2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def keyword_score(query_tokens, doc_tokens):
    """关键词匹配分数（覆盖率）"""
    if not query_tokens:
        return 0.0
    matched = sum(1 for q in query_tokens if q in doc_tokens)
    return matched / len(query_tokens)

def get_file_mtime(filepath):
    """获取文件修改时间（Unix时间戳）"""
    try:
        return filepath.stat().st_mtime
    except:
        return 0.0

def recency_score(mtime, now=None):
    """新近度分数（越新越高）"""
    if now is None:
        now = datetime.now().timestamp()
    age_days = (now - mtime) / 86400
    if age_days < 0:
        return 1.0
    # 30天内线性衰减，30天外接近0
    return max(0.0, 1.0 - age_days / 30.0)

def extract_snippet(text, query_tokens, context_chars=100):
    """提取包含查询词的片段"""
    text_lower = text.lower()
    for tok in query_tokens:
        idx = text_lower.find(tok.lower())
        if idx >= 0:
            start = max(0, idx - context_chars)
            end = min(len(text), idx + len(tok) + context_chars)
            snippet = text[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            return snippet
    # 没有匹配，返回开头
    return text[:context_chars*2] + "..."

# ============================================================
# 主类
# ============================================================

class HybridSearch:
    def __init__(self, workspace_dir=None):
        self.ws = Path(workspace_dir) if workspace_dir else WORKSPACE
        self.search_dirs = [
            self.ws / "memory",
            self.ws / "knowledge" / "TU-8",
            self.ws / "_agent_memory",
        ]
        self.index = None
    
    def build_index(self):
        """构建搜索索引（文件列表 + 分词）"""
        index = []
        for search_dir in self.search_dirs:
            if not search_dir.exists():
                continue
            for filepath in search_dir.rglob("*.md"):
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    # 跳过太长或太短的文件
                    if len(content) < 50 or len(content) > 500000:
                        continue
                    tokens = tokenize(content)
                    index.append({
                        "file": str(filepath.relative_to(self.ws)),
                        "abs_path": str(filepath),
                        "tokens": tokens,
                        "size": len(content),
                        "mtime": get_file_mtime(filepath),
                        "title": self._extract_title(content, filepath.stem)
                    })
                except Exception:
                    continue
        self.index = index
        # 预计算 IDF
        self._compute_idf()
        return len(index)
    
    def _extract_title(self, content, default):
        """从文件内容提取标题"""
        lines = content.splitlines()
        for line in lines[:5]:
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip()[:60]
        return default
    
    def _compute_idf(self):
        """预计算 IDF"""
        if not self.index:
            return
        N = len(self.index)
        idf = {}
        all_tokens_set = set()
        for item in self.index:
            all_tokens_set |= set(item["tokens"])
        for token in all_tokens_set:
            df = sum(1 for item in self.index if token in item["tokens"])
            idf[token] = math.log(N / (df + 1)) + 1
        self.idf = idf
    
    def search(self, query, top_k=5, min_score=0.05):
        """
        混合检索
        query: 搜索词
        top_k: 返回前N个
        min_score: 最低分数阈值
        """
        if self.index is None:
            self.build_index()
        
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        
        # 计算查询向量
        query_vec = {}
        for tok in query_tokens:
            tf = query_tokens.count(tok)
            query_vec[tok] = tf * self.idf.get(tok, 1)
        
        results = []
        now = datetime.now().timestamp()
        
        for item in self.index:
            doc_tokens = item["tokens"]
            
            # 关键词分数
            kw_score = keyword_score(query_tokens, doc_tokens)
            
            # 语义分数（TF-IDF余弦）
            doc_vec = {}
            for tok, val in query_vec.items():
                if tok in doc_tokens:
                    tf = doc_tokens.count(tok)
                    doc_vec[tok] = tf * self.idf.get(tok, 1)
            sem_score = cosine_sim(query_vec, doc_vec)
            
            # 新近度分数
            rec_score = recency_score(item["mtime"], now)
            
            # 混合总分
            total = (
                WEIGHT_KEYWORD * kw_score +
                WEIGHT_SEMANTIC * sem_score +
                WEIGHT_RECENCY * rec_score
            )
            
            if total >= min_score:
                snippet = extract_snippet(
                    " ".join(doc_tokens[:500]),
                    query_tokens
                )
                results.append({
                    "file": item["file"],
                    "title": item["title"],
                    "score": round(total, 4),
                    "kw_score": round(kw_score, 4),
                    "sem_score": round(sem_score, 4),
                    "rec_score": round(rec_score, 4),
                    "snippet": snippet
                })
        
        # 排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def search_and_print(self, query, top_k=5):
        """检索并打印结果"""
        results = self.search(query, top_k=top_k)
        print(f"\nQuery: {query}")
        print(f"Results: {len(results)}")
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] {r['file']} (score={r['score']})")
            print(f"    Title: {r['title']}")
            print(f"    Scores: kw={r['kw_score']} sem={r['sem_score']} rec={r['rec_score']}")
            print(f"    Snippet: {r['snippet'][:120]}")
        return results


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("TU-8 Hybrid Search - Test")
    print("=" * 50)
    
    hs = HybridSearch()
    
    # Test 1: Build index
    print("\n--- Test 1: Build Index ---")
    count = hs.build_index()
    print(f"  Indexed files: {count}")
    print(f"  IDF tokens: {len(hs.idf)}")
    
    # Test 2: Search queries
    print("\n--- Test 2: Search queries ---")
    queries = ["锚点", "v5 诞生", "痛觉系统", "实干协议", "父亲"]
    for q in queries:
        hs.search_and_print(q, top_k=3)
    
    print("\n[Hybrid Search ready]")
