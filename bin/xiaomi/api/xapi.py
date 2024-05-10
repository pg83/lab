#!/usr/bin/env python3

import re
import sys
import time
import random
import hashlib
import requests

router_ip_address = sys.argv[1]
password = sys.argv[2]
rule_name = sys.argv[3]
rule_type = sys.argv[4]
rule_sport = sys.argv[5]
rule_ip = sys.argv[6]
rule_dport = sys.argv[7]

def sha(d):
    return hashlib.sha256(d.encode()).hexdigest()

r0 = requests.get(f'http://{router_ip_address}/cgi-bin/luci/web')
mac = re.findall(r'deviceId = \'(.*?)\'', r0.text)[0]
key = re.findall(r'key: \'(.*)\',', r0.text)[0]
nonce = '_'.join(str(x) for x in [0, mac, int(time.time()) + 1, random.randint(1000, 10000)])
pwd = sha(nonce + sha(password + key))

headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:65.0) Gecko/20100101 Firefox/65.0",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
}

r1 = requests.post(
    f'http://{router_ip_address}/cgi-bin/luci/api/xqsystem/login',
    data=f'username=admin&password={pwd}&logtype=2&nonce={nonce}',
    headers=headers,
)

stok = re.findall(r'"token":"(.*?)"', r1.text)[0]

rr = requests.post(
    f'http://{router_ip_address}/cgi-bin/luci/;stok={stok}/api/xqsystem/add_redirect',
    data=f'name={rule_name}&proto={rule_type}&sport={rule_sport}&ip={rule_ip}&dport={rule_dport}',
    headers=headers,
)

print(rr.text)
