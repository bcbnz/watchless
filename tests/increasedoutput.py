#!/usr/bin/env python

# A simple test script for watchless, a Python script which emulates the Unix
# watch program and adds paging support similar to that of the less program.
# The first time it is run it outputs 5 lines of text, and on subsequent runs it
# outputs 10 lines of text. A file, /tmp/ioutput, is used to test if this is the
# first run - delete it to reset the behaviour.

import os.path
import sys

if os.path.exists('/tmp/ioutput'):
    out = ['newoutput'] * 10
else:
    out = ['oldoutput'] * 5
    f = open('/tmp/ioutput', 'w')
    f.close()

sys.stdout.write('\n'.join(out))
