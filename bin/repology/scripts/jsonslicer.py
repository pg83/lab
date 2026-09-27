"""
Stand-in for jsonslicer: the same iteration protocol, over the json
module's raw_decode instead of yajl.

JsonSlicer(file, path_prefix, path_mode=None) walks the document and
yields the values whose path matches path_prefix, where None matches
any key or index. path_mode='map_keys' yields (key, value) for values
under a dict, path_mode='full' yields (*path, value).

Only the containers on the prefix path are walked by hand; every value
at the prefix depth is decoded and handed out one at a time, so a
150k-package index costs its text, not its object tree. The walk runs
over a latin-1 view of the bytes (one byte per char: a UTF-8 decode of
a 400 MB index with a single astral character costs 8 GB) and only
finds extents; each value is then decoded from its exact bytes.
"""

import json
import mmap

_WS = ' \t\r\n'


class JsonSlicer:
    def __init__(self, file, path_prefix, path_mode=None, encoding=None, **kwargs):
        try:
            self.raw = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError, AttributeError):
            self.raw = file.read()

        self.text = self.raw[:].decode('latin-1')
        self.prefix = tuple(path_prefix)
        self.mode = path_mode
        self.decoder = json.JSONDecoder()

    def __iter__(self):
        yield from self._walk((), 0, self._ws(0))

    def _ws(self, i):
        text = self.text
        n = len(text)

        while i < n and text[i] in _WS:
            i += 1

        return i

    def _value(self, i):
        """The decoded JSON value at i and the offset after it."""
        _, end = self.decoder.raw_decode(self.text, i)

        return json.loads(self.raw[i:end]), end

    def _emit(self, path, value):
        if self.mode == 'full':
            return (*path, value)

        if self.mode == 'map_keys':
            return (path[-1], value)

        return value

    def _expect(self, i, char):
        if self.text[i] != char:
            raise ValueError(f'expected {char!r} at offset {i}, got {self.text[i]!r}')

    def _walk(self, path, depth, i):
        """Yield the matches inside the value at i; return the offset after it."""
        text = self.text

        if depth == len(self.prefix):
            value, end = self._value(i)
            yield self._emit(path, value)
            return end

        want = self.prefix[depth]

        if text[i] == '{':
            i = self._ws(i + 1)

            if text[i] == '}':
                return i + 1

            while True:
                key, i = self._value(i)
                i = self._ws(i)
                self._expect(i, ':')
                i = self._ws(i + 1)

                if want is None or want == key:
                    i = yield from self._walk((*path, key), depth + 1, i)
                else:
                    _, i = self.decoder.raw_decode(text, i)

                i = self._ws(i)

                if text[i] == ',':
                    i = self._ws(i + 1)
                    continue

                self._expect(i, '}')
                return i + 1

        if text[i] == '[':
            i = self._ws(i + 1)

            if text[i] == ']':
                return i + 1

            idx = 0

            while True:
                if want is None or want == idx:
                    i = yield from self._walk((*path, idx), depth + 1, i)
                else:
                    _, i = self.decoder.raw_decode(text, i)

                i = self._ws(i)
                idx += 1

                if text[i] == ',':
                    i = self._ws(i + 1)
                    continue

                self._expect(i, ']')
                return i + 1

        # A scalar where the prefix wants a container: nothing below it.
        _, end = self.decoder.raw_decode(text, i)
        return end
