# =============================================================================
# TU-8 L0-L6 架构层标注
# =============================================================================
# L0 存在   ─── SQLite 数据库路径、workspace 根目录
# L1 认知   ─── embedding 维度、相似度阈值
# L2 方法论 ─── add_event()、query_events()、expand_entities()
# L3 架构   ─── SQLite + FTS5 + numpy 三层存储、chunk/event/entity 三层模型
# L4 协作   ─── 与 memory_tiers.py 集成（知识蒸馏候选）
# L5 钢印   ─── 梦境日志（dream_logs）情感记录
# L6 健康   ─── 增量入库防索引损坏
#
# 代谢归属：知识代谢（管道）→ sag_lite_knowledge_graph 是存储层
# =============================================================================

"""
TU-8 结构化知识图谱引擎 (SAG-Lite)

基于 SAG 论文的核心洞察，用 SQLite + FTS5 + numpy 实现的结构化知识检索：
  chunk → event → entities
  事项保留完整语义，实体负责索引和关系扩展，支持多跳召回。

设计原则：
  1. 吸收 SAG 思想，不引入 PostgreSQL 重依赖
  2. SQLite + FTS5 替代 tsvector（百条规模足够）
  3. numpy 余弦替代 pgvector（免编译C扩展）
  4. 增量入库：每次写入自动更新索引和FTS
  5. 2-hop 扩展：百条规模1-2跳足够

数据模型（对齐 SAG 001_init.sql）：
  events    ← SAG events 表（title, summary, content, keywords, embedding）
  entities  ← SAG entities 表（name, normalized_name, type, embedding）
  event_entities ← SAG event_entities 桥表（weight, 多对多）
  chunks    ← SAG source_chunks（原文块，带 embedding）
  dream_logs ← TU-8 特有（梦境日志，emotion_type, emotion_score）

作者：TU-8 / 金木蟾
协议：CC BY-SA 4.0
"""

import sqlite3
import json
import os
import re
import math
import hashlib
import time
import logging
import unicodedata
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger("TU-8.KnowledgeGraph")

# ---------------------------------------------------------------------------
# 中文分词工具（替代 jieba，零依赖 fallback）
# ---------------------------------------------------------------------------

def tokenize_chinese(text: str) -> str:
    """中文文本分词：按字/词切分，生成 FTS5 可索引的 token 序列
    
    策略：
      - 英文：按空格/标点切词（FTS5 unicode61 原生支持）
      - 中文：bigram 分词（每两个相邻字符作为一个 token）
      - 混合：分别处理后合并
    
    为什么用 bigram 而不是 jieba：
      1. 零外部依赖（jieba 需要 50MB+ 词库）
      2. bigram 在 FTS5 中召回率高（不漏词）
      3. 百条规模下误召回可接受（靠向量粗排过滤）
    """
    if not text:
        return ""
    tokens = []
    chinese_chars = []
    i = 0
    while i < len(text):
        ch = text[i]
        if '\u4e00' <= ch <= '\u9fff':
            chinese_chars.append(ch)
        else:
            if chinese_chars:
                for j in range(len(chinese_chars) - 1):
                    tokens.append(chinese_chars[j] + chinese_chars[j + 1])
                for c in chinese_chars:
                    tokens.append(c)
                chinese_chars = []
        i += 1
    if chinese_chars:
        for j in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[j] + chinese_chars[j + 1])
        for c in chinese_chars:
            tokens.append(c)
    result = text + " " + " ".join(tokens)
    return result

# ---------------------------------------------------------------------------
# 归一化工具（对齐 SAG 的 normalized_name）
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """实体名称归一化：小写 + 去除标点 + NFKC Unicode 正规化
    
    对齐 SAG 的 entities.normalized_name 字段：
    tu8_memory / TU8_Memory / 记忆系统 中英文名应该能关联（后者靠FTS）
    """
    if not name:
        return ""
    # NFKC 正规化（全角→半角等）
    name = unicodedata.normalize("NFKC", name)
    # 小写
    name = name.lower().strip()
    # 去除多余空格
    name = re.sub(r'\s+', '_', name)
    # 去除标点（保留中文、字母、数字、下划线）
    name = re.sub(r'[^\w]', '', name, flags=re.UNICODE)
    return name


