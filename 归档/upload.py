#!/usr/bin/env python3
import requests, sys

filepath = r'C:\Users\qq366410837\.qclaw\workspace\knowledge\TU-8\TU-8-Package-v1.0.zip'

try:
    with open(filepath, 'rb') as f:
        files = {'file': ('TU-8-Package-v1.0.zip', f, 'application/zip')}
        resp = requests.post('https://file.io', files=files, timeout=60)
    print(resp.status_code)
    print(resp.text)
except Exception as e:
    print('ERROR:', e)