import sys, importlib.util

sys.path.insert(0, r'D:\tu8-v5\hackathon')

# Test import
spec = importlib.util.spec_from_file_location('app', r'D:\tu8-v5\hackathon\app.py')
try:
    app_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_mod)
    print('OK: app.py imports without errors')
except Exception as e:
    print('FAIL:', e)

# Test zhihu_scraper standalone
spec2 = importlib.util.spec_from_file_location('zs', r'D:\tu8-v5\hackathon\zhihu_scraper.py')
zs = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(zs)
r = zs.get_hot_topics('心理健康')
print('OK: zhihu_scraper tier=', r['tier'], 'topics=', len(r['topics']))
print('OK: topic[0] title=', r['topics'][0]['q_title'][:20])
