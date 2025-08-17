#!/usr/bin/env python3

import sys
import json
import base64

import urllib.request as ur

req = {
    'type': 'put',
    'key': sys.argv[1],
    'val': base64.b64encode(open(sys.argv[1], 'rb').read()).decode(),
}

ur.urlopen('http://localhost:8024/' + base64.b64encode(json.dumps(req).encode()).decode()).read()
