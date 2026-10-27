import os
for f in [r'C:\Users\qq366410837\.qclaw\workspace\scripts\add39.py',
          r'C:\Users\qq366410837\.qclaw\workspace\scripts\rm38.py',
          r'C:\Users\qq366410837\.qclaw\workspace\scripts\rm37.py']:
    try: os.remove(f)
    except: pass
