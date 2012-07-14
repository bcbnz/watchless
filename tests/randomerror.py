#!/usr/bin/env python

# A simple test script for watchless, a Python script which emulates the Unix
# watch program and adds paging support similar to that of the less program.
# Using Python's random module, on approximately 50% of the times it is run a
# message is printed on stderr and the script exits with return code 1. The
# remainder of the time a success message is printed on stdout and the script
# exits normally.

import random
import sys

if random.randint(0, 100) < 50:
    sys.stderr.write("Error occurred, exiting.\n")
    sys.exit(1)

sys.stdout.write("Everything ran successfully.\n")
