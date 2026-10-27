import pathlib, re

content = pathlib.Path(r'C:\Users\qq366410837\.qclaw\workspace\MEMORY.md').read_text(encoding='utf-8')

print("总长度: %d 字符" % len(content))
print("行数: %d" % content.count('\n'))
print()

keywords = ["钢印", "2026-07-03", "涌现耦合", "感知预测", "大自然三阶", "代谢"]
for kw in keywords:
    count = content.count(kw)
    status = "OK" if count > 0 else "MISSING"
    print("  [%s] '%s' 出现 %d 次" % (status, kw, count))

print()
print("=== 段落结构 ===")
headers = re.findall(r'^## .+$', content, re.MULTILINE)
for h in headers:
    print("  %s" % h)
