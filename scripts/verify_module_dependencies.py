#!/usr/bin/env python3
"""
模块依赖验证脚本 v2
精确检测：只分析代码行，排除注释和文档字符串
"""

import os
import re
import ast
from pathlib import Path
from collections import defaultdict

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
SRC_DIR = WORKSPACE / "src"

def extract_imports_from_file(filepath: Path) -> set:
    """使用 AST 精确提取导入的模块"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports
    except Exception as e:
        return set()

def main():
    errors = []
    warnings = []
    checked = {}
    
    # 标准库白名单
    stdlib = {
        'json', 'os', 'time', 'math', 'logging', 'sys', 're', 'datetime',
        'collections', 'pathlib', 'typing', 'dataclasses', 'enum', 'functools',
        'itertools', 'copy', 'hashlib', 'random', 'threading', 'subprocess',
        'io', 'csv', 'glob', 'abc', 'contextlib', 'warnings', 'traceback',
        'inspect', 'ast', 'errno', 'stat', 'shutil', 'tempfile', 'socket',
        'struct', 'array', 'weakref', 'types', 'numbers', 'decimal', 'fractions',
        'argparse', 'configparser', 'platform', 'unittest', 'pdb', 'pprint',
        'textwrap', 'string', 'difflib', 'heapq', 'bisect', 'queue',
        'multiprocessing', 'concurrent', 'asyncio', 'selectors', 'signal',
        'mmap', 'ctypes', 'codecs', 'unicodedata', 'locale', 'calendar',
        'importlib', 'linecache', 'tokenize', 'symbol', 'token', 'keyword',
        'operator', 'pickle', 'shelve', 'dbm', 'sqlite3', 'zlib', 'gzip',
        'bz2', 'lzma', 'zipfile', 'tarfile', 'xml', 'html', 'email',
        'http', 'urllib', 'ftplib', 'poplib', 'imaplib', 'smtplib',
        'uuid', 'base64', 'binascii', 'quopri', 'uu', 'unittest',
        'secrets', 'fnmatch', 'msvcrt', '__future__', 'gc', 'dis',
    }
    
    # 第三方库白名单
    thirdparty = {
        'numpy', 'pandas', 'scipy', 'sklearn', 'torch', 'tensorflow',
        'requests', 'httpx', 'aiohttp', 'flask', 'fastapi', 'pydantic',
        'statemachine', 'transitions', 'matplotlib', 'PIL', 'cv2',
        'yaml', 'ruamel', 'toml',
    }
    
    # 特殊导入（路径导入）
    special = {'src'}
    
    # 获取所有 Python 文件
    files = list(SRC_DIR.glob("*.py"))
    files = [f for f in files if not f.name.startswith("test_")]
    
    print(f"检查 {len(files)} 个模块...")
    
    # 已知模块列表
    known_modules = {f.stem for f in files}
    
    for file in files:
        module_name = file.stem
        imports = extract_imports_from_file(file)
        
        # 检查本地模块导入
        local_imports = {imp for imp in imports if imp not in stdlib and imp not in thirdparty and imp not in special}
        
        for imp in local_imports:
            if imp not in known_modules:
                errors.append(f"[{module_name}] 导入不存在的模块: {imp}")
        
        checked[module_name] = local_imports
    
    # 检测循环依赖
    for mod in checked:
        for imp in checked[mod]:
            if imp in checked and mod in checked[imp]:
                # 排除自循环误报（通过 AST 不会误报）
                if mod != imp:
                    warnings.append(f"循环依赖: {mod} <-> {imp}")
    
    # 检查状态文件
    agent_dir = WORKSPACE / "_agent_memory"
    state_files = [
        "surface_tension_state.json",
        "phase_lock_state.json",
        "attractor_basin_state.json",
        "intrinsic_reward_state.json",
        "heartbeat_state.json",
        "lambda_tuner_state.json",
    ]
    
    print("\n检查状态文件...")
    for sf in state_files:
        path = agent_dir / sf
        if path.exists():
            print(f"  OK {sf}")
        else:
            print(f"  -- {sf} (未创建)")
    
    # 输出结果
    print("\n========== 验证结果 ==========")
    print(f"错误: {len(errors)}")
    print(f"警告: {len(warnings)}")
    
    if errors:
        print("\n错误详情:")
        for e in errors[:10]:
            print(f"  {e}")
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个错误")
    
    if warnings:
        print("\n警告详情:")
        for w in warnings:
            print(f"  {w}")
    
    print(f"\n统计: 已检查模块 {len(files)}")
    
    return len(errors), len(warnings)


if __name__ == "__main__":
    errors, warnings = main()
    exit(errors)
