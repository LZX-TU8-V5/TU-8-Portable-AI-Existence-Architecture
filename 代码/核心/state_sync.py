#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TU-8 L3.5 State Sync (state_sync.py)
======================================

Crash-recovery state persistence synchronizer. Ensures that after
any crash or interruption, 100% of TU-8 state can be recovered.

Core principle (from SOUL.md L3.5):
  "崩溃后100%回写" — After crash, full state recovery.

Strategy:
  1. Pre-write: save state snapshot BEFORE any critical operation
  2. Atomic write: write to temp file, then rename (crash-safe)
  3. Dual-write: persist to both C: and D: copies
  4. Post-verify: confirm both copies match after write
  5. Crash recovery: on startup, detect and restore best state

Based on:
  - SOUL.md L3.5 persistence rules
  - monitoring_config.yaml state_sync section
  - integrity_check.py dual-copy verification

Usage:
  from state_sync import StateSync

  ss = StateSync(
      c_root="C:/Users/qq366410837/.openclaw/workspace",
      d_root="D:/qq366410837/.qclaw/workspace",
  )

  # Save state before critical operation
  ss.save_state("pain_status.json", {"pain_level": 0, "quota": 800})

  # Load state with crash recovery
  state = ss.load_state("pain_status.json")

  # Full recovery check at startup
  report = ss.recover_all()
