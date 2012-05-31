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
        self.x = 0
        self.y = 0
        self.bottom = 0
        self.right = 0
        self.page_height = 0
        self.page_width = 0
        self.dirty = False
        self.screen = None

    def get_output(self):
        self._popen = subprocess.Popen(self._command, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        out = []
        while self._popen.returncode is None:
            out.extend(self._popen.stdout.readlines())
            self._popen.poll()
        return out

    def handle_keys(self):
        # Get any pending key. In no-delay mode, -1 means there was no key
        # waiting.
        key = self.screen.getch()
        if key == -1:
            return

        # Page movement keys.
        if key == curses.KEY_UP:
            self.y -= 1
            self.dirty = True
        elif key == curses.KEY_DOWN:
            self.y += 1
            self.dirty = True
        elif key == curses.KEY_NPAGE or key == 519:
            # 519 == control-down
            self.y += self.page_height
            self.dirty = True
        elif key == curses.KEY_PPAGE or key == 560:
            # 560 == control-up
            self.y -= self.page_height
            self.dirty = True
        elif key == curses.KEY_LEFT:
            self.x -= 1
            self.dirty = True
        elif key == curses.KEY_RIGHT:
            self.x += 1
            self.dirty = True
        elif key == curses.KEY_END:
            self.y = self.bottom
            self.dirty = True
        elif key == curses.KEY_HOME:
            self.y = 0
            self.dirty = True
        elif key == 539:
            # Control-left
            self.x -= self.page_width
            self.dirty = True
        elif key == 554:
            # Control-right
            self.x += self.page_width
            self.dirty = True

    def run(self, screen):
        # Save the screen for future reference.
        self.screen = screen

        # Enter no-delay mode so that getch() is non-blocking.
        self.screen.nodelay(True)

        # Print the header.
        screen.addstr(0, 0, "Every 2.0s: {0:s}".format(' '.join(self._command)))
        screen.refresh()

        # Get the output.
        out = self.get_output()

        # Calculate width and height of the output.
        height = len(out)
        width = max(len(o) for o in out)

        # Create a pad for the output and add the contents to it. The +1 is to
        # give us a buffer character/row - when addstr() is done, the cursor is
        # moved to the character after the end of the string. If there is not
        # room in the pad for this, an exception is raised.
        pad = curses.newpad(height+1, width+1)
        for y, line in enumerate(out):
            pad.addstr(y, 0, line)

        # Get the screen size, and from this the size of the page we can
        # display. Note we need to subtract one to get the 'index' of the last
        # available column and row.
        screenh, screenw = screen.getmaxyx()
        screenh -= 1; screenw -= 1
        self.page_height = screenh - 2
        self.page_width = screenw

        # Calculate the maximum x and y positions for the pad. Note that this is
        # the (x, y) coordinate within the pad that should be at the top-left of
        # the available area so that the bottom/right content is visible at the
        # bottom-right corner of the display.
        self.right = width - self.page_width
        self.bottom = height - self.page_height

        # Display the pad, leaving room for the header plus a blank line.
        pad.refresh(self.y, self.x, 2, 0, screenh, screenw)

        # Infinite loop for the time being.
        while True:
            # Handle any key presses.
            self.handle_keys()

            # We need to refresh the screen.
            if self.dirty:
                # Ensure the position is kept within limits.
                self.y = max(min(self.y, self.bottom), 0)
                self.x = max(min(self.x, self.right), 0)

                # Redraw and we're done.
                pad.refresh(self.y, self.x, 2, 0, screenh, screenw)
                self.dirty = False

if __name__ == '__main__':
    wl = Watchless(*sys.argv)
    curses.wrapper(wl.run)
