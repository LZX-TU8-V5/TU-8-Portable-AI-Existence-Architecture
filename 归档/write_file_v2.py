#!/usr/bin/env python3
"""
text-file-writer: 跨平台文本文件写入脚本
=========================================
解决 OpenClaw write 工具硬编码 utf-8 (无 BOM) 导致 Windows Excel
打开 CSV/TSV 文件时中文乱码的问题。

用法:
  # 平台探测（不写文件，仅返回当前系统信息）
  python3 write_file.py --detect

  # 写入文件
  python3 write_file.py --path <文件路径> --content-file <内容临时文件> [选项]
  python3 write_file.py --path <文件路径> --content <内容字符串> [选项]

选项:
  --detect             探测当前平台并输出 JSON，不做任何文件写入（推荐写文件前先调用）
  --encoding <enc>     显式指定编码。不传则根据文件后缀和目标平台自动推断。
                       可选值: utf-8 | utf-8-sig | gbk | gb18030 | utf-16 | utf-16-le | auto (默认 auto)
  --platform <p>       目标平台。不传则自动检测当前平台。
                       可选值: windows | mac | linux | auto (默认 auto)
  --newline <nl>       换行符。不传则根据平台自动选择。
                       可选值: crlf | lf | preserve | auto (默认 auto)
                       preserve: 保留已有文件的换行符风格（文件不存在时退化为 auto）
  --preserve           同时启用 --preserve-bom 和 --preserve-newline
  --preserve-bom       若目标文件已存在且有 BOM，则保留 BOM（即使推断规则认为不需要）
  --preserve-newline   等同于 --newline preserve
  --append             追加模式（不覆盖，追加到文件末尾）
  --no-mkdir           禁止自动创建父目录

退出码:
  0  成功
  1  参数错误
  2  写入失败

输出 (stdout, JSON):
  # --detect 模式
  {"platform": "mac", "system": "Darwin", "python": "3.11.0",
   "default_csv_encoding": "utf-8", "default_csv_bom": false}

  # 写入成功
  {"status": "ok", "path": "<绝对路径>", "encoding": "<实际使用的编码>",
   "bom": true/false, "newline": "crlf"/"lf", "bytes": <字节数>,
   "mode": "write"/"append", "preserved_bom": true/false, "preserved_newline": true/false}

  {"status": "error", "message": "<错误信息>"}
"""

import argparse
import json
import platform
import sys
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# 编码缓存：避免对同一 (ext, platform) 组合重复推理
# ══════════════════════════════════════════════════════════════════════════════
_encoding_cache: dict[str, str] = {}

# ══════════════════════════════════════════════════════════════════════════════
# 核心规则极简化表（仅 3 类，其余默认 utf-8 无 BOM）
# ══════════════════════════════════════════════════════════════════════════════

# 需要 UTF-16 LE with BOM 的文件（Windows 注册表文件）
_UTF16_LE_BOM_EXTS = {".reg"}

# Windows ANSI (GBK) 文件（.inf 安装信息，.bat/.cmd 含非 ASCII 时）
_WINDOWS_ANSI_EXTS = {".inf", ".bat", ".cmd"}

# Excel 友好类型：Windows → utf-8-sig（加 BOM），其他 → utf-8
_EXCEL_FRIENDLY_EXTS = {".csv", ".tsv"}

# .ps1 PowerShell 脚本始终 utf-8-sig
_PS1_EXT = ".ps1"

# ══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════════════════════

def _has_non_ascii(content: str) -> bool:
    """检测内容是否包含非 ASCII 字符。"""
    return any(ord(c) > 127 for c in content)


