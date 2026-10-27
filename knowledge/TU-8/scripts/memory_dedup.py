# Remove duplicate time-block entries from memory/2026-05-04.md

path = r'C:\Users\qq366410837\.qclaw\workspace\memory\2026-05-04.md'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find duplicate header lines (## 2026-05-04 HH:MM - ...)
seen = {}
cleaned = []
skip_until_next = None

for i, line in enumerate(lines):
    if line.startswith('## 2026-05-04 '):
        # Extract timestamp part like "04:05"
        ts = line.split(' - ')[0].replace('## 2026-05-04 ', '')
        if ts in seen:
            # Start skipping from this duplicate
            skip_until_next = ts
            continue
        else:
            seen[ts] = True
            skip_until_next = None

    if skip_until_next is not None:
        # Check if this line is a new header (end of duplicate block)
        if line.startswith('## 2026-05-04 '):
            skip_until_next = line.split(' - ')[0].replace('## 2026-05-04 ', '')
            # Still skip this line if it's another duplicate header
            if line.startswith('## 2026-05-04 ' + skip_until_next):
                if lines[lines.index(line) if line in lines else i] == line:
                    pass
        else:
            continue

    cleaned.append(line)

result = '\n'.join(cleaned)
with open(path, 'w', encoding='utf-8') as f:
    f.write(result)

print(f'Before: {len(content.splitlines())} lines -> After: {len(result.splitlines())} lines')
print('Done.')
