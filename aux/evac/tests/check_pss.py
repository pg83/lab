import base64
import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from bridge import prepare_signature

vectors = []
for algorithm in ('SHA256', 'SHA384', 'SHA512'):
    digest = hashlib.new(algorithm.lower(), b'evacuation bridge PSS interoperability test').digest()
    for salt in ('digest', 'max'):
        encoded, mode = prepare_signature(base64.b64encode(digest).decode(),
            f'RSA_PKCS1_PSS_PADDING,hashalg={algorithm},saltlen={salt}')
        assert mode == 'RSA_NO_PADDING'
        vectors.append(json.dumps({'Encoded': encoded, 'Digest': base64.b64encode(digest).decode(),
            'Hash': algorithm, 'Salt': len(digest) if salt == 'digest' else 256-len(digest)-2}))
subprocess.run([sys.argv[1]], input='\n'.join(vectors)+'\n', text=True, check=True)
for malformed in ('RSA_PKCS1_PSS_PADDING,hashalg=SHA256,saltlen=invalid',
                  'RSA_PKCS1_PSS_PADDING,hashalg=SHA256,saltlen=digest,data=message',
                  'RSA_PKCS1_PSS_PADDING,hashalg=MD5,saltlen=digest'):
    try:
        prepare_signature(base64.b64encode(b'x'*32).decode(), malformed)
    except (ValueError, KeyError):
        pass
    else:
        raise AssertionError('Unexpected parameters accepted')
print('PASS: unsupported parameters rejected')