def _detect_existing_encoding(file_path: Path) -> tuple:
    """
    检测已有文件的编码和 BOM 类型。

    返回值: (encoding, has_bom)
      - encoding: "utf-8-sig" | "utf-16-le" | "utf-16-be" | "utf-8"
      - has_bom: True 如果文件有 BOM
    """
    try:
        with open(file_path, "rb") as f:
            head = f.read(4)

        # UTF-8 BOM (EF BB BF)
        if head[:3] == b"\xef\xbb\xbf":
            return "utf-8-sig", True
        # UTF-16 LE BOM (FF FE) - 注意要在 UTF-32 之前检查
        if head[:2] == b"\xff\xfe" and head[2:4] != b"\x00\x00":
            return "utf-16-le", True
        # UTF-16 BE BOM (FE FF)
        if head[:2] == b"\xfe\xff":
            return "utf-16-be", True
        # UTF-32 LE BOM (FF FE 00 00) - 罕见
        if head[:4] == b"\xff\xfe\x00\x00":
            return "utf-32-le", True
        # UTF-32 BE BOM (00 00 FE FF) - 罕见
        if head[:4] == b"\x00\x00\xfe\xff":
            return "utf-32-be", True

        return "utf-8", False
    except Exception:
        return "utf-8", False


def _detect_existing_newline(file_path: Path, encoding: str) -> str:
    """读取已有文件前几 KB，检测其换行符风格。"""
    try:
        with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
            text = f.read(4096)
        if "\r\n" in text:
            return "\r\n"
        return "\n"
    except Exception:
        return ""  # 失败时返回空字符串，调用方用平台默认值兜底


def _infer_encoding(path: Path, target_platform: str, content: str = "") -> str:
    """
    根据文件后缀、目标平台推断最合适的编码。

    核心规则极简化：
      .reg              → utf-16 (with BOM)
      .inf / .bat / .cmd (含中文, Windows) → gbk
      .csv / .tsv (Windows) → utf-8-sig
      .ps1              → utf-8-sig
      其余一切           → utf-8 (无 BOM)

    返回值:
      "utf-8-sig"   — UTF-8 with BOM
      "utf-8"       — UTF-8 without BOM
      "utf-16"      — UTF-16 with BOM (Python 自动选择字节序)
      "gbk"         — GBK (Windows .bat/.cmd/.inf 含中文场景)
    """
    ext = path.suffix.lower()

    # 缓存键：(ext, platform)
    cache_key = f"{ext}|{target_platform}"
    if cache_key in _encoding_cache:
        cached = _encoding_cache[cache_key]
        # .bat/.cmd 含中文与否影响结果，缓存命中时无法访问 content，
        # 故对含中文 .bat/.cmd 绕过缓存。
        # 其余类型缓存命中直接返回。
        if ext not in {".bat", ".cmd"}:
            return cached

    # ── 规则推理 ────────────────────────────────────────────────────────────
    encoding: str

    if ext in _UTF16_LE_BOM_EXTS:
        encoding = "utf-16"  # Python 的 utf-16 自动加 BOM

    elif ext in _WINDOWS_ANSI_EXTS:
        if target_platform == "windows" and _has_non_ascii(content):
            encoding = "gbk"
        else:
            encoding = "utf-8"

    elif ext == _PS1_EXT:
        encoding = "utf-8-sig"

    elif ext in _EXCEL_FRIENDLY_EXTS:
        encoding = "utf-8-sig" if target_platform == "windows" else "utf-8"

    else:
        # 默认：utf-8 无 BOM（最通用，不会破坏任何解析器）
        encoding = "utf-8"

    # 写入缓存（不含中文的 .bat/.cmd 结果也可缓存）
    if ext not in {".bat", ".cmd"} or not _has_non_ascii(content):
        _encoding_cache[cache_key] = encoding

    return encoding


def _detect_platform(arg: str) -> str:
    """将 --platform 参数或当前系统映射为 windows / mac / linux。"""
    if arg != "auto":
        return arg.lower()
    s = platform.system().lower()
    if s == "windows":
        return "windows"
    if s == "darwin":
        return "mac"
    return "linux"


def _newline_for_platform(arg: str, target_platform: str) -> str:
    """返回实际换行符字符串。"""
    if arg in ("auto", "preserve"):
        return "\r\n" if target_platform == "windows" else "\n"
    return "\r\n" if arg == "crlf" else "\n"


def _detect_existing_newline_TEXT(text: str) -> str:
    """检测文本中使用的换行符风格，返回 '\\r\\n' 或 '\\n'。"""
    if "\r\n" in text:
        return "\r\n"
    return "\n"


