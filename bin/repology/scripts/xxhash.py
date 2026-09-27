"""
Stand-in for the xxhash module: repology only wants a stable 64-bit
integer digest of bytes (package hashes, rule text hashes) and never
compares it with anything computed elsewhere.
"""

import hashlib


def xxh64_intdigest(data):
    return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), 'little')
