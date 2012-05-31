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
        x = 0
        y = 0
        pad.refresh(y, x, 2, 0, screenh-1, screenw-1)

        # Maximum x and y positions for the pad.
        maxx = width - (screenw - 1)
        maxy = height - (screenh - 3)

        # Infinite loop for the time being.
        while True:
            key = screen.getch()
            if key == curses.KEY_UP:
                y -= 1
            elif key == curses.KEY_DOWN:
                y += 1
            elif key == curses.KEY_NPAGE or key == 519:
                # 519 == control-down
                y += (screenh - 3)
            elif key == curses.KEY_PPAGE or key == 560:
                # 560 == control-up
                y -= (screenh - 3)
            elif key == curses.KEY_LEFT:
                x -= 1
            elif key == curses.KEY_RIGHT:
                x += 1
            elif key == curses.KEY_END:
                y = maxy
            elif key == curses.KEY_HOME:
                y = 0
            elif key == 539:
                # Control-left
                x -= (screenw - 1)
            elif key == 554:
                # Control-right
                x += (screenw - 1)
            y = max(min(y, maxy), 0)
            x = max(min(x, maxx), 0)
            pad.refresh(y, x, 2, 0, screenh-1, screenw-1)

if __name__ == '__main__':
    wl = Watchless(*sys.argv)
    curses.wrapper(wl.run)
