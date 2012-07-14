#!/usr/bin/env python

# A simple test script for watchless, a Python script which emulates the Unix
# watch program and adds paging support similar to that of the less program.
# Using Python's random module, on approximately 50% of the times it is run a
# SystemError exception is raised. The remainder of the time a success message
# is printed on stdout and the script exits normally.

import random
import sys

if random.randint(0, 100) < 50:
    raise SystemError("Error occurred.")

sys.stdout.write("Everything ran successfully.\n")