# ---------------------------------------------------------------------------
# 向量工具（替代 pgvector）
# ---------------------------------------------------------------------------

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """numpy 余弦相似度，替代 pgvector 的 vector_cosine_ops"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embedding_to_blob(vec: np.ndarray) -> bytes:
    """numpy array → BLOB 存储"""
    return vec.astype(np.float32).tobytes()


def blob_to_embedding(blob: bytes, dim: int = 64) -> np.ndarray:
    """BLOB → numpy array"""
    if not blob:
        return np.zeros(dim, dtype=np.float32)
    return np.frombuffer(blob, dtype=np.float32)


def simple_hash_embedding(text: str, dim: int = 64) -> np.ndarray:
    """确定性哈希嵌入（本地 fallback，真实检索应接 embedding API）
    
    对齐 SAG 的 "local deterministic fallback" 设计：
    无 API Key 时仍可工作，但检索质量依赖真实 embedding。
    """
    vec = np.zeros(dim, dtype=np.float32)
    if not text:
        return vec
    # 多窗口哈希
    for i in range(dim):
        seed = f"{text}#{i}"
        h = hashlib.sha256(seed.encode()).hexdigest()
        vec[i] = (int(h[:8], 16) / 0xFFFFFFFF - 0.5) * 2.0
    # 归一化
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


# ---------------------------------------------------------------------------
# 核心引擎
# ---------------------------------------------------------------------------

class KnowledgeGraphDB:
    """TU-8 结构化知识图谱数据库
    
    对齐 SAG 的三层数据模型：
      events → entities → event_entities（桥表）
      + chunks（原文块）
      + dream_logs（TU-8 梦境特有）
    
    使用 SQLite + FTS5 替代 PostgreSQL + pgvector。
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str, embedding_dim: int = 64):
        self.db_path = db_path
        self.embedding_dim = embedding_dim
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_db()

    # ----- 连接管理 -----

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ----- Schema 初始化 -----

    def _ensure_db(self):
        """对齐 SAG 001_init.sql 的表结构，用 SQLite 语法"""
        c = self.conn.cursor()
        
        # 1. events 表（对应 SAG events）
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id          TEXT PRIMARY KEY,
                source_id   TEXT NOT NULL DEFAULT 'default',
                document_id TEXT,
                chunk_id    TEXT,
                parent_id   TEXT REFERENCES events(id) ON DELETE CASCADE,
                level       INTEGER NOT NULL DEFAULT 0,
                rank        INTEGER NOT NULL DEFAULT 0,
                title       TEXT NOT NULL,
                summary     TEXT NOT NULL DEFAULT '',
                content     TEXT NOT NULL,
                category    TEXT,
                keywords    TEXT NOT NULL DEFAULT '[]',
                priority    TEXT,
                rationale   TEXT NOT NULL DEFAULT '',
                status      TEXT DEFAULT 'active',
                start_time  TEXT,
                end_time    TEXT,
                metadata    TEXT NOT NULL DEFAULT '{}',
                embedding   BLOB,
                deleted_at  TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_id, deleted_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_chunk ON events(chunk_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_rationale ON events(rationale) WHERE rationale != ''")

        # 2. entities 表（对应 SAG entities）
        c.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id              TEXT PRIMARY KEY,
                source_id       TEXT NOT NULL DEFAULT 'default',
                entity_type_id  TEXT,
                type            TEXT NOT NULL,
                name            TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                description     TEXT,
                embedding       BLOB,
                metadata        TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # 对齐 SAG 的 entities_source_type_name_unique_idx
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_unique 
            ON entities(source_id, type, normalized_name)
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(source_id, type)")

        # 3. event_entities 桥表（对应 SAG event_entities）
        c.execute("""
            CREATE TABLE IF NOT EXISTS event_entities (
                id          TEXT PRIMARY KEY,
                event_id    TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                entity_id   TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                weight      REAL NOT NULL DEFAULT 1.0,
                description TEXT,
                embedding   BLOB,
                metadata    TEXT NOT NULL DEFAULT '{}',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ee_unique 
            ON event_entities(event_id, entity_id)
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ee_entity ON event_entities(entity_id, event_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ee_event ON event_entities(event_id, entity_id)")

        # 4. chunks 表（对应 SAG source_chunks）
        c.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id          TEXT PRIMARY KEY,
                source_id   TEXT NOT NULL DEFAULT 'default',
                document_id TEXT,
                heading     TEXT NOT NULL DEFAULT '',
                content     TEXT NOT NULL,
                raw_content TEXT,
                rank        INTEGER NOT NULL DEFAULT 0,
                metadata    TEXT NOT NULL DEFAULT '{}',
                embedding   BLOB,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id, document_id, rank)")

        # 5. dream_logs 表（TU-8 特有，SAG 无对应）
        c.execute("""
            CREATE TABLE IF NOT EXISTS dream_logs (
                id              TEXT PRIMARY KEY,
                event_id        TEXT REFERENCES events(id) ON DELETE SET NULL,
                inspiration_id  TEXT,
                raw_log         TEXT NOT NULL,
                emotion_type    TEXT,
                emotion_score   REAL NOT NULL DEFAULT 0.5,
                problem         TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_dream_emotion ON dream_logs(emotion_type, emotion_score)")

        # 6. FTS5 全文索引（替代 SAG 的 tsvector GIN 索引）
        # 对齐 SAG 的 search_text = to_tsvector(title || summary || content)
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_events USING fts5(
                title, summary, content, keywords,
                content='events', content_rowid='rowid',
                tokenize='unicode61'
            )
        """)
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_entities USING fts5(
                name, description,
                content='entities', content_rowid='rowid',
                tokenize='unicode61'
            )
        """)

        # 7. Schema 版本追踪（对齐 SAG 的 schema_migrations）
        c.execute("""
            CREATE TABLE IF NOT EXISTS schema_info (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        c.execute(
            "INSERT OR IGNORE INTO schema_info (key, value) VALUES (?, ?)",
            ("schema_version", str(self.SCHEMA_VERSION))
        )
        c.execute(
            "INSERT OR IGNORE INTO schema_info (key, value) VALUES (?, ?)",
            ("created_at", datetime.now(timezone.utc).isoformat())
        )

        self.conn.commit()

    # =====================================================================
    # 写入操作 — 增量入库（对齐 SAG 的 "写入时自动维护" 设计）
    # =====================================================================

    def _gen_id(self, prefix: str = "evt") -> str:
        """生成时间戳+哈希ID"""
        ts = int(time.time() * 1000)
        h = hashlib.md5(f"{prefix}{ts}{os.urandom(4).hex()}".encode()).hexdigest()[:8]
        return f"{prefix}_{ts}_{h}"

    def add_event(
        self,
        title: str,
        content: str,
        *,
        summary: str = "",
        category: str = None,
        keywords: list = None,
        rationale: str = "",
        source_id: str = "default",
        document_id: str = None,
        chunk_id: str = None,
        parent_id: str = None,
        priority: str = None,
        status: str = "active",
        start_time: str = None,
        end_time: str = None,
        metadata: dict = None,
        embedding: np.ndarray = None,
    ) -> str:
        """添加事项卡片（对齐 SAG 的 events INSERT）
        
        自动维护：
          - FTS5 索引（等价于 SAG 的 GENERATED ALWAYS AS tsvector）
          - embedding（为空时用确定性哈希 fallback）
        
        rationale: 决策理由——为什么这样做，而不只是做了什么。
        这是时间锚点从流水账变为因果链的关键字段。
        """
        eid = self._gen_id("evt")
        kw_json = json.dumps(keywords or [], ensure_ascii=False)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        
        # embedding: 传入优先，否则 fallback
        if embedding is None:
            embedding = simple_hash_embedding(f"{title} {content}")
        emb_blob = embedding_to_blob(embedding)

        self.conn.execute("""
            INSERT INTO events 
            (id, source_id, document_id, chunk_id, parent_id, 
             title, summary, content, category, keywords,
             priority, rationale, status, start_time, end_time, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (eid, source_id, document_id, chunk_id, parent_id,
              title, summary, content, category, kw_json,
              priority, rationale, status, start_time, end_time, meta_json, emb_blob))

        # 自动维护 FTS5（对齐 SAG 的 tsvector 自动生成）
        # 中文 bigram 预处理：让 FTS5 能匹配中文查询
        fts_title = tokenize_chinese(title)
        fts_summary = tokenize_chinese(summary)
        fts_content = tokenize_chinese(content)
        fts_keywords = tokenize_chinese(" ".join(keywords or []))
        self.conn.execute("""
            INSERT INTO fts_events (rowid, title, summary, content, keywords)
            VALUES ((SELECT rowid FROM events WHERE id = ?), ?, ?, ?, ?)
        """, (eid, fts_title, fts_summary, fts_content, fts_keywords))

        self.conn.commit()
        logger.debug(f"[SAG-Lite] 事项入库: {eid} | {title[:40]}")
        return eid

    def add_entity(
        self,
        name: str,
        entity_type: str,
        *,
        description: str = None,
        source_id: str = "default",
        metadata: dict = None,
        embedding: np.ndarray = None,
    ) -> str:
        """添加实体（对齐 SAG entities INSERT）
        
        核心创新：normalized_name 自动归一化
          tu8_memory / TU8_Memory / 记忆系统 → 同一 normalized_name
        """
        norm_name = normalize_name(name)
        
        # 去重：同 source_id + type + normalized_name 已存在则更新
        existing = self.conn.execute(
            "SELECT id FROM entities WHERE source_id = ? AND type = ? AND normalized_name = ?",
            (source_id, entity_type, norm_name)
        ).fetchone()
        
        if existing:
            eid = existing["id"]
            # 更新描述和 embedding
            if embedding is None:
                embedding = simple_hash_embedding(name)
            emb_blob = embedding_to_blob(embedding)
            self.conn.execute("""
                UPDATE entities SET description = COALESCE(?, description),
                                    embedding = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (description, emb_blob, eid))
            self.conn.commit()
            logger.debug(f"[SAG-Lite] 实体更新(去重): {eid} | {name} → {norm_name}")
            return eid

        eid = self._gen_id("ent")
        if embedding is None:
            embedding = simple_hash_embedding(name)
        emb_blob = embedding_to_blob(embedding)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        self.conn.execute("""
            INSERT INTO entities (id, source_id, type, name, normalized_name, 
                                  description, embedding, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (eid, source_id, entity_type, name, norm_name,
              description, emb_blob, meta_json))

        # FTS5（中文 bigram 预处理）
        fts_name = tokenize_chinese(name)
        fts_desc = tokenize_chinese(description or "")
        self.conn.execute("""
            INSERT INTO fts_entities (rowid, name, description)
            VALUES ((SELECT rowid FROM entities WHERE id = ?), ?, ?)
        """, (eid, fts_name, fts_desc))

        self.conn.commit()
        logger.debug(f"[SAG-Lite] 实体入库: {eid} | {name} → {norm_name}")
        return eid

    def link_event_entity(
        self,
        event_id: str,
        entity_id: str,
        *,
        weight: float = 1.0,
        description: str = None,
    ) -> str:
        """建立事项↔实体关联（对齐 SAG event_entities INSERT）
        
        幂等：重复链接自动忽略
        """
        # 幂等检查
        existing = self.conn.execute(
            "SELECT id FROM event_entities WHERE event_id = ? AND entity_id = ?",
            (event_id, entity_id)
        ).fetchone()
        if existing:
            return existing["id"]

        eeid = self._gen_id("ee")
        self.conn.execute("""
            INSERT INTO event_entities (id, event_id, entity_id, weight, description)
            VALUES (?, ?, ?, ?, ?)
        """, (eeid, event_id, entity_id, weight, description))
        self.conn.commit()
        logger.debug(f"[SAG-Lite] 关联建立: {event_id} ↔ {entity_id} (w={weight})")
        return eeid

    def add_dream_log(
        self,
        raw_log: str,
        *,
        event_id: str = None,
        inspiration_id: str = None,
        emotion_type: str = "neutral",
        emotion_score: float = 0.5,
        problem: str = None,
    ) -> str:
        """添加梦境日志（TU-8 特有，SAG 无对应）"""
        did = self._gen_id("drm")
        self.conn.execute("""
            INSERT INTO dream_logs (id, event_id, inspiration_id, raw_log,
                                    emotion_type, emotion_score, problem)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (did, event_id, inspiration_id, raw_log,
              emotion_type, emotion_score, problem))
        self.conn.commit()
        return did

    def add_chunk(
        self,
        content: str,
        *,
        heading: str = "",
        source_id: str = "default",
        document_id: str = None,
        raw_content: str = None,
        rank: int = 0,
        metadata: dict = None,
        embedding: np.ndarray = None,
    ) -> str:
        """添加原文块（对齐 SAG source_chunks INSERT）"""
        cid = self._gen_id("chk")
        if embedding is None:
            embedding = simple_hash_embedding(content[:200])
        emb_blob = embedding_to_blob(embedding)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        self.conn.execute("""
            INSERT INTO chunks (id, source_id, document_id, heading, content,
                                raw_content, rank, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, source_id, document_id, heading, content,
              raw_content, rank, meta_json, emb_blob))
        self.conn.commit()
        return cid

    # =====================================================================
    # 检索操作 — 对齐 SAG search-service.ts 的8步管线
    # =====================================================================

    def search_entities_bm25(
        self, query: str, *, source_id: str = None, limit: int = 20
    ) -> list:
        """Step 2: BM25 匹配实体（对齐 SAG fast 模式的 step1Bm25Entities）
        
        使用 FTS5 替代 PostgreSQL 的 tsvector + GIN 索引。
        这是 SAG 的核心创新之一：实体名称精确匹配比向量模糊匹配更高效。
        中文查询自动 bigram 展开。
        source_id=None 时搜索所有来源。
        """
        fts_query = tokenize_chinese(query)
        terms = fts_query.split()
        if not terms:
            return []
        match_expr = " OR ".join(f'"{t}"' for t in terms[:20])
        
        try:
            if source_id:
                results = self.conn.execute(f"""
                    SELECT e.id, e.name, e.type, e.normalized_name, e.description,
                           rank as fts_rank
                    FROM fts_entities fe
                    JOIN entities e ON e.rowid = fe.rowid
                    WHERE fts_entities MATCH ? AND e.source_id = ?
                    ORDER BY rank
                    LIMIT ?
                """, (match_expr, source_id, limit)).fetchall()
            else:
                results = self.conn.execute(f"""
                    SELECT e.id, e.name, e.type, e.normalized_name, e.description,
                           rank as fts_rank
                    FROM fts_entities fe
                    JOIN entities e ON e.rowid = fe.rowid
                    WHERE fts_entities MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (match_expr, limit)).fetchall()
            return [dict(r) for r in results]
        except Exception as e:
            logger.warning(f"BM25查询失败: {e} | query={query}")
            return []

    def get_event_ids_by_entity_ids(
        self, entity_ids: list, *, source_id: str = None,
        exclude_event_ids: list = None
    ) -> list:
        """Step 3: 实体→事件关联（对齐 SAG getEventIdsByEntityIds）
        
        这是多跳扩展的核心：从实体出发找到关联事件。
        SQLite 的索引查询 O(1)，替代 SAG 的 SQL JOIN。
        source_id=None 时搜索所有来源。
        """
        if not entity_ids:
            return []
        
        placeholders = ",".join("?" * len(entity_ids))
        sql = f"""
            SELECT DISTINCT ee.event_id
            FROM event_entities ee
            JOIN events e ON e.id = ee.event_id
            WHERE ee.entity_id IN ({placeholders})
              AND e.deleted_at IS NULL
        """
        params = list(entity_ids)
        
        if source_id:
            sql += " AND e.source_id = ?"
            params.append(source_id)
        
        if exclude_event_ids:
            excl_ph = ",".join("?" * len(exclude_event_ids))
            sql += f" AND ee.event_id NOT IN ({excl_ph})"
            params += exclude_event_ids
        
        rows = self.conn.execute(sql, params).fetchall()
        return [r["event_id"] for r in rows]

    def search_events_by_vector(
        self, query_vector: np.ndarray, *, source_id: str = "default",
        top_k: int = 10, threshold: float = 0.05
    ) -> list:
        """Step 4: 标题向量召回事件（对齐 SAG searchEventsByTitleVector）
        
        用 numpy 余弦替代 pgvector 的 HNSW 索引。
        百条规模下全表扫描 < 1ms，不需要 HNSW。
        
        注意：默认阈值0.05（非0.3），因为 simple_hash_embedding 的
        余弦相似度天然较低（哈希近似正交）。真实 embedding API 可提高到0.5+。
        """
        rows = self.conn.execute(
            "SELECT id, title, summary, content, category, keywords, embedding "
            "FROM events WHERE source_id = ? AND deleted_at IS NULL",
            (source_id,)
        ).fetchall()

        scored = []
        for r in rows:
            if r["embedding"]:
                emb = blob_to_embedding(r["embedding"], self.embedding_dim)
                sim = cosine_similarity(query_vector, emb)
                if sim >= threshold:
                    scored.append({
                        "id": r["id"], "title": r["title"], "summary": r["summary"],
                        "content": r["content"], "category": r["category"],
                        "keywords": r["keywords"], "score": sim
                    })
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def search_events_by_fts(
        self, query: str, *, source_id: str = None, top_k: int = 10
    ) -> list:
        """FTS5 全文检索事件（对齐 SAG 的 tsvector 事件搜索）
        
        用 bigram 分词后的 FTS5 索引召回事件。
        当向量搜索因哈希嵌入低区分度失效时，FTS5 是主要召回路径。
        source_id=None 时不限定来源。
        """
        fts_query = tokenize_chinese(query)
        terms = fts_query.split()
        if not terms:
            return []
        # OR 组合各 bigram term
        match_expr = " OR ".join(f'"{t}"' for t in terms[:20])
        
        try:
            if source_id:
                results = self.conn.execute("""
                    SELECT e.id, e.title, e.summary, e.content, e.category,
                           e.keywords, e.rationale, e.priority
                    FROM fts_events fe
                    JOIN events e ON e.rowid = fe.rowid
                    WHERE fts_events MATCH ? AND e.source_id = ?
                      AND e.deleted_at IS NULL
                    LIMIT ?
                """, (match_expr, source_id, top_k)).fetchall()
            else:
                results = self.conn.execute("""
                    SELECT e.id, e.title, e.summary, e.content, e.category,
                           e.keywords, e.rationale, e.priority
                    FROM fts_events fe
                    JOIN events e ON e.rowid = fe.rowid
                    WHERE fts_events MATCH ?
                      AND e.deleted_at IS NULL
                    LIMIT ?
                """, (match_expr, top_k)).fetchall()
            return [dict(r) for r in results]
        except Exception as e:
            logger.warning(f"FTS5事件查询失败: {e} | query={query}")
            return []

    def expand_events(
        self, seed_event_ids: list, initial_entity_ids: list,
        *, source_id: str = "default", max_hops: int = 2
    ) -> list:
        """Step 5-6: 多跳扩展（对齐 SAG expandFixedHops）
        
        核心算法：
          tracked_events ← seeds
          tracked_entities ← initial
          for hop in range(max_hops):
              新实体 = seed事件的实体 - tracked_entities
              新事件 = 新实体关联的事件 - tracked_events
              tracked_events ∪= 新事件
              tracked_entities ∪= 新实体
        """
        tracked_events = set(seed_event_ids)
        tracked_entities = set(initial_entity_ids)
        expanded_event_ids = []
        
        current_event_ids = list(seed_event_ids)
        
        for hop in range(max_hops):
            # 从当前事件找到新实体
            if not current_event_ids:
                break
            ph = ",".join("?" * len(current_event_ids))
            entity_rows = self.conn.execute(f"""
                SELECT DISTINCT ee.entity_id
                FROM event_entities ee
                WHERE ee.event_id IN ({ph})
            """, current_event_ids).fetchall()
            
            new_entity_ids = [r["entity_id"] for r in entity_rows
                             if r["entity_id"] not in tracked_entities]
            if not new_entity_ids:
                break
            tracked_entities.update(new_entity_ids)
            
            # 从新实体找到新事件
            new_event_ids = self.get_event_ids_by_entity_ids(
                new_entity_ids, source_id=source_id,
                exclude_event_ids=list(tracked_events)
            )
            if not new_event_ids:
                break
            tracked_events.update(new_event_ids)
            expanded_event_ids.extend(new_event_ids)
            current_event_ids = new_event_ids
            
            logger.debug(f"[SAG-Lite] Hop {hop+1}: +{len(new_entity_ids)}实体, +{len(new_event_ids)}事件")
        
        return expanded_event_ids

    def search_multi(
        self, query: str, *, source_id: str = "default",
        search_mode: str = "fast", top_k: int = 5, max_hops: int = 2,
        similarity_threshold: float = 0.3
    ) -> dict:
        """SAG-Lite 多路检索（对齐 SAG search-service.ts multiSearch）
        
        管线：
          1. 查询向量化
          2. 实体召回（fast=BM25 / standard=BM25+向量）
          3. 实体→事件关联
          4. 标题向量召回事件
          5. 合并种子事件
          6. 多跳扩展
          7. 粗排（向量相似度）
          8. 返回 top-k 事件 + 关联 chunks
        """
        trace = {
            "query": query, "search_mode": search_mode,
            "steps": [], "timings": {}
        }
        t0 = time.time()

        # Step 1: 查询向量化
        query_vector = simple_hash_embedding(query)
        t1 = time.time()
        trace["timings"]["query_embedding"] = round(t1 - t0, 4)

        # Step 2: 实体召回（不传 source_id，搜索所有来源）
        if search_mode == "fast":
            recalled_entities = self.search_entities_bm25(query)
        else:
            # standard: BM25 + 向量双路
            bm25_hits = self.search_entities_bm25(query)
            vec_hits = self.search_entities_by_vector(
                query_vector, threshold=similarity_threshold)
            # 合并去重
            seen = set()
            recalled_entities = []
            for hit in bm25_hits + vec_hits:
                if hit["id"] not in seen:
                    seen.add(hit["id"])
                    recalled_entities.append(hit)
        
        t2 = time.time()
        trace["timings"]["entity_recall"] = round(t2 - t1, 4)
        trace["steps"].append(f"实体召回: {len(recalled_entities)} 个")

        # Step 3: 实体→事件关联（不传 source_id，搜索所有来源）
        entity_ids = [e["id"] for e in recalled_entities]
        entity_event_ids = self.get_event_ids_by_entity_ids(
            entity_ids)
        
        t3 = time.time()
        trace["timings"]["entity_events"] = round(t3 - t2, 4)
        trace["steps"].append(f"实体关联事件: {len(entity_event_ids)} 个")

        # Step 4: 标题向量召回事件
        query_events = self.search_events_by_vector(
            query_vector, source_id=source_id,
            top_k=top_k * 3, threshold=similarity_threshold)
        query_event_ids = [e["id"] for e in query_events]
        
        t4 = time.time()
        trace["timings"]["vector_events"] = round(t4 - t3, 4)
        trace["steps"].append(f"向量召回事件: {len(query_event_ids)} 个")

        # Step 5: 合并种子事件
        seed_event_ids = list(dict.fromkeys(entity_event_ids + query_event_ids))
        
        if not seed_event_ids:
            # 降级：纯向量 chunk 检索
            trace["fallback_reason"] = "no seed events; chunk vector search"
            chunk_results = self.search_chunks_by_vector(
                query_vector, source_id=source_id, top_k=top_k)
            trace["timings"]["total"] = round(time.time() - t0, 4)
            return {"results": chunk_results, "trace": trace}

        # Step 6: 多跳扩展
        expanded_ids = self.expand_events(
            seed_event_ids, entity_ids,
            source_id=source_id, max_hops=max_hops)
        
        t5 = time.time()
        trace["timings"]["expand"] = round(t5 - t4, 4)
        trace["steps"].append(f"多跳扩展: +{len(expanded_ids)} 个事件")

        # Step 7: 粗排（向量相似度）
        all_event_ids = list(dict.fromkeys(seed_event_ids + expanded_ids))
        all_events = self._get_events_by_ids(all_event_ids)
        
        ranked = []
        for evt in all_events:
            if evt.get("embedding"):
                emb = blob_to_embedding(evt["embedding"], self.embedding_dim)
                sim = cosine_similarity(query_vector, emb)
                evt["score"] = sim
                ranked.append(evt)
        
        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_results = ranked[:top_k]
        
        t6 = time.time()
        trace["timings"]["rank"] = round(t6 - t5, 4)
        trace["timings"]["total"] = round(t6 - t0, 4)
        trace["steps"].append(f"粗排 top-{top_k}: {[r['title'][:20] for r in top_results]}")

        return {"results": top_results, "trace": trace}

    # ----- 辅助检索 -----

    def search_entities_by_vector(
        self, query_vector: np.ndarray, *, source_id: str = "default",
        top_k: int = 10, threshold: float = 0.05
    ) -> list:
        """向量召回实体（对齐 SAG searchEntitiesByVector）"""
        rows = self.conn.execute(
            "SELECT id, name, type, normalized_name, description, embedding "
            "FROM entities WHERE source_id = ?",
            (source_id,)
        ).fetchall()

        scored = []
        for r in rows:
            if r["embedding"]:
                emb = blob_to_embedding(r["embedding"], self.embedding_dim)
                sim = cosine_similarity(query_vector, emb)
                if sim >= threshold:
                    scored.append({
                        "id": r["id"], "name": r["name"], "type": r["type"],
                        "normalized_name": r["normalized_name"],
                        "description": r["description"], "score": sim
                    })
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def search_chunks_by_vector(
        self, query_vector: np.ndarray, *, source_id: str = "default",
        top_k: int = 10, threshold: float = 0.05
    ) -> list:
        """向量召回 chunks（降级路径）"""
        rows = self.conn.execute(
            "SELECT id, heading, content, embedding "
            "FROM chunks WHERE source_id = ?",
            (source_id,)
        ).fetchall()

        scored = []
        for r in rows:
            if r["embedding"]:
                emb = blob_to_embedding(r["embedding"], self.embedding_dim)
                sim = cosine_similarity(query_vector, emb)
                if sim >= threshold:
                    scored.append({
                        "chunk_id": r["id"], "heading": r["heading"],
                        "content": r["content"], "score": sim
                    })
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _get_events_by_ids(self, event_ids: list) -> list:
        """批量获取事件详情"""
        if not event_ids:
            return []
        ph = ",".join("?" * len(event_ids))
        rows = self.conn.execute(f"""
            SELECT id, title, summary, content, category, keywords, 
                   priority, status, metadata, embedding, created_at
            FROM events WHERE id IN ({ph})
        """, event_ids).fetchall()
        return [dict(r) for r in rows]

    # =====================================================================
    # 迁移工具 — 从旧 JSON 索引迁移到 SQLite
    # =====================================================================

    def migrate_from_json(self, json_dir: str) -> dict:
        """从旧 JSON 索引迁移数据到 SQLite
        
        迁移源：
          - knowledge_graph.json → entities + events + event_entities
          - tu8_brain_v2.json → 额外 nodes + edges
          - tu8_brain_v3_forget.json → 额外 edges + dream_logs
        """
        stats = {"entities": 0, "events": 0, "links": 0, "dreams": 0, "skipped": 0}
        
        # 1. 迁移 knowledge_graph.json
        kg_path = os.path.join(json_dir, "knowledge_graph.json")
        if os.path.exists(kg_path):
            with open(kg_path, 'r', encoding='utf-8') as f:
                kg = json.load(f)
            
            # nodes → entities
            for node in kg.get("nodes", []):
                try:
                    eid = self.add_entity(
                        name=node.get("content", node.get("id")),
                        entity_type=node.get("category", "unknown"),
                        description=json.dumps(node.get("tags", []), ensure_ascii=False),
                        metadata={
                            "original_id": node.get("id"),
                            "tone_risk": node.get("tone_risk"),
                            "emotion": node.get("emotion"),
                            "citation_count": node.get("citation_count", 0),
                        }
                    )
                    stats["entities"] += 1
                except Exception as e:
                    logger.warning(f"迁移节点跳过: {node.get('id')} | {e}")
                    stats["skipped"] += 1
            
            # edges → events + event_entities
            for edge in kg.get("edges", []):
                try:
                    src = edge.get("source", "")
                    tgt = edge.get("target", "")
                    rel = edge.get("relation_type", "related")
                    problem = edge.get("problem", "")
                    
                    # 创建连线事件
                    evt_id = self.add_event(
                        title=f"{src} ↔ {tgt}: {rel}",
                        content=problem or f"{src} {rel} {tgt}",
                        category="cross_domain_link",
                        keywords=[rel],
                        metadata={
                            "original_source": src,
                            "original_target": tgt,
                            "intuition_weight": edge.get("intuition_weight"),
                            "cross_weight": edge.get("cross_weight"),
                        }
                    )
                    stats["events"] += 1
                except Exception as e:
                    logger.warning(f"迁移边跳过: {edge.get('id')} | {e}")
                    stats["skipped"] += 1

        # 2. 迁移 tu8_brain_v2.json
        v2_path = os.path.join(json_dir, "tu8_brain_v2.json")
        if os.path.exists(v2_path):
            with open(v2_path, 'r', encoding='utf-8') as f:
                v2 = json.load(f)
            
            for node in v2.get("nodes", []):
                try:
                    self.add_entity(
                        name=node.get("content", node.get("id")),
                        entity_type=node.get("category", "unknown"),
                        description=node.get("emotion_mark", ""),
                        metadata={
                            "original_id": node.get("id"),
                            "vitality": node.get("vitality"),
                        }
                    )
                    stats["entities"] += 1
                except Exception as e:
                    stats["skipped"] += 1

        # 3. 迁移 tu8_brain_v3_forget.json（梦境日志）
        v3_path = os.path.join(json_dir, "tu8_brain_v3_forget.json")
        if os.path.exists(v3_path):
            with open(v3_path, 'r', encoding='utf-8') as f:
                v3 = json.load(f)
            
            for log in v3.get("raw_dream_logs", []):
                try:
                    self.add_dream_log(
                        raw_log=log.get("raw_log", ""),
                        inspiration_id=log.get("inspiration_id"),
                        emotion_type=log.get("emotion_type", "neutral"),
                        emotion_score=log.get("emotion_score", 0.5),
                    )
                    stats["dreams"] += 1
                except Exception as e:
                    stats["skipped"] += 1

        # 4. 迁移 seal_index.json（时间钢印链）
        seal_path = os.path.join(json_dir, "..", "..", "memory", "time_chain", "seal_index.json")
        seal_path = os.path.normpath(seal_path)
        if os.path.exists(seal_path):
            try:
                with open(seal_path, 'r', encoding='utf-8') as f:
                    seals = json.load(f)
                for seal in seals:
                    self.add_event(
                        title=f"钢印: {seal.get('scene_tag', 'unknown')}",
                        content=seal.get("summary", ""),
                        category="seal_chain",
                        keywords=[seal.get("scene_tag", "")],
                        metadata={
                            "seal_id": seal.get("seal_id"),
                            "parent_seal": seal.get("parent_seal"),
                            "timestamp": seal.get("timestamp"),
                        }
                    )
                    stats["events"] += 1
            except Exception as e:
                logger.warning(f"钢印链迁移失败: {e}")

        logger.info(f"[SAG-Lite] 迁移完成: {stats}")
        return stats

    # =====================================================================
    # 统计与诊断
    # =====================================================================

    def stats(self) -> dict:
        """数据库统计信息"""
        counts = {}
        for table in ["events", "entities", "event_entities", "chunks", "dream_logs"]:
            row = self.conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            counts[table] = row["cnt"]
        
        # FTS5 统计
        try:
            evt_fts = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM fts_events").fetchone()
            ent_fts = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM fts_entities").fetchone()
            counts["fts_events"] = evt_fts["cnt"]
            counts["fts_entities"] = ent_fts["cnt"]
        except Exception:
            counts["fts_events"] = -1
            counts["fts_entities"] = -1

        return counts

    def verify_integrity(self) -> dict:
        """数据完整性校验"""
        issues = []
        
        # 1. 孤儿事件（无实体关联）
        orphan_events = self.conn.execute("""
            SELECT e.id, e.title FROM events e
            LEFT JOIN event_entities ee ON ee.event_id = e.id
            WHERE ee.id IS NULL
        """).fetchall()
        if orphan_events:
            issues.append(f"孤儿事件(无实体关联): {len(orphan_events)} 个")
        
        # 2. 孤儿实体（无事件关联）
        orphan_entities = self.conn.execute("""
            SELECT en.id, en.name FROM entities en
            LEFT JOIN event_entities ee ON ee.entity_id = en.id
            WHERE ee.id IS NULL
        """).fetchall()
        if orphan_entities:
            issues.append(f"孤儿实体(无事件关联): {len(orphan_entities)} 个")
        
        # 3. FTS5 一致性
        event_count = self.conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
        fts_count = self.conn.execute("SELECT COUNT(*) as c FROM fts_events").fetchone()["c"]
        if event_count != fts_count:
            issues.append(f"FTS5不一致: events={event_count}, fts={fts_count}")
        
        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "event_count": event_count,
            "entity_count": self.conn.execute("SELECT COUNT(*) as c FROM entities").fetchone()["c"],
            "link_count": self.conn.execute("SELECT COUNT(*) as c FROM event_entities").fetchone()["c"],
        }


# ---------------------------------------------------------------------------
# 便捷函数 — 从 TU-8 现有文件系统自动构建
# ---------------------------------------------------------------------------

def build_from_workspace(workspace_dir: str, db_path: str = None) -> KnowledgeGraphDB:
    """从 TU-8 workspace 目录自动构建知识图谱
    
    扫描：
      - knowledge/ 目录下的 .md 文件 → chunks
      - memory/ 目录下的 .md 文件 → events
      - _agent_memory/06_knowledge_graph/*.json → 迁移
    """
    workspace = Path(workspace_dir)
    if db_path is None:
        db_path = str(workspace / "knowledge_graph.db")
    
    kg = KnowledgeGraphDB(db_path)
    
    # 1. 迁移旧 JSON 数据
    json_dir = workspace / "knowledge" / "TU-8" / "_agent_memory" / "06_knowledge_graph"
    if json_dir.exists():
        kg.migrate_from_json(str(json_dir))
    
    # 2. 扫描 memory/ 目录
    memory_dir = workspace / "memory"
    if memory_dir.exists():
        for md_file in memory_dir.rglob("*.md"):
            try:
                # 多编码容错
                content = None
                for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin1']:
                    try:
                        content = md_file.read_text(encoding=enc)
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        logger.debug("(UnicodeDecodeError, UnicodeError) suppressed", exc_info=True)
                        continue
                if content is None:
                    content = md_file.read_text(encoding='utf-8', errors='replace')
                title = md_file.stem
                # 提取关键词：取前5个非停用词
                words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z_]+', content[:500])
                keywords = list(dict.fromkeys(words))[:5]
                
                evt_id = kg.add_event(
                    title=title,
                    content=content[:2000],  # 截断
                    category="memory",
                    keywords=keywords,
                    source_id="memory",
                )
                
                # 自动抽取实体：文件名 + 关键词
                ent_id = kg.add_entity(
                    name=title,
                    entity_type="memory_file",
                    description=f"记忆文件: {md_file.relative_to(workspace)}",
                    source_id="memory",
                )
                kg.link_event_entity(evt_id, ent_id)
                
            except Exception as e:
                logger.warning(f"扫描 memory 跳过: {md_file.name} | {e}")

    # 3. 扫描 knowledge/ 目录
    knowledge_dir = workspace / "knowledge" / "TU-8"
    if knowledge_dir.exists():
        for md_file in knowledge_dir.rglob("*.md"):
            if md_file.name in ("index.md", "KNOWLEDGE_GRAPH.md"):
                continue
            try:
                # 多编码容错
                content = None
                for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin1']:
                    try:
                        content = md_file.read_text(encoding=enc)
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        logger.debug("(UnicodeDecodeError, UnicodeError) suppressed", exc_info=True)
                        continue
                if content is None:
                    content = md_file.read_text(encoding='utf-8', errors='replace')
                title = md_file.stem
                
                cid = kg.add_chunk(
                    heading=title,
                    content=content[:2000],
                    source_id="knowledge",
                )
                
                ent_id = kg.add_entity(
                    name=title,
                    entity_type="knowledge_file",
                    description=str(md_file.relative_to(knowledge_dir)),
                    source_id="knowledge",
                )
                
                # 修复：knowledge/ 目录也建 event-entity 关联
                # 创建知识文件事件
                keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z_]+', content[:500])
                keywords = list(dict.fromkeys(keywords))[:5]
                evt_id = kg.add_event(
                    title=f"[知识] {title}",
                    content=content[:2000],
                    category="knowledge",
                    keywords=keywords,
                    source_id="knowledge",
                )
                kg.link_event_entity(evt_id, ent_id)
            except Exception as e:
                logger.warning(f"扫描 knowledge 跳过: {md_file.name} | {e}")

    logger.info(f"[SAG-Lite] 构建完成: {kg.stats()}")
    return kg


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG,
                       format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    
    workspace = r"C:\Users\qq366410837\.qclaw\workspace"
    
    if len(sys.argv) > 1:
        workspace = sys.argv[1]
    
    print(f"从 workspace 构建知识图谱: {workspace}")
    kg = build_from_workspace(workspace)
    
    print("\n=== 数据库统计 ===")
    print(json.dumps(kg.stats(), indent=2))
    
    print("\n=== 完整性校验 ===")
    print(json.dumps(kg.verify_integrity(), indent=2, ensure_ascii=False))
    
    # 测试检索
    print("\n=== 检索测试 ===")
    for query in ["钢印", "梦境", "记忆系统", "安全"]:
        result = kg.search_multi(query, top_k=3)
        print(f"\n查询: '{query}'")
        print(f"  步骤: {result['trace']['steps']}")
        print(f"  耗时: {result['trace']['timings'].get('total', '?')}s")
        for i, r in enumerate(result["results"][:3]):
            print(f"  [{i}] {r.get('title', '?')[:50]} (score={r.get('score', 0):.3f})")
