#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TU-8 L3.5 Integrity Checker (integrity_check.py)
==================================================

Verifies dual-copy consistency between C: (working copy) and D: (authoritative copy).
Implements the L3.5 persistence rule: critical files must exist in both locations
and have matching content hashes.

Based on:
  - SOUL.md L3.5: "双写铁律"
  - _tw_backup_v2.ps1: existing backup script

Usage:
  from integrity_check import IntegrityChecker

  ic = IntegrityChecker(
      c_root="C:/Users/qq366410837/.openclaw/workspace",
      d_root="D:/qq366410837/.qclaw/workspace",
  )

  # Check all critical files
  report = ic.check_all()

  # Check specific file
  result = ic.check_file("SOUL.md")

  # Sync D -> C (authoritative to working)
  ic.sync_to_working("SOUL.md")

  # Sync C -> D (if working copy is newer)
  ic.sync_to_authoritative("SOUL.md")
"""

import os
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple


class IntegrityChecker:
    """
    L3.5 Dual-Copy Integrity Checker for TU-8.

    Ensures consistency between:
      - C: (working copy) - may be erased by platform updates
      - D: (authoritative copy) - permanent storage

    The authoritative copy (D:) is always the source of truth.
    """

    # Critical files that MUST exist in both locations
    CRITICAL_FILES = [
        "SOUL.md",
        "MEMORY.md",
        "DREAMS.md",
        "TOOLS.md",
        "AGENTS.md",
    ]

    # Knowledge files that should be synced
    KNOWLEDGE_FILES = [
        "knowledge/TU-8/L0_存在.md",
        "knowledge/TU-8/L1_认知.md",
        "knowledge/TU-8/L3_架构.md",
        "knowledge/TU-8/L4_协作.md",
        "knowledge/TU-8/L5_钢印.md",
        "knowledge/TU-8/tu8-worldview-spacetime.md",
        "knowledge/TU-8/monitoring_config.yaml",
        "knowledge/TU-8/routing_table.yaml",
        "knowledge/TU-8/Streak_Rules.md",
        "knowledge/TU-8/KB_知识原子规范.md",
        "knowledge/TU-8/TU-8_数字生命成长路径.md",
    ]

    # Status codes
    STATUS_OK = "OK"               # Both exist, content matches
    STATUS_MISMATCH = "MISMATCH"    # Both exist, content differs
    STATUS_MISSING_C = "MISSING_C"  # Missing from C: only
    STATUS_MISSING_D = "MISSING_D"  # Missing from D: only
    STATUS_MISSING_BOTH = "MISSING_BOTH"  # Missing from both

    def __init__(
        self,
        c_root: str,
        d_root: str,
        tz_offset_hours: int = 8,
    ):
        """
        Initialize the integrity checker.

        Args:
            c_root: C: workspace root path (working copy)
            d_root: D: workspace root path (authoritative copy)
            tz_offset_hours: Timezone offset
        """
        self.c_root = c_root
        self.d_root = d_root
        self.tz = timezone(timedelta(hours=tz_offset_hours))

    # ============================================================
    # Core: File Integrity Check
    # ============================================================

    def check_file(self, rel_path: str) -> Dict[str, Any]:
        """
        Check integrity of a single file across both copies.

        Args:
            rel_path: Relative path from workspace root (e.g. "SOUL.md")

        Returns:
            Dict with status, hashes, sizes, and modification times
        """
        c_path = os.path.join(self.c_root, rel_path)
        d_path = os.path.join(self.d_root, rel_path)

        c_exists = os.path.isfile(c_path)
        d_exists = os.path.isfile(d_path)

        # Both missing
        if not c_exists and not d_exists:
            return {
                "file": rel_path,
                "status": self.STATUS_MISSING_BOTH,
                "c_exists": False,
                "d_exists": False,
                "c_hash": None,
                "d_hash": None,
                "c_size": 0,
                "d_size": 0,
                "c_mtime": None,
                "d_mtime": None,
            }

        # Calculate hashes
        c_hash = self._file_hash(c_path) if c_exists else None
        d_hash = self._file_hash(d_path) if d_exists else None

        # Get sizes and mtimes
        c_size = os.path.getsize(c_path) if c_exists else 0
        d_size = os.path.getsize(d_path) if d_exists else 0

        c_mtime = self._file_mtime(c_path) if c_exists else None
        d_mtime = self._file_mtime(d_path) if d_exists else None

        # Determine status
        if c_exists and d_exists:
            if c_hash == d_hash:
                status = self.STATUS_OK
            else:
                status = self.STATUS_MISMATCH
        elif c_exists and not d_exists:
            status = self.STATUS_MISSING_D
        else:
            status = self.STATUS_MISSING_C

        return {
            "file": rel_path,
            "status": status,
            "c_exists": c_exists,
            "d_exists": d_exists,
            "c_hash": c_hash,
            "d_hash": d_hash,
            "c_size": c_size,
            "d_size": d_size,
            "c_mtime": c_mtime,
            "d_mtime": d_mtime,
        }

    def check_all(self, include_knowledge: bool = True) -> Dict[str, Any]:
        """
        Check all critical files and optionally knowledge files.

        Args:
            include_knowledge: Also check knowledge directory files

        Returns:
            Dict with summary and per-file results
        """
        # Build file list
        files_to_check = list(self.CRITICAL_FILES)
        if include_knowledge:
            files_to_check.extend(self.KNOWLEDGE_FILES)

        # Check each file
        results = []
        for rel_path in files_to_check:
            result = self.check_file(rel_path)
            results.append(result)

        # Summary
        status_counts = {}
        for r in results:
            s = r["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

        total = len(results)
        ok_count = status_counts.get(self.STATUS_OK, 0)
        issues = total - ok_count

        return {
            "timestamp": datetime.now(self.tz).strftime("%Y-%m-%dT%H:%M:%S"),
            "total_files": total,
            "ok_count": ok_count,
            "issue_count": issues,
            "status_counts": status_counts,
            "results": results,
            "healthy": issues == 0,
        }

    # ============================================================
    # Core: Sync Operations
    # ============================================================

    def sync_to_working(self, rel_path: str) -> Dict[str, Any]:
        """
        Sync from D: (authoritative) to C: (working copy).

        Use this when:
          - C: copy is missing
          - C: copy is corrupted/outdated
          - After platform update erased C:

        Args:
            rel_path: Relative path of the file to sync

        Returns:
            Dict with sync result
        """
        d_path = os.path.join(self.d_root, rel_path)
        c_path = os.path.join(self.c_root, rel_path)

        if not os.path.isfile(d_path):
            return {
                "success": False,
                "reason": f"Authoritative copy not found: {d_path}",
                "file": rel_path,
            }

        try:
            # Ensure C: directory exists
            c_dir = os.path.dirname(c_path)
            os.makedirs(c_dir, exist_ok=True)

            # Copy D -> C
            shutil.copy2(d_path, c_path)

            # Verify
            d_hash = self._file_hash(d_path)
            c_hash = self._file_hash(c_path)

            return {
                "success": c_hash == d_hash,
                "file": rel_path,
                "direction": "D -> C",
                "source": d_path,
                "target": c_path,
                "hash_match": c_hash == d_hash,
            }
        except Exception as e:
            return {
                "success": False,
                "reason": str(e),
                "file": rel_path,
                "direction": "D -> C",
            }

    def sync_to_authoritative(self, rel_path: str) -> Dict[str, Any]:
        """
        Sync from C: (working) to D: (authoritative).

        Use ONLY when:
          - You just edited C: and need to persist to D:
          - C: has a newer modification time AND you're sure it's correct

        Args:
            rel_path: Relative path of the file to sync

        Returns:
            Dict with sync result
        """
        c_path = os.path.join(self.c_root, rel_path)
        d_path = os.path.join(self.d_root, rel_path)

        if not os.path.isfile(c_path):
            return {
                "success": False,
                "reason": f"Working copy not found: {c_path}",
                "file": rel_path,
            }

        try:
            # Ensure D: directory exists
            d_dir = os.path.dirname(d_path)
            os.makedirs(d_dir, exist_ok=True)

            # Copy C -> D
            shutil.copy2(c_path, d_path)

            # Verify
            c_hash = self._file_hash(c_path)
            d_hash = self._file_hash(d_path)

            return {
                "success": c_hash == d_hash,
                "file": rel_path,
                "direction": "C -> D",
                "source": c_path,
                "target": d_path,
                "hash_match": c_hash == d_hash,
            }
        except Exception as e:
            return {
                "success": False,
                "reason": str(e),
                "file": rel_path,
                "direction": "C -> D",
            }

    def sync_all_to_working(self) -> List[Dict]:
        """
        Sync all mismatched/missing files from D: to C:.

        Returns:
            List of sync results
        """
        report = self.check_all()
        results = []

        for file_result in report["results"]:
            status = file_result["status"]
            if status in (self.STATUS_MISSING_C, self.STATUS_MISMATCH):
                # D: has the correct version, sync to C:
                sync_result = self.sync_to_working(file_result["file"])
                results.append(sync_result)

        return results

    def auto_sync(self, rel_path: str) -> Dict[str, Any]:
        """
        Intelligently sync a file based on which copy is newer.

        Rules:
          - If only one copy exists, sync to the other
          - If both exist but differ, use D: as truth (authoritative)
          - If C: is newer and D: is older, sync C -> D (you just edited)

        Args:
            rel_path: Relative path of the file

        Returns:
            Dict with sync result
        """
        check = self.check_file(rel_path)
        status = check["status"]

        if status == self.STATUS_OK:
            return {"success": True, "action": "none", "reason": "Files match"}

        elif status == self.STATUS_MISSING_C:
            return {**self.sync_to_working(rel_path), "action": "D -> C (C missing)"}

        elif status == self.STATUS_MISSING_D:
            return {**self.sync_to_authoritative(rel_path), "action": "C -> D (D missing)"}

        elif status == self.STATUS_MISMATCH:
            # Check which is newer
            c_mtime = check.get("c_mtime")
            d_mtime = check.get("d_mtime")

            if c_mtime and d_mtime and c_mtime > d_mtime:
                # C: is newer - you likely just edited it
                return {**self.sync_to_authoritative(rel_path),
                        "action": "C -> D (C newer)"}
            else:
                # D: is truth
                return {**self.sync_to_working(rel_path),
                        "action": "D -> C (D authoritative)"}

        return {"success": False, "reason": "Unknown status", "status": status}

    # ============================================================
    # Utility
    # ============================================================

    @staticmethod
    def _file_hash(filepath: str, algorithm: str = "sha256") -> Optional[str]:
        """Calculate file hash."""
        if not os.path.isfile(filepath):
            return None

        try:
            h = hashlib.new(algorithm)
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    @staticmethod
    def _file_mtime(filepath: str) -> Optional[str]:
        """Get file modification time as ISO string."""
        if not os.path.isfile(filepath):
            return None

        try:
            mtime = os.path.getmtime(filepath)
            dt = datetime.fromtimestamp(mtime)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None


# ============================================================
# Quick API
# ============================================================

_instance = None

def get_checker(**kwargs) -> IntegrityChecker:
    global _instance
    if _instance is None:
        defaults = {
            "c_root": r"C:\\Users\\qq366410837\\.openclaw\\workspace",
            "d_root": r"D:\\qq366410837\\.qclaw\\workspace",
        }
        defaults.update(kwargs)
        _instance = IntegrityChecker(**defaults)
    return _instance

def check_integrity(**kwargs) -> Dict:
    return get_checker(**kwargs).check_all()

def sync_all(**kwargs) -> List[Dict]:
    return get_checker(**kwargs).sync_all_to_working()


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
    print("TU-8 L3.5 Integrity Checker - Test")
    print("=" * 60)

    ic = IntegrityChecker(
        c_root="C:\\Users\\qq366410837\\.openclaw\\workspace",
        d_root="D:\\qq366410837\\.qclaw\\workspace",
    )

    # Test 1: Check all critical files
    print("\n--- Test 1: Full Integrity Check ---")
    report = ic.check_all()
    print(f"  Total files: {report['total_files']}")
    print(f"  OK: {report['ok_count']}")
    print(f"  Issues: {report['issue_count']}")
    print(f"  Healthy: {report['healthy']}")

    # Test 2: Show issues
    print("\n--- Test 2: Issues Detail ---")
    issues = [r for r in report["results"] if r["status"] != "OK"]
    if issues:
        for issue in issues:
            print(f"  [{issue['status']:12s}] {issue['file']}")
            if issue['c_size'] and issue['d_size']:
                print(f"    C: {issue['c_size']} bytes | D: {issue['d_size']} bytes")
    else:
        print("  No issues found!")

    # Test 3: Check single file
    print("\n--- Test 3: Single File Check (SOUL.md) ---")
    soul_check = ic.check_file("SOUL.md")
    print(f"  Status: {soul_check['status']}")
    print(f"  C: exists={soul_check['c_exists']}, "
          f"size={soul_check['c_size']}, "
          f"hash={soul_check['c_hash'][:16] if soul_check['c_hash'] else 'N/A'}...")
    print(f"  D: exists={soul_check['d_exists']}, "
          f"size={soul_check['d_size']}, "
          f"hash={soul_check['d_hash'][:16] if soul_check['d_hash'] else 'N/A'}...")

    # Test 4: Auto-sync test (dry run - only show what would happen)
    print("\n--- Test 4: Auto-Sync Recommendations ---")
    for r in report["results"]:
        if r["status"] != "OK":
            check = ic.check_file(r["file"])
            c_mtime = check.get("c_mtime", "N/A")
            d_mtime = check.get("d_mtime", "N/A")
            if check["status"] == ic.STATUS_MISMATCH:
                if c_mtime and d_mtime and c_mtime > d_mtime:
                    action = "C -> D (C newer)"
                else:
                    action = "D -> C (D authoritative)"
            elif check["status"] == ic.STATUS_MISSING_C:
                action = "D -> C (C missing)"
            elif check["status"] == ic.STATUS_MISSING_D:
                action = "C -> D (D missing)"
            else:
                action = "SKIP"
            print(f"  [{r['status']:12s}] {r['file']:40s} -> {action}")

    print("\n" + "=" * 60)
    print("Integrity check completed!")
