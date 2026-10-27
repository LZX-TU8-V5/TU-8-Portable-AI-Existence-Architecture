"""
TU-8 错误翻译器 v1.0
====================
目的：将 Shell 层的"幻觉错误"翻译为真实根因。

根因：PowerShell 会把外部程序（npm/Node/native binary）的 stderr/stdout
     解析成 PowerShell 语法，导致真实的底层错误被翻译成语法报错。

典型案例（2026-07-01）：
  - PowerShell 报错："此时不应有 )"
  - 实际根因：npm EPERM 权限拒绝
  - 中间层：npm 调用链环境变量缺失
  - 表象：PowerShell 把二进制程序的错误输出当成了自己的语法
"""

import re
import os
import json
import sys
from typing import Optional

# ─────────────────────────────────────────
# 翻译规则表
# 格式：(pattern, shell_type, 层, 翻译, 根因, 下一步)
# ─────────────────────────────────────────

TRANSLATION_RULES = [
    # ── 幻觉层：PowerShell 把二进制错误解析成 PS 语法 ──────────────
    {
        "pattern": r"此时不应有\s+\)",
        "shell": "powershell",
        "layer": "L1_illusion",
        "表象": "PowerShell 语法错误",
        "翻译": "PowerShell 捕获了外部程序的 stderr/stdout 并试图解析为 PS 语法",
        "根因层": [
            ("L2_env", "外部程序依赖环境变量，当前 session 缺失"),
            ("L3_perm", "程序尝试写入受保护目录（Program Files 等）"),
            ("L4_binary", "程序二进制本身损坏或缺失"),
        ],
        "下一步": "将命令改为直接调用 node.exe + cli.js，跳过 PS 解析层",
        "证据检查": [
            ("环境变量", "QCLAW_CLI_NODE_BINARY 是否存在"),
            ("权限", "目标目录是否可写"),
            ("二进制", "node.exe/npm.cmd 是否存在"),
        ],
        "priority": 10,  # 高优先级，因为会误导整个诊断方向
    },

    # ── 幻觉层：命令不存在 ────────────────────────────────────────
    {
        "pattern": r"无法将.*项识别为.*命令.*",
        "shell": "powershell",
        "layer": "L1_illusion",
        "表象": "命令不存在",
        "翻译": "PowerShell 在 PATH 中找不到该命令",
        "根因层": [
            ("L2_path", "命令不在 PATH 环境变量中"),
            ("L3_env", "QClaw 打包的命令依赖注入环境变量才能找到"),
            ("L4_missing", "命令本身未安装"),
        ],
        "下一步": "检查 where.exe <命令> 的完整路径；检查命令是否 QClaw 打包的 wrapper",
        "证据检查": [
            ("PATH", "where.exe <命令>"),
            ("QCLAW_WRAPPER", "检查命令是否为 .cmd/.ps1 wrapper"),
        ],
        "priority": 8,
    },

    {
        "pattern": r".*不是内部或外部命令.*也不是可运行的程序",
        "shell": "powershell",
        "layer": "L1_illusion",
        "表象": "命令不在 PATH 中",
        "翻译": "同 '无法将...识别为命令'",
        "根因层": [
            ("L2_path", "命令不在系统 PATH"),
            ("L3_qclaw", "QClaw CLI 工具需要运行时环境变量"),
        ],
        "下一步": "使用 where.exe 定位命令；检查 openclaw.cmd/npm.cmd 等 wrapper",
        "证据检查": [
            ("完整路径", "Get-ChildItem 搜索命令文件"),
            ("Wrapper检查", "读取 .cmd 文件内容，确认是否 QClaw 注入型"),
        ],
        "priority": 7,
    },

    # ── 真实层：权限拒绝 ──────────────────────────────────────────
    {
        "pattern": r"EPERM.*operation not permitted|Permission denied|拒绝访问",
        "shell": "any",
        "layer": "L3_perm",
        "表象": "权限不足",
        "翻译": "当前用户无权在目标路径写入或执行",
        "根因层": [
            ("L4_prog_files", "目标路径在 D:\\Program Files\\（受保护目录）"),
            ("L4_admin_only", "目录需要管理员权限"),
        ],
        "下一步": "改用用户目录（AppData/Local/AppData\\Roaming）；或请求管理员提权",
        "证据检查": [
            ("目标路径", "从错误信息提取 path"),
            ("当前用户", "whoami 或 $env:USERNAME"),
            ("目录权限", "Test-Path 配合 -PathType Container"),
        ],
        "priority": 9,
    },

    # ── 真实层：模块不存在 ────────────────────────────────────────
    {
        "pattern": r"Cannot find module|module.*not found|MODULE_NOT_FOUND",
        "shell": "any",
        "layer": "L2_env",
        "表象": "Node.js 模块缺失",
        "翻译": "require() 或 import 找不到目标模块",
        "根因层": [
            ("L3_path", "node_modules 目录不在 NODE_PATH 中"),
            ("L3_missing", "模块确实未安装"),
            ("L3_scope", "全局模块 vs 本地模块路径问题"),
        ],
        "下一步": "检查模块是否在 node_modules 中；npm list；检查 NODE_PATH",
        "证据检查": [
            ("模块路径", "npm list <模块> --depth=0"),
            ("NODE_PATH", "echo $env:NODE_PATH"),
            ("全局位置", "npm root -g"),
        ],
        "priority": 8,
    },

    # ── 真实层：文件不存在 ──────────────────────────────────────
    {
        "pattern": r"No such file or directory|找不到路径|路径不存在",
        "shell": "any",
        "layer": "L2_path",
        "表象": "文件或目录缺失",
        "翻译": "指定的路径不存在",
        "根因层": [
            ("L3_moved", "文件被移动或删除"),
            ("L3_typo", "路径拼写错误"),
            ("L3_case", "Windows 文件系统大小写不敏感但 WSL/Python 敏感"),
        ],
        "下一步": "逐级检查父目录存在性；搜索文件位置",
        "证据检查": [
            ("父目录", "Test-Path <dirname>"),
            ("搜索", "Get-ChildItem -Recurse -Filter <basename>"),
        ],
        "priority": 7,
    },

    # ── 幻觉层：Python 语法被 PS 解析 ────────────────────────────
    {
        "pattern": r"SyntaxError.*unterminated string|unterminated.*string literal",
        "shell": "powershell",
        "layer": "L1_illusion",
        "表象": "Python 语法错误",
        "翻译": "PowerShell 解析了 Python 错误输出的引号，导致 PS 认为字符串未结束",
        "根因层": [
            ("L2_python", "Python 脚本本身有语法错误（次要）"),
            ("L3_shell_parse", "PS 把 Python 错误消息当成了自己的代码（主因）"),
        ],
        "下一步": "将 -c \"...\" 改为脚本文件方式运行；或用 & python.exe 显式调用",
        "证据检查": [
            ("脚本文件", "将内联 -c 代码写入 .py 文件运行"),
            ("转义", "检查引号是否在 PS 和 Python 间正确转义"),
        ],
        "priority": 8,
    },
]

