#!/usr/bin/env python

# watchless: a Python script which emulates the Unix watch program and adds
# paging support similar to that of the less program.
#
# Copyright (C) 2012 Blair Bonnett
#
# watchless is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# watchless is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# watchless.  If not, see <http://www.gnu.org/licenses/>.

import curses
import subprocess
import sys

class Watchless(object):
    def __init__(self, *args):
        self._command = args[1:]
        self._popen = None

    def get_output(self):
        self._popen = subprocess.Popen(self._command, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        out = []
        while self._popen.returncode is None:
            out.extend(self._popen.stdout.readlines())
            self._popen.poll()
        return out

    def run(self, screen):
        # Print the header.
        screen.addstr(0, 0, "Every 2.0s: {0:s}".format(' '.join(self._command)))
        screen.refresh()

        # Get the output.
        out = self.get_output()

        # Calculate width and height of the output.
        height = len(out)
        width = max(len(o) for o in out)

        # Create a pad for the output and add the contents to it.
        pad = curses.newpad(height+1, width+1)
        for y, line in enumerate(out):
            pad.addstr(y, 0, line)

        # Start the pad two lines from the top and fill the rest of the screen.
        screenh, screenw = screen.getmaxyx()
        pad.refresh(0, 0, 2, 0, screenh-1, screenw-1)

        # Infinite loop for the time being.
        while True:
            continue

if __name__ == '__main__':
    wl = Watchless(*sys.argv)
    curses.wrapper(wl.run)
