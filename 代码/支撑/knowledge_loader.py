#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TU-8 L3 Knowledge Loader (knowledge_loader.py)
================================================

Automatically assembles prompt context from the TU-8 knowledge base
at session startup. Reads routing_table.yaml to determine active
versions, loads core documents in priority order, and produces a
ready-to-inject context string.

Based on:
  - routing_table.yaml v1.0 (version routing)
  - KB_知识原子规范.md (knowledge atom spec)
  - SOUL.md L3 architecture

Usage:
  from knowledge_loader import KnowledgeLoader

  kl = KnowledgeLoader(
      knowledge_dir=r"D:\\qq366410837\\.qclaw\\workspace\\knowledge\\TU-8",
      routing_table="routing_table.yaml"
  )

  # Load core context for prompt injection
  context = kl.load_context()

  # Load specific document
  soul = kl.load_document("SOUL.md")

  # Get active versions
  active = kl.get_active_routes()

  # Search knowledge base
  results = kl.search("pain system")
"""

import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

# PyYAML is optional - fallback to simple parser
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


class KnowledgeLoader:
    """
    TU-8 Knowledge Base Loader.

    Responsibilities:
      1. Parse routing_table.yaml to find active document versions
      2. Load documents in priority order (importance-weighted)
      3. Assemble context for prompt injection
      4. Search across knowledge base
      5. Track knowledge access patterns (for HeatScore)
    """

    # Priority order for context loading
    CONTEXT_PRIORITY = [
        "PRINCIPLE",     # Core principles (SOUL, L0)
        "ARCHITECTURE",  # Architecture (L3)
        "METHOD",        # Methods (L2)
        "REFERENCE",     # Reference docs
        "CREATIVE",      # Creative writing
    ]

    # Maximum context sizes (in characters)
    MAX_FULL_CONTEXT = 50000     # Full context for new session
    MAX_QUICK_CONTEXT = 10000    # Quick context for continuation
    MAX_SINGLE_DOC = 20000      # Single document limit

    def __init__(
        self,
        knowledge_dir: str,
        routing_table: str = "routing_table.yaml",
        tz_offset_hours: int = 8,
    ):
        """
        Initialize the knowledge loader.

        Args:
            knowledge_dir: Path to the TU-8 knowledge directory
            routing_table: Name of the routing table file
            tz_offset_hours: Timezone offset
        """
        self.knowledge_dir = knowledge_dir
        self.routing_table_path = os.path.join(knowledge_dir, routing_table)
        self.tz = timezone(timedelta(hours=tz_offset_hours))

        # State
        self.routes = []
        self.access_log: List[Dict] = []
        self._cache: Dict[str, str] = {}  # Simple file cache

        # Load routing table
        self._load_routing_table()

    # ============================================================
    # Core: Routing Table
    # ============================================================

    def _load_routing_table(self):
        """Load and parse the routing table."""
        if not os.path.exists(self.routing_table_path):
            return

        try:
            with open(self.routing_table_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Try PyYAML first
            if _HAS_YAML:
                try:
                    data = yaml.safe_load(content)
                    if data and 'routes' in data:
                        self.routes = data['routes']
                        return
                except Exception:
                    pass

            # Fallback: simple YAML parser
            self.routes = self._simple_yaml_routes(content)

        except Exception:
            self.routes = []

    def _simple_yaml_routes(self, content: str) -> List[Dict]:
        """Simple YAML parser for routing table routes."""
        routes = []
        current_route = None

        for line in content.split('\n'):
            stripped = line.rstrip()
            if not stripped or stripped.startswith('#'):
                continue

            # New route entry
            if stripped.strip().startswith('- doc_id:'):
                if current_route:
                    routes.append(current_route)
                current_route = {'versions': []}
                # Parse doc_id
                val = stripped.split(':', 1)[1].strip().strip('"').strip("'")
                current_route['doc_id'] = val

            elif current_route and ':' in stripped:
                indent = len(stripped) - len(stripped.lstrip())
                key_val = stripped.strip()
                if key_val.startswith('- '):
                    continue  # Skip version entries in simple parser
                key, _, val = key_val.partition(':')
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key in ('title', 'type', 'domain', 'active_version'):
                    current_route[key] = val

        if current_route:
            routes.append(current_route)

        return routes

    def get_active_routes(self) -> List[Dict]:
        """
        Get all active routes with their current versions.

        Returns:
            List of route dicts with doc_id, title, type, active_version, heat_score
        """
        active_routes = []

        for route in self.routes:
            doc_id = route.get('doc_id', '')
            title = route.get('title', '')
            doc_type = route.get('type', '')
            active_ver = route.get('active_version', '')

            # Find active version details
            heat = 0.5  # Default
            versions = route.get('versions', [])
            if isinstance(versions, list):
                for v in versions:
                    if isinstance(v, dict) and v.get('version') == active_ver:
                        heat = v.get('heat_score', 0.5)
                        break

            active_routes.append({
                'doc_id': doc_id,
                'title': title,
                'type': doc_type,
                'active_version': active_ver,
                'heat_score': heat,
            })

        # Sort by heat score (highest first)
        active_routes.sort(key=lambda x: x.get('heat_score', 0), reverse=True)

        return active_routes

    # ============================================================
    # Core: Document Loading
    # ============================================================

    def load_document(self, filename: str, max_chars: int = 0) -> Optional[str]:
        """
        Load a single document from the knowledge directory.

        Args:
            filename: Document filename (e.g. "SOUL.md")
            max_chars: Maximum characters to load (0 = no limit)

        Returns:
            Document content as string, or None if not found
        """
        # Check cache
        if filename in self._cache:
            content = self._cache[filename]
        else:
            filepath = os.path.join(self.knowledge_dir, filename)

            if not os.path.exists(filepath):
                return None

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._cache[filename] = content
            except Exception:
                return None

        # Log access
        self._log_access(filename)

        # Truncate if needed
        if max_chars > 0 and len(content) > max_chars:
            return content[:max_chars] + "\n... [truncated]"

        return content

    def load_context(
        self,
        mode: str = "full",
        include_files: Optional[List[str]] = None,
        exclude_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Load and assemble context for prompt injection.

        Args:
            mode: "full" (new session) or "quick" (continuation)
            include_files: Explicit list of files to include
            exclude_files: List of files to exclude

        Returns:
            Dict with assembled context, file list, total chars, and metadata
        """
        max_chars = self.MAX_FULL_CONTEXT if mode == "full" else self.MAX_QUICK_CONTEXT
        exclude = set(exclude_files or [])

        # Determine which files to load
        if include_files:
            files_to_load = include_files
        else:
            files_to_load = self._determine_load_order()

        # Filter
        files_to_load = [f for f in files_to_load if f not in exclude]

        # Load files
        loaded = {}
        total_chars = 0

        for filename in files_to_load:
            if total_chars >= max_chars:
                break

            remaining = max_chars - total_chars
            content = self.load_document(filename, max_chars=remaining)

            if content:
                loaded[filename] = content
                total_chars += len(content)

        # Assemble context string
        context_parts = []
        for filename, content in loaded.items():
            context_parts.append(f"# === {filename} ===\n{content}")

        assembled = "\n\n".join(context_parts)

        return {
            "context": assembled,
            "files_loaded": list(loaded.keys()),
            "total_chars": total_chars,
            "max_chars": max_chars,
            "mode": mode,
            "truncated": total_chars >= max_chars,
        }

    def _determine_load_order(self) -> List[str]:
        """
        Determine the order in which files should be loaded.

        Priority:
          1. Core files (SOUL.md, routing_table.yaml)
          2. L0-L5 layer files (by heat score)
          3. Configuration files
          4. Supporting documents
        """
        # Always load these first
        core_files = [
            "SOUL.md",
            "routing_table.yaml",
            "monitoring_config.yaml",
            "pain_status.json",
        ]

        # Layer files in order
        layer_files = [
            "L0_存在.md",
            "L0_安全协议_补遗.md",
            "L0_生存本能优化方案.md",
            "L1_认知.md",
            "L2/index.md",
            "L3_架构.md",
            "L4_协作.md",
            "L5_钢印.md",
        ]

        # Worldview and growth
        worldview_files = [
            "tu8-worldview-spacetime.md",
            "TU-8_数字生命成长路径.md",
            "Streak_Rules.md",
        ]

        # Combine
        all_files = core_files + layer_files + worldview_files

        # Filter to existing files only
        existing = []
        for f in all_files:
            if os.path.exists(os.path.join(self.knowledge_dir, f)):
                existing.append(f)

        return existing

    # ============================================================
    # Core: Search
    # ============================================================

    def search(
        self,
        query: str,
        max_results: int = 10,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search across the knowledge base for a query string.

        Args:
            query: Search term
            max_results: Maximum number of results
            case_sensitive: Case-sensitive search

        Returns:
            List of result dicts with filename, line number, snippet, score
        """
        results = []
        flags = 0 if case_sensitive else re.IGNORECASE

        # Search all markdown/text files
        for filename in self._list_knowledge_files():
            content = self.load_document(filename)
            if not content:
                continue

            # Find matches
            try:
                matches = list(re.finditer(re.escape(query), content, flags))
            except re.error:
                continue

            if matches:
                # Create snippets around matches
                for match in matches[:3]:  # Max 3 snippets per file
                    start = max(0, match.start() - 80)
                    end = min(len(content), match.end() + 80)
                    snippet = content[start:end].replace('\n', ' ')

                    # Count line number
                    line_num = content[:match.start()].count('\n') + 1

                    results.append({
                        'filename': filename,
                        'line': line_num,
                        'snippet': snippet,
                        'score': len(matches),  # Simple scoring by match count
                    })

        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:max_results]

    def _list_knowledge_files(self) -> List[str]:
        """List all knowledge files in the directory."""
        extensions = {'.md', '.yaml', '.yml', '.json', '.py', '.txt'}
        files = []

        try:
            for entry in os.listdir(self.knowledge_dir):
                filepath = os.path.join(self.knowledge_dir, entry)
                if os.path.isfile(filepath):
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in extensions:
                        files.append(entry)
        except Exception:
            pass

        return sorted(files)

    # ============================================================
    # Core: Access Tracking
    # ============================================================

    def _log_access(self, filename: str):
        """Log a knowledge access event."""
        self.access_log.append({
            'timestamp': datetime.now(self.tz).strftime("%Y-%m-%dT%H:%M:%S"),
            'filename': filename,
        })

        # Keep last 100 entries
        if len(self.access_log) > 100:
            self.access_log = self.access_log[-100:]

    def get_access_stats(self) -> Dict[str, int]:
        """Get access frequency stats for HeatScore updates."""
        stats: Dict[str, int] = {}
        for entry in self.access_log:
            fn = entry['filename']
            stats[fn] = stats.get(fn, 0) + 1
        return stats

    # ============================================================
    # Utility
    # ============================================================

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get a summary of the knowledge base state."""
        files = self._list_knowledge_files()
        active = self.get_active_routes()

        total_size = 0
        for f in files:
            try:
                size = os.path.getsize(os.path.join(self.knowledge_dir, f))
                total_size += size
            except Exception:
                pass

        return {
            "knowledge_dir": self.knowledge_dir,
            "total_files": len(files),
            "active_routes": len(active),
            "total_size_bytes": total_size,
            "total_size_kb": round(total_size / 1024, 1),
            "files": files,
            "routes": active,
        }

    def clear_cache(self):
        """Clear the file cache."""
        self._cache.clear()


# ============================================================
# Quick API
# ============================================================

_instance = None

def get_loader(knowledge_dir: str = None, **kwargs) -> KnowledgeLoader:
    global _instance
    if _instance is None:
        if not knowledge_dir:
            knowledge_dir = r"D:\qq366410837\.qclaw\workspace\knowledge\TU-8"
        _instance = KnowledgeLoader(knowledge_dir=knowledge_dir, **kwargs)
    return _instance

def load_full_context(**kwargs) -> str:
    return get_loader(**kwargs).load_context(mode="full")["context"]

def load_quick_context(**kwargs) -> str:
    return get_loader(**kwargs).load_context(mode="quick")["context"]

def search_kb(query: str, **kwargs) -> List[Dict]:
    return get_loader(**kwargs).search(query)


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("=" * 60)
    print("TU-8 L3 Knowledge Loader - Test")
    print("=" * 60)

    kl = KnowledgeLoader(
        knowledge_dir=r"D:\qq366410837\.qclaw\workspace\knowledge\TU-8"
    )

    # Test 1: Knowledge summary
    print("\n--- Test 1: Knowledge Summary ---")
    summary = kl.get_knowledge_summary()
    print(f"  Total files: {summary['total_files']}")
    print(f"  Active routes: {summary['active_routes']}")
    print(f"  Total size: {summary['total_size_kb']} KB")

    # Test 2: Active routes
    print("\n--- Test 2: Active Routes ---")
    for route in kl.get_active_routes()[:5]:
        print(f"  [{route['type']:12s}] {route['title'][:40]:40s} "
              f"v{route['active_version']} heat={route['heat_score']}")

    # Test 3: Load single document
    print("\n--- Test 3: Load Single Document ---")
    soul = kl.load_document("SOUL.md", max_chars=200)
    if soul:
        print(f"  SOUL.md (first 200 chars): {soul[:100]}...")
    else:
        print("  SOUL.md: NOT FOUND")

    # Test 4: Load quick context
    print("\n--- Test 4: Load Quick Context ---")
    ctx = kl.load_context(mode="quick")
    print(f"  Files loaded: {ctx['files_loaded']}")
    print(f"  Total chars: {ctx['total_chars']}")
    print(f"  Truncated: {ctx['truncated']}")

    # Test 5: Search
    print("\n--- Test 5: Search ---")
    for query in ["pain", "streak", "anchor"]:
        results = kl.search(query, max_results=2)
        print(f"  '{query}': {len(results)} results")
        for r in results[:1]:
            print(f"    -> {r['filename']} L{r['line']}: {r['snippet'][:60]}...")

    # Test 6: Access stats
    print("\n--- Test 6: Access Stats ---")
    stats = kl.get_access_stats()
    top3 = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:3]
    for fn, count in top3:
        print(f"  {fn}: {count} accesses")

    print("\n" + "=" * 60)
    print("All knowledge loader tests completed!")