# ─────────────────────────────────────────
# QClaw 路径动态检测（v1.1 — 从 sys.executable 反推 root）
# ─────────────────────────────────────────

_QCLAW_ROOT = None
_QCLAW_VERSION = None

def _detect_qclaw_root():
    """从 sys.executable 反推 QClaw 安装根目录。"""
    global _QCLAW_ROOT, _QCLAW_VERSION
    if _QCLAW_ROOT:
        return _QCLAW_ROOT, _QCLAW_VERSION
    exe = getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', None)
    if not exe:
        # sys.executable = D:\Program Files\QClaw\vX.X.X.XXX\resources\python\python.exe
        exe = sys.executable
    # Go up: python → resources → version_dir → root
    # vX.X.X.XXX/resources/python/python.exe
    parts = exe.replace('\\', '/').split('/')
    try:
        python_idx = parts.index('resources') - 1  # version dir
        root_idx = python_idx  # QClaw root (vX.X.X.XXX)
        if root_idx >= 0 and python_idx >= 2:
            _QCLAW_VERSION = parts[python_idx]  # e.g. "v0.2.35.624"
            _QCLAW_ROOT = '/'.join(parts[:root_idx + 1]).replace('/', '\\')
    except (ValueError, IndexError):
        pass
    return _QCLAW_ROOT, _QCLAW_VERSION


def get_qclaw_path_map():
    """动态构建当前版本的 QClaw 工具路径映射。"""
    root, version = _detect_qclaw_root()
    if not root:
        return {"error": "无法检测 QClaw 安装路径，sys.executable=" + sys.executable}
    r = root  # e.g. D:\Program Files\QClaw\v0.2.35.624
    return {
        "node.exe": [
            r + r"\resources\node\node.exe",
        ],
        "npm.cmd (QClaw)": [
            r + r"\resources\openclaw\config\npm-tools\node_modules\.bin\npm.cmd",
        ],
        "openclaw.cmd": [
            r + r"\resources\openclaw\config\bin\openclaw.cmd",
        ],
        "npm-cli.js": [
            r + r"\resources\openclaw\config\npm-tools\node_modules\npm\bin\npm-cli.js",
        ],
    }


# 保留旧常量供 __main__ 自测使用（内部调用 get_qclaw_path_map）
QCLAW_PATH_MAP = {}  # 惰性填充，首次访问时动态检测


def _get_qclaw_path_map_lazy():
    """兼容旧代码：首次调用时填充 QCLAW_PATH_MAP。"""
    global QCLAW_PATH_MAP
    if not QCLAW_PATH_MAP:
        QCLAW_PATH_MAP = get_qclaw_path_map()
    return QCLAW_PATH_MAP



