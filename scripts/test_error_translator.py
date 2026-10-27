import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
from error_translator import translate, format_report

tests = [
    'npm error EPERM operation not permitted mkdir',
    'npm error EPERM 拒绝访问',
    '无法将 npm.cmd 项识别为...命令',
    'xxx 不是内部或外部命令 也不是可运行的程序',
    '此时不应有 )',
    'SyntaxError: unterminated string literal',
    'Cannot find module openclaw',
]

for err in tests:
    r = translate(err)
    snippet = err[:50]
    print(f"[{'OK' if r['matched'] else 'NO'}] {snippet} => {r['layer']}")
