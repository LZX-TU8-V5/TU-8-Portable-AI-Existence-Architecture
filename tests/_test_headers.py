import urllib.request, json

data = json.dumps({'message': '你好'}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:5000/api/chat',
    data=data,
    headers={
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    },
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=15)
    print(f'Status: {r.status}')
    print(f'Headers: {dict(r.headers)}')
    content = r.read(500)
    print(f'Content (first 500 bytes): {content}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    print(f'Headers: {dict(e.headers)}')
    print(f'Body: {e.read()[:200]}')
except Exception as e:
    print(f'FAIL: {e}')
