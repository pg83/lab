#!/usr/bin/env python3

import sys
import json
import base64

import urllib.request as ur

req = {
    'type': 'get',
    'key': sys.argv[1],
}

data = ur.urlopen('http://localhost:8024/' + base64.b64encode(json.dumps(req).encode()).decode()).read()

sys.stdout.buffer.write(data)
