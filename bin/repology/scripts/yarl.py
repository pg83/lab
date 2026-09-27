"""Stand-in for yarl: the guix parser only reads URL(url).host."""

import urllib.parse


class URL:
    def __init__(self, url):
        self.host = urllib.parse.urlsplit(url).hostname