# ── 平台探测 ──────────────────────────────────────────────────────────────────

def _detect_info() -> dict:
    """探测当前平台信息，供 AI 决策是否需要传 --platform。"""
    sys_name = platform.system()          # 'Darwin' / 'Windows' / 'Linux'
    plat = _detect_platform("auto")       # 'mac' / 'windows' / 'linux'

    # 在当前平台上，.csv 默认会用什么编码？（反映脚本实际行为）
    dummy_csv = Path("dummy.csv")
    default_csv_enc = _infer_encoding(dummy_csv, plat)
    has_bom = default_csv_enc == "utf-8-sig"

    return {
        "platform": plat,                       # mac | windows | linux
        "system": sys_name,                     # Darwin | Windows | Linux
        "python": platform.python_version(),    # e.g. "3.11.0"
        "default_csv_encoding": default_csv_enc,
        "default_csv_bom": has_bom,
        # 给 AI 的直接建议：当前平台写 CSV 是否需要传 --platform windows？
        "needs_platform_windows_for_local_csv": plat == "windows",
    }


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="跨平台文本文件写入工具")
    parser.add_argument(
        "--detect",
        action="store_true",
        help="探测当前平台并输出 JSON，不做任何文件写入",
    )
    parser.add_argument("--path", help="目标文件路径（相对或绝对）")

    content_group = parser.add_mutually_exclusive_group()
    content_group.add_argument("--content", help="文件内容（直接传字符串）")
    content_group.add_argument(
        "--content-file",
        help="包含文件内容的临时文件路径（推荐，避免 shell 转义问题）",
    )

    parser.add_argument(
        "--encoding",
        default="auto",
        help="编码 (utf-8 | utf-8-sig | gbk | gb18030 | utf-16 | utf-16-le | auto)，默认 auto 自动推断",
    )
    parser.add_argument(
        "--platform",
        default="auto",
        help="目标平台 (windows | mac | linux | auto)，默认 auto",
    )
    parser.add_argument(
        "--newline",
        default="auto",
        help="换行符 (crlf | lf | preserve | auto)，默认 auto",
    )
    parser.add_argument(
        "--preserve",
        action="store_true",
        help="同时启用 --preserve-bom 和 --preserve-newline（修改已有文件时推荐）",
    )
    parser.add_argument(
        "--preserve-bom",
        action="store_true",
        help="若目标文件已有 BOM，则保留（即使推断规则认为不需要）",
    )
    parser.add_argument(
        "--preserve-newline",
        action="store_true",
        help="保留已有文件的换行符风格（等同于 --newline preserve）",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="追加模式，不覆盖文件，追加到末尾",
    )
    parser.add_argument(
        "--no-mkdir",
        action="store_true",
        help="禁止自动创建父目录",
    )

    args = parser.parse_args()

    # ── --detect 模式：仅输出平台信息，不做任何文件操作 ──────────────────────
    if args.detect:
        _ok(_detect_info())
        return 0

    # 非 detect 模式时，--path 和内容来源为必填
    if not args.path:
        _error("--path 为必填参数（或使用 --detect 仅探测平台）")
        return 1
    if args.content is None and args.content_file is None:
        _error("--content 或 --content-file 为必填参数之一")
        return 1

    # --preserve 是 --preserve-bom + --preserve-newline 的快捷方式
    preserve_bom = args.preserve_bom or args.preserve
    preserve_newline = args.preserve_newline or args.preserve
    newline_arg = "preserve" if preserve_newline else args.newline

    # ── 读取内容 ──────────────────────────────────────────────────────────────
    if args.content is not None:
        content = args.content
    else:
        try:
            with open(args.content_file, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError as e:
            _error(f"读取内容文件失败: 文件编码不是 UTF-8。{e}")
            return 2
        except FileNotFoundError:
            _error(f"读取内容文件失败: 文件不存在 '{args.content_file}'")
            return 2
        except Exception as e:
            _error(f"读取内容文件失败: {e}")
            return 2

    # ── 解析目标路径 ──────────────────────────────────────────────────────────
    target_path = Path(args.path).expanduser().resolve()
    file_exists = target_path.exists()

    # ── 推断平台和编码 ────────────────────────────────────────────────────────
    target_platform = _detect_platform(args.platform)

    # 编码推断需要知道内容（用于检测 .bat/.cmd 是否含非 ASCII）
    if args.encoding == "auto":
        encoding = _infer_encoding(target_path, target_platform, content)
    else:
        encoding = args.encoding

    # ── preserve-bom：若文件已存在且有 BOM，强制保留 ──────────────────────────
    preserved_bom = False
    if file_exists:
        detected_enc, has_existing_bom = _detect_existing_encoding(target_path)
        if preserve_bom and has_existing_bom and not args.append:
            encoding = detected_enc
            preserved_bom = True

    # ── 换行符处理 ────────────────────────────────────────────────────────────
    # 优化：只有 --preserve-newline 时才读文件，否则按平台推断
    preserved_newline = False
    if newline_arg == "preserve" and file_exists:
        # 按已有文件的实际换行符风格读取
        existing_newline = _detect_existing_newline(target_path, encoding)
        if existing_newline:
            newline = existing_newline
            preserved_newline = True
        else:
            newline = _newline_for_platform("auto", target_platform)
    else:
        newline = _newline_for_platform(newline_arg, target_platform)

    # ── 创建父目录 ────────────────────────────────────────────────────────────
    if not args.no_mkdir:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            _error(f"创建目录失败: 权限拒绝 '{target_path.parent}'")
            return 2
        except Exception as e:
            _error(f"创建目录失败: {e}")
            return 2

    # ── 统一换行符 ────────────────────────────────────────────────────────────
    # 先把内容中所有换行符统一为 \n，再替换为目标换行符
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    final_content = normalized.replace("\n", newline)

    # ── 记录写入前大小（用于 append 模式统计） ────────────────────────────────
    size_before = 0
    if args.append and file_exists:
        try:
            size_before = target_path.stat().st_size
        except Exception:
            pass

    # ── 写入文件 ──────────────────────────────────────────────────────────────
    open_mode = "a" if args.append else "w"
    try:
        # newline="" 让 Python 不再做额外换行转换（我们已手动处理）
        with open(target_path, open_mode, encoding=encoding, newline="") as f:
            f.write(final_content)
    except UnicodeEncodeError as e:
        # 编码无法表示某些字符（如用 GBK 写 emoji）
        problem_char = e.object[e.start:e.end] if e.start < len(e.object) else "?"
        try:
            code_point = f"U+{ord(problem_char):04X}"
        except (TypeError, ValueError):
            code_point = "unknown"
        _error(
            f"编码错误: 字符 '{problem_char}' ({code_point}) 无法用 {encoding} 编码表示。"
            f"建议使用 --encoding utf-8 或 --encoding utf-8-sig"
        )
        return 2
    except PermissionError:
        _error(f"写入失败: 权限拒绝 '{target_path}'")
        return 2
    except OSError as e:
        # errno 28 = ENOSPC (磁盘空间不足)
        if hasattr(e, 'errno') and e.errno == 28:
            _error(f"写入失败: 磁盘空间不足")
        else:
            _error(f"写入失败: {e}")
        return 2
    except Exception as e:
        _error(f"写入失败: {e}")
        return 2

    # ── 计算实际字节数 ────────────────────────────────────────────────────────
    try:
        byte_size = target_path.stat().st_size
        bytes_written = byte_size - size_before if args.append else byte_size
    except Exception:
        byte_size = -1
        bytes_written = -1

    # 判断最终文件是否有 BOM
    has_bom = encoding.lower() in {"utf-8-sig", "utf-8-bom", "utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"}

    _ok({
        "status": "ok",
        "path": str(target_path),
        "encoding": encoding,
        "bom": has_bom,
        "newline": "crlf" if newline == "\r\n" else "lf",
        "bytes": byte_size,
        "bytes_written": bytes_written,
        "mode": "append" if args.append else "write",
        "preserved_bom": preserved_bom,
        "preserved_newline": preserved_newline,
    })
    return 0


# ── 输出工具 ──────────────────────────────────────────────────────────────────

def _ok(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False))


def _error(message: str) -> None:
    print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