def check_qclaw_env():
    """检查 QClaw 运行时环境变量是否注入。"""
    result = {
        "env_injected": False,
        "QCLAW_CLI_NODE_BINARY": os.environ.get("QCLAW_CLI_NODE_BINARY", "MISSING"),
        "QCLAW_NPM_CLI_JS": os.environ.get("QCLAW_NPM_CLI_JS", "MISSING"),
        "QCLAW_TASK_NODE_ENABLED": os.environ.get("QCLAW_TASK_NODE_ENABLED", "MISSING"),
        "node_binary_exists": os.path.exists(
            os.environ.get("QCLAW_CLI_NODE_BINARY", "")
        ),
    }
    result["env_injected"] = (
        result["QCLAW_CLI_NODE_BINARY"] != "MISSING"
        and result["node_binary_exists"]
    )
    return result


def translate(error_text: str, context: Optional[dict] = None) -> dict:
    """
    将错误信息翻译为真实根因。

    Args:
        error_text: 错误信息原文（来自 stderr/stdout/PS 输出）
        context: 可选的上下文（命令类型、shell 类型等）

    Returns:
        翻译结果 dict:
        {
            "matched": bool,
            "pattern": str,
            "layer": str,
            "表象": str,
            "翻译": str,
            "根因分析": [...],
            "下一步": str,
            "幻觉警告": str (如果有),
        }
    """
    for rule in sorted(TRANSLATION_RULES, key=lambda r: -r["priority"]):
        if re.search(rule["pattern"], error_text, re.IGNORECASE):
            result = {
                "matched": True,
                "pattern": rule["pattern"],
                "layer": rule["layer"],
                "表象": rule["表象"],
                "翻译": rule["翻译"],
                "根因分析": rule["根因层"],
                "下一步": rule["下一步"],
                "幻觉警告": "",
            }

            # 标记幻觉层（L1）
            if rule["layer"] == "L1_illusion":
                result["幻觉警告"] = (
                    f"⚠️ 【幻觉警告】以上报错是 PowerShell 解析了外部程序的输出，"
                    f"不是真实语法错误。真实问题在根因层（L2-L4）。"
                )

            # 特殊：如果是 npm/Node 相关幻觉，附加 QClaw 环境检查
            if context and context.get("command") in ["npm", "npm.cmd", "openclaw.cmd"]:
                qclaw_env = check_qclaw_env()
                if not qclaw_env["env_injected"]:
                    result["QClaw_环境诊断"] = {
                        "状态": "QClaw 工具路径（动态检测）",
                        "说明": "运行 python error_translator.py --check-env 查看实际路径",
                        "解决方案": "运行 --check-env 查看实际路径",
                        "工具路径": _get_qclaw_path_map_lazy(),
                    },

            return result

    return {
        "matched": False,
        "pattern": None,
        "layer": "unknown",
        "表象": error_text[:100],
        "翻译": "未找到匹配规则",
        "根因分析": [],
        "下一步": "提供更多信息以便添加规则",
    }


def format_report(result: dict) -> str:
    """格式化翻译报告为可读文本。"""
    lines = []
    lines.append("═" * 60)
    lines.append(f"错误翻译报告")
    lines.append("═" * 60)
    lines.append(f"匹配层: {result['layer']}")
    lines.append(f"表象: {result['表象']}")
    lines.append(f"真实含义: {result['翻译']}")

    if result.get("幻觉警告"):
        lines.append("")
        lines.append(result["幻觉警告"])

    if result.get("根因分析"):
        lines.append("")
        lines.append("根因层次分析:")
        for layer, desc in result["根因分析"]:
            lines.append(f"  [{layer}] {desc}")

    lines.append("")
    lines.append(f"下一步: {result['下一步']}")

    if result.get("QClaw_环境诊断"):
        qc = result["QClaw_环境诊断"]
        lines.append("")
        lines.append("─" * 40)
        lines.append(f"QClaw 环境: {qc['状态']}")
        lines.append(f"说明: {qc['说明']}")
        lines.append(f"解决方案: {qc['解决方案']}")
        lines.append("工具路径:")
        for name, paths in qc["工具路径"].items():
            exists = "✅" if any(os.path.exists(p) for p in paths) else "❌"
            lines.append(f"  {exists} {name}: {paths[0]}")

    lines.append("═" * 60)
    return "\n".join(lines)


# ─────────────────────────────────────────
# CLI 接口
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io
    # 确保 stdout 编码为 UTF-8（避免 Windows GBK 问题）
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    if len(sys.argv) < 2:
        print("用法: python error_translator.py <错误信息>")
        print("用法: python error_translator.py --check-env")
        sys.exit(0)

    if sys.argv[1] == "--check-env":
        env = check_qclaw_env()
        path_map = get_qclaw_path_map()
        print(json.dumps({"env": env, "path_map": path_map}, indent=2, ensure_ascii=False))
        sys.exit(0)

    error_text = " ".join(sys.argv[1:])
    result = translate(error_text)
    print(format_report(result))