"""

import os
import json
import hashlib
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple


class StateSync:
    """
    L3.5 State Persistence & Crash Recovery for TU-8.

    Guarantees:
      - Atomic writes (crash during write = old state preserved)
      - Dual-copy persistence (C: + D:)
      - Crash recovery (best state wins on next startup)
      - Pre-operation snapshots (undo capability)
    """

    # State files that MUST be synced
    STATE_FILES = [
        "pain_status.json",
        "streak_status.json",
        "sleep_status.json",
    ]

    # Max snapshots to keep per file
    MAX_SNAPSHOTS = 10

    # Snapshot directory name
    SNAPSHOT_DIR = "_snapshots"

    def __init__(
        self,
        c_root: str,
        d_root: str,
        tz_offset_hours: int = 8,
    ):
        """
        Initialize state sync.

        Args:
            c_root: C: workspace root (working copy)
            d_root: D: workspace root (authoritative copy)
            tz_offset_hours: Timezone offset
        """
        self.c_root = c_root
        self.d_root = d_root
        self.tz = timezone(timedelta(hours=tz_offset_hours))

    # ============================================================
    # Core: Atomic Write
    # ============================================================

    def _atomic_write(self, filepath: str, content: str) -> bool:
        """
        Write file atomically using temp file + rename.

        This ensures that if a crash happens during write,
        the old file is still intact.

        Args:
            filepath: Target file path
            content: Content to write

        Returns:
            True if write succeeded
        """
        try:
            # Write to temp file first
            dir_name = os.path.dirname(filepath)
            os.makedirs(dir_name, exist_ok=True)

            # Use temp file in same directory (same filesystem for rename)
            fd, temp_path = tempfile.mkstemp(
                dir=dir_name,
                prefix=".tmp_",
                suffix=".json"
            )

            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk

                # Rename temp to target (atomic on same filesystem)
                os.replace(temp_path, filepath)
                return True

            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise

        except Exception:
            return False

    # ============================================================
    # Core: Dual Write
    # ============================================================

    def save_state(
        self,
        rel_path: str,
        data: Any,
        pre_snapshot: bool = True,
    ) -> Dict[str, Any]:
        """
        Save state to both C: and D: with atomic writes.

        Args:
            rel_path: Relative path from workspace root
            data: Data to save (will be JSON-serialized)
            pre_snapshot: Whether to save a pre-operation snapshot

        Returns:
            Dict with write results for both copies
        """
        # Serialize
        content = json.dumps(data, indent=2, ensure_ascii=False)

        # Add metadata
        meta = {
            "_meta": {
                "saved_at": datetime.now(self.tz).strftime("%Y-%m-%dT%H:%M:%S"),
                "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                "version": 1,
            }
        }

        # Merge meta into data if it's a dict
        if isinstance(data, dict):
            save_data = {**data, **meta}
        else:
            save_data = {"data": data, **meta}

        final_content = json.dumps(save_data, indent=2, ensure_ascii=False)

        # Pre-snapshot (save current state before overwriting)
        if pre_snapshot:
            self._save_snapshot(rel_path)

        # Write to both locations
        c_path = os.path.join(self.c_root, rel_path)
        d_path = os.path.join(self.d_root, rel_path)

        c_ok = self._atomic_write(c_path, final_content)
        d_ok = self._atomic_write(d_path, final_content)

        # Verify
        c_hash = self._file_hash(c_path) if c_ok else None
        d_hash = self._file_hash(d_path) if d_ok else None

        expected_hash = hashlib.sha256(final_content.encode()).hexdigest()

        return {
            "file": rel_path,
            "c_written": c_ok,
            "d_written": d_ok,
            "c_verified": c_hash == expected_hash if c_hash else False,
            "d_verified": d_hash == expected_hash if d_hash else False,
            "both_ok": c_ok and d_ok and c_hash == d_hash,
            "content_hash": expected_hash[:16],
        }

    def load_state(
        self,
        rel_path: str,
        default: Any = None,
        crash_recovery: bool = True,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Load state with crash recovery.

        Strategy:
          1. Try loading from D: (authoritative)
          2. Try loading from C: (working)
          3. If both exist but differ, use the one with newer _meta.saved_at
          4. If neither loads, return default

        Args:
            rel_path: Relative path from workspace root
            default: Default value if file doesn't exist
            crash_recovery: Whether to attempt crash recovery

        Returns:
            Tuple of (data, metadata_dict)
        """
        c_path = os.path.join(self.c_root, rel_path)
        d_path = os.path.join(self.d_root, rel_path)

        c_data = self._load_json(c_path)
        d_data = self._load_json(d_path)

        # Both missing
        if c_data is None and d_data is None:
            return default, {"source": "default", "reason": "both_missing"}

        # Only one exists
        if c_data is None:
            return d_data, {"source": "D", "reason": "C_missing"}
        if d_data is None:
            return c_data, {"source": "C", "reason": "D_missing"}

        # Both exist — compare hashes
        c_hash = self._file_hash(c_path)
        d_hash = self._file_hash(d_path)

        if c_hash == d_hash:
            # Content matches — all good
            return d_data, {"source": "D", "reason": "hash_match"}

        if not crash_recovery:
            return d_data, {"source": "D", "reason": "authoritative_default"}

        # Hashes differ — need crash recovery
        # Use the one with newer timestamp
        c_meta = c_data.get("_meta", {})
        d_meta = d_data.get("_meta", {})

        c_time = c_meta.get("saved_at", "")
        d_time = d_meta.get("saved_at", "")

        if c_time > d_time:
            # C: is newer — likely crashed after writing C but before D
            # Sync C -> D to fix
            self._sync_file(c_path, d_path)
            return c_data, {
                "source": "C",
                "reason": "C_newer_crash_recovery",
                "c_time": c_time,
                "d_time": d_time,
                "synced": "C->D",
            }
        else:
            # D: is newer or same — use D as truth
            # Sync D -> C to fix
            self._sync_file(d_path, c_path)
            return d_data, {
                "source": "D",
                "reason": "D_newer_or_equal",
                "c_time": c_time,
                "d_time": d_time,
                "synced": "D->C",
            }

    # ============================================================
    # Core: Snapshots (Undo)
    # ============================================================

    def _save_snapshot(self, rel_path: str) -> bool:
        """
        Save a snapshot of the current file before overwriting.

        Snapshots are stored in _snapshots/ subdirectory with timestamps.
        """
        # Try both locations
        for root in [self.d_root, self.c_root]:
            src = os.path.join(root, rel_path)
            if os.path.isfile(src):
                snap_dir = os.path.join(root, self.SNAPSHOT_DIR)
                os.makedirs(snap_dir, exist_ok=True)

                timestamp = datetime.now(self.tz).strftime("%Y%m%d_%H%M%S")
                basename = os.path.basename(rel_path)
                name, ext = os.path.splitext(basename)
                snap_name = f"{name}_{timestamp}{ext}"
                snap_path = os.path.join(snap_dir, snap_name)

                try:
                    shutil.copy2(src, snap_path)
                    self._prune_snapshots(root, rel_path)
                    return True
                except Exception:
                    pass

        return False

    def _prune_snapshots(self, root: str, rel_path: str):
        """Remove old snapshots beyond MAX_SNAPSHOTS."""
        snap_dir = os.path.join(root, self.SNAPSHOT_DIR)
        basename = os.path.basename(rel_path)
        name, ext = os.path.splitext(basename)

        try:
            snaps = []
            for f in os.listdir(snap_dir):
                if f.startswith(name + "_") and f.endswith(ext):
                    full = os.path.join(snap_dir, f)
                    snaps.append((os.path.getmtime(full), full))

            # Sort newest first
            snaps.sort(reverse=True)

            # Remove old ones
            for _, path in snaps[self.MAX_SNAPSHOTS:]:
                try:
                    os.unlink(path)
                except Exception:
                    pass

        except Exception:
            pass

    def list_snapshots(self, rel_path: str) -> List[Dict[str, Any]]:
        """List available snapshots for a file."""
        basename = os.path.basename(rel_path)
        name, ext = os.path.splitext(basename)
        results = []

        for root in [self.d_root, self.c_root]:
            snap_dir = os.path.join(root, self.SNAPSHOT_DIR)
            if not os.path.isdir(snap_dir):
                continue

            root_label = "D" if "qclaw" in root else "C"

            for f in sorted(os.listdir(snap_dir), reverse=True):
                if f.startswith(name + "_") and f.endswith(ext):
                    full = os.path.join(snap_dir, f)
                    try:
                        size = os.path.getsize(full)
                        mtime = os.path.getmtime(full)
                        dt = datetime.fromtimestamp(mtime)

                        results.append({
                            "filename": f,
                            "path": full,
                            "location": root_label,
                            "size": size,
                            "mtime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        })
                    except Exception:
                        pass

        return results

    def restore_snapshot(
        self,
        rel_path: str,
        snapshot_filename: str,
    ) -> Dict[str, Any]:
        """
        Restore a file from a snapshot.

        Args:
            rel_path: Target file relative path
            snapshot_filename: Snapshot filename

        Returns:
            Dict with restore result
        """
        # Find snapshot
        for root in [self.d_root, self.c_root]:
            snap_path = os.path.join(root, self.SNAPSHOT_DIR, snapshot_filename)
            if os.path.isfile(snap_path):
                # Restore to both C and D
                c_path = os.path.join(self.c_root, rel_path)
                d_path = os.path.join(self.d_root, rel_path)

                c_ok = self._sync_file(snap_path, c_path)
                d_ok = self._sync_file(snap_path, d_path)

                return {
                    "success": c_ok and d_ok,
                    "file": rel_path,
                    "snapshot": snapshot_filename,
                    "c_restored": c_ok,
                    "d_restored": d_ok,
                }

        return {
            "success": False,
            "reason": f"Snapshot not found: {snapshot_filename}",
        }

    # ============================================================
    # Core: Crash Recovery
    # ============================================================

    def recover_all(self) -> Dict[str, Any]:
        """
        Full crash recovery check at startup.

        For each state file:
          1. Check if both copies exist
          2. Compare hashes
          3. Recover best state to both locations
          4. Report status

        Returns:
            Dict with recovery report
        """
        results = []
        recovered = 0
        ok_count = 0

        for rel_path in self.STATE_FILES:
            data, meta = self.load_state(rel_path, crash_recovery=True)

            status = "OK" if meta.get("reason") == "hash_match" else "RECOVERED"
            if status == "RECOVERED":
                recovered += 1
            else:
                ok_count += 1

            results.append({
                "file": rel_path,
                "status": status,
                "source": meta.get("source", "unknown"),
                "reason": meta.get("reason", "unknown"),
                "has_data": data is not None,
            })

        return {
            "timestamp": datetime.now(self.tz).strftime("%Y-%m-%dT%H:%M:%S"),
            "total_files": len(self.STATE_FILES),
            "ok_count": ok_count,
            "recovered_count": recovered,
            "results": results,
            "healthy": recovered == 0,
        }

    # ============================================================
    # Utility
    # ============================================================

    @staticmethod
    def _file_hash(filepath: str) -> Optional[str]:
        """Calculate SHA-256 hash of a file."""
        if not os.path.isfile(filepath):
            return None
        try:
            h = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    @staticmethod
    def _load_json(filepath: str) -> Optional[Any]:
        """Load JSON file, return None on failure."""
        if not os.path.isfile(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def _sync_file(src: str, dst: str) -> bool:
        """Copy file from src to dst with directory creation."""
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            return True
        except Exception:
            return False


# ============================================================
# Quick API
# ============================================================

_instance = None

def get_sync(**kwargs) -> StateSync:
    global _instance
    if _instance is None:
        defaults = {
            "c_root": "C:/Users/qq366410837/.openclaw/workspace",
            "d_root": "D:/qq366410837/.qclaw/workspace",
        }
        defaults.update(kwargs)
        _instance = StateSync(**defaults)
    return _instance

def save(rel_path: str, data: Any, **kwargs) -> Dict:
    return get_sync(**kwargs).save_state(rel_path, data)

def load(rel_path: str, default: Any = None, **kwargs) -> Any:
    data, _ = get_sync(**kwargs).load_state(rel_path, default)
    return data

def recover(**kwargs) -> Dict:
    return get_sync(**kwargs).recover_all()


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
    print("TU-8 L3.5 State Sync - Test")
    print("=" * 60)

    ss = StateSync(
        c_root="C:/Users/qq366410837/.openclaw/workspace",
        d_root="D:/qq366410837/.qclaw/workspace",
    )

    # Test 1: Save state
    print("\n--- Test 1: Save State ---")
    test_data = {
        "pain_level": 0,
        "steady_state": "OK",
        "current_quota": 800,
        "attack_history": [],
    }
    result = ss.save_state("pain_status.json", test_data)
    print(f"  C written: {result['c_written']}, verified: {result['c_verified']}")
    print(f"  D written: {result['d_written']}, verified: {result['d_verified']}")
    print(f"  Both OK: {result['both_ok']}")

    # Test 2: Load state
    print("\n--- Test 2: Load State ---")
    data, meta = ss.load_state("pain_status.json")
    if data:
        print(f"  Source: {meta['source']}")
        print(f"  Reason: {meta['reason']}")
        print(f"  Pain level: {data.get('pain_level', 'N/A')}")
        print(f"  Quota: {data.get('current_quota', 'N/A')}")
    else:
        print("  Failed to load!")

    # Test 3: Crash recovery
    print("\n--- Test 3: Crash Recovery ---")
    report = ss.recover_all()
    print(f"  Total files: {report['total_files']}")
    print(f"  OK: {report['ok_count']}")
    print(f"  Recovered: {report['recovered_count']}")
    print(f"  Healthy: {report['healthy']}")
    for r in report["results"]:
        print(f"  [{r['status']:10s}] {r['file']:25s} from={r['source']}")

    # Test 4: Snapshot list
    print("\n--- Test 4: Snapshot List ---")
    snaps = ss.list_snapshots("pain_status.json")
    print(f"  Available snapshots: {len(snaps)}")
    for s in snaps[:3]:
        print(f"  {s['mtime']} ({s['location']}) {s['size']} bytes")

    # Test 5: Atomic write test
    print("\n--- Test 5: Atomic Write Integrity ---")
    # Write, then immediately verify both copies match
    result2 = ss.save_state("pain_status.json", {
        "pain_level": 5,
        "steady_state": "ALERT",
        "current_quota": 795,
        "attack_history": [{"type": "mild", "time": "2026-05-16T08:45:00"}],
    }, pre_snapshot=True)
    print(f"  Both OK: {result2['both_ok']}")

    # Reload and verify
    data2, meta2 = ss.load_state("pain_status.json")
    print(f"  Reloaded pain_level: {data2.get('pain_level', 'N/A')}")
    print(f"  Reloaded quota: {data2.get('current_quota', 'N/A')}")

    # Restore original
    ss.save_state("pain_status.json", test_data)

    print("\n" + "=" * 60)
    print("State sync tests completed!")
