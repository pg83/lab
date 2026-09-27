"""
Pure-python port of libversion (https://github.com/repology/libversion),
the version comparison used by repology. Same algorithm, same flags, same
answers on the upstream test table (see test_libversion.py).

A version is split into components: runs of ASCII letters or ASCII
digits; everything else separates. Each component gets a rank
(metaorder), ranks compare first, then values: letters by their first
letter case-insensitively, numbers numerically. A shorter version is
padded with zero components, or with bound components when a bound
flag is set.
"""

P_IS_PATCH = 0x1
ANY_IS_PATCH = 0x2
LOWER_BOUND = 0x4
UPPER_BOUND = 0x8

# component ranks, in ascending order
_LOWER_BOUND = 0
_PRE_RELEASE = 1
_ZERO = 2
_POST_RELEASE = 3
_NONZERO = 4
_LETTER_SUFFIX = 5
_UPPER_BOUND = 6

_KW_UNKNOWN = 0
_KW_PRE = 1
_KW_POST = 2

_ALPHA = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
_DIGIT = frozenset('0123456789')


def _classify_keyword(word, flags):
    w = word.lower()

    if w in ('alpha', 'beta', 'rc') or w.startswith('pre'):
        return _KW_PRE

    if w.startswith('post') or w.startswith('patch') or w in ('pl', 'errata'):
        return _KW_POST

    if flags & P_IS_PATCH and w == 'p':
        return _KW_POST

    return _KW_UNKNOWN


def _alpha_rank(word, flags, unknown):
    kw = _classify_keyword(word, flags)

    if kw == _KW_PRE:
        return _PRE_RELEASE

    if kw == _KW_POST:
        return _POST_RELEASE

    return unknown


def parse(version, flags=0):
    """Components of a version as (rank, value) tuples, without padding."""
    n = len(version)
    i = 0
    out = []

    while True:
        while i < n and version[i] not in _ALPHA and version[i] not in _DIGIT:
            i += 1

        if i >= n:
            return out

        if version[i] in _ALPHA:
            j = i

            while j < n and version[j] in _ALPHA:
                j += 1

            unknown = _POST_RELEASE if flags & ANY_IS_PATCH else _PRE_RELEASE
            out.append((_alpha_rank(version[i:j], flags, unknown), version[i].lower()))
            i = j
            continue

        j = i

        while j < n and version[j] in _DIGIT:
            j += 1

        digits = version[i:j].lstrip('0')
        out.append((_NONZERO, int(digits)) if digits else (_ZERO, 0))
        i = j

        # Letter suffix: letters glued to a number and not followed by a
        # digit (1.0a, 1.0a.1, but not 1.0a1). Known keywords keep their
        # rank, anything else ranks above every number.
        if i < n and version[i] in _ALPHA:
            k = i

            while k < n and version[k] in _ALPHA:
                k += 1

            if k >= n or version[k] not in _DIGIT:
                out.append((_alpha_rank(version[i:k], flags, _LETTER_SUFFIX), version[i].lower()))
                i = k


def _padding(flags):
    if flags & LOWER_BOUND:
        return (_LOWER_BOUND, 0)

    if flags & UPPER_BOUND:
        return (_UPPER_BOUND, 0)

    return (_ZERO, 0)


def _cmp(a, b):
    return (a > b) - (a < b)


def version_compare(v1, v2, v1_flags=0, v2_flags=0):
    """-1, 0 or 1, like libversion's version_compare4."""
    c1 = parse(v1, v1_flags)
    c2 = parse(v2, v2_flags)

    p1 = _padding(v1_flags)
    p2 = _padding(v2_flags)

    # A bound flag adds one padding component even to the longer side, so
    # 1.0 with an upper bound compares greater than 1.0 itself.
    n1 = len(c1) + (1 if v1_flags & (LOWER_BOUND | UPPER_BOUND) else 0)
    n2 = len(c2) + (1 if v2_flags & (LOWER_BOUND | UPPER_BOUND) else 0)

    for i in range(max(n1, n2)):
        r1, x1 = c1[i] if i < len(c1) else p1
        r2, x2 = c2[i] if i < len(c2) else p2

        if r1 != r2:
            return _cmp(r1, r2)

        if x1 != x2:
            return _cmp(x1, x2)

    return 0


__all__ = ['ANY_IS_PATCH', 'LOWER_BOUND', 'P_IS_PATCH', 'UPPER_BOUND', 'version_compare']
