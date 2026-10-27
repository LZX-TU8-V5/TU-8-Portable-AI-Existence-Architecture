#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file_lock.py — TU-8 跨进程文件锁 + 原子写（并发读写防护）

Windows 用原生 msvcrt.locking 对 `.lock` 旁挂文件加排他锁（进程崩溃时 OS 自动释放，无死锁）；
非 Windows 回退到 O_EXCL 锁文件（仅 advisory，无崩溃恢复）。

提供：
  - FileLock(path, timeout): with 上下文管理器
  - atomic_write_json(path, obj): 临时文件 + fsync + os.replace（防半截写入）
  - safe_read_json(path, default): 损坏/缺失返回 default，不抛
  - read_modify_write(path, fn, default): 加锁的读-改-写（防竞态丢更新）
  - append_jsonl(path, obj): 加锁追加一行
"""
import os
import sys
import time
import json
import tempfile

try:
    import msvcrt
    _HAVE_MSVC = True
except Exception:
    _HAVE_MSVC = False


class FileLock:
    def __init__(self, path, timeout=10.0, retry=0.05):
        self.lockpath = path + ".lock"
        self.timeout = timeout
        self.retry = retry
        self.fd = None

    def acquire(self):
        deadline = time.time() + self.timeout
        if not _HAVE_MSVC:
            while True:
                try:
                    fd = os.open(self.lockpath, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                except FileExistsError:
                    if time.time() >= deadline:
                        raise TimeoutError("文件锁超时: " + self.lockpath)
                    time.sleep(self.retry)
                    continue
                self.fd = fd
                return
        while True:
            try:
                fd = os.open(self.lockpath, os.O_CREAT | os.O_RDWR | os.O_BINARY)
            except Exception:
                fd = None
            if fd is not None:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    self.fd = fd
                    return
                except OSError:
                    os.close(fd)
                    self.fd = None
            if time.time() >= deadline:
                raise TimeoutError("文件锁超时: " + self.lockpath)
            time.sleep(self.retry)

    def release(self):
        if self.fd is not None:
            try:
                if _HAVE_MSVC:
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def atomic_write_json(path, obj, indent=2):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp", prefix=".fl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def safe_read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default


def safe_read_text(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default
    except Exception:
        return default


def atomic_write_text(path, text):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp", prefix=".fl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def read_modify_write_text(path, fn, default="", timeout=10.0):
    with FileLock(path, timeout):
        data = safe_read_text(path, default)
        new = fn(data)
        if new is not None:
            atomic_write_text(path, new)
        return new


def read_modify_write(path, fn, default=None, timeout=10.0):
    with FileLock(path, timeout):
        data = safe_read_json(path, default)
        new = fn(data)
        if new is not None:
            atomic_write_json(path, new)
        return new


def append_jsonl(path, obj, timeout=10.0):
    line = json.dumps(obj, ensure_ascii=False)
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    with FileLock(path, timeout):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
