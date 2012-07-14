#!/usr/bin/env python

# A simple test script for watchless, a Python script which emulates the Unix
# watch program and adds paging support similar to that of the less program.
# The first time it is run it outputs 10 lines of text, and on subsequent runs it
# outputs 5 lines of text. A file, /tmp/routput, is used to test if this is the
# first run - delete it to reset the behaviour.

import os.path
import sys

if os.path.exists('/tmp/routput'):
    out = ['newoutput'] * 5
else:
    out = ['oldoutput'] * 10
    f = open('/tmp/routput', 'w')
    f.close()

sys.stdout.write('\n'.join(out))
