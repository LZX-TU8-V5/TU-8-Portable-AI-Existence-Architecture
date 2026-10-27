import os, shutil, filecmp

src = os.path.expanduser(r'~\.qclaw\workspace\knowledge\TU-8')
dst = r'D:\tu8-v5\TU-8'

synced, skipped, copied_to_dst, copied_to_src = 0, 0, [], []

for root, dirs, files in os.walk(src):
    for f in files:
        sp = os.path.join(root, f)
        rel = os.path.relpath(sp, src)
        dp = os.path.join(dst, rel)
        if os.path.exists(dp):
            if filecmp.cmp(sp, dp, shallow=False):
                skipped += 1
            else:
                st = os.path.getmtime(sp)
                dt = os.path.getmtime(dp)
                if st > dt:
                    shutil.copy2(sp, dp)
                    copied_to_dst.append(rel)
                else:
                    shutil.copy2(dp, sp)
                    copied_to_src.append(rel)
                synced += 1
        else:
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copy2(sp, dp)
            copied_to_dst.append(rel)
            synced += 1

for root, dirs, files in os.walk(dst):
    for f in files:
        dp = os.path.join(root, f)
        rel = os.path.relpath(dp, dst)
        sp = os.path.join(src, rel)
        if not os.path.exists(sp):
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            shutil.copy2(dp, sp)
            copied_to_src.append(rel)
            synced += 1

print(f'Same: {skipped}, Synced: {synced}')
if copied_to_dst: print(f'To D:\\tu8-v5: {copied_to_dst}')
if copied_to_src: print(f'To knowledge: {copied_to_src}')
