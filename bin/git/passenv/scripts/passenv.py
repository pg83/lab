#!/usr/bin/env python3

import os
import sys

if 'Username' in str(sys.argv):
    print(os.environ['GIT_USER'])
elif 'Pass' in str(sys.argv):
    print(os.environ['GIT_PASS'])
