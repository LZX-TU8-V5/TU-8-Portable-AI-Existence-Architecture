import urllib.request, json

# Test homepage
try:
    r = urllib.request.urlopen('http://127.0.0.1:5000/', timeout=5)
    print(f'GET / -> {r.status}')
except Exception as e:
    print(f'GET / -> FAIL: {e}')

# Test API
data = json.dumps({'message': '你好'}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:5000/api/chat',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=15)
    print(f'POST /api/chat -> {r.status}')
except urllib.error.HTTPError as e:
    print(f'POST /api/chat -> HTTP {e.code}: {e.read()[:200]}')
except Exception as e:
    print(f'POST /api/chat -> FAIL: {e}')
