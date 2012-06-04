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
import time

class WatchLess(object):
    """The main class which implements the periodic execution and paged display
    of its output.
    """

    def __init__(self, command, interval=2):
        """
        :param command: The command to run.
        :param interval: The interval, in seconds, between execution.

        """
        self._command = command
        self.interval = interval

        # Some basic variables.
        self._popen = None
        self.dirty = False
        self.screen = None
        self.pad = None
        self.next_run = None

        # The width and height of the screen (i.e., the controlling terminal).
        self.screen_width = 0
        self.screen_height = 0

        # The width and height of the content we wish to display.
        self.content_height = 0
        self.content_width = 0

        # The width and height of each 'page' of the display (i.e, the maximum
        # area of content we can put on the screen at any one time). Smaller
        # than the screen width due to headers etc.
        self.page_height = 0
        self.page_width = 0

        # Position within the content of the top-left character of the display.
        self.x = 0
        self.y = 0

        # Maximum limits of the previous x and y variables.
        self.bottom = 0
        self.right = 0

        # Details for the header. The time of the last execution is stored so it
        # can be used when the window is resized etc.
        self.cmd_str = 'Every ' + str(self.interval) + 's: ' + ' '.join(self._command)
        self.cmd_str_len = len(self.cmd_str)
        self.header_time = None

    def process_command(self):
        """Execute the command if it is time to and return the results. This
        takes care of timing the repetition, watching for the output etc. in a
        non-blocking manner. Call it regularly.

        :return: If the command has finished executing and the output not yet
                 collected, a list of the output of the command, with each entry
                 corresponding to one line of output. Otherwise, ``None`` is
                 returned.

        """
        # Not currently running.
        if self._popen is None:
            # Time to run it again.
            if self.next_run is None or time.time() >= self.next_run:
                # Start the command running.
                self._popen = subprocess.Popen(self._command, shell=True,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)

                # Clear the buffer for any output.
                self._buffer = []

            # Nothing to return at this point.
            return None

        # Add any current output to our buffer.
        self._buffer.extend(self._popen.stdout.readlines())

        # Update the status of the process.
        self._popen.poll()

        # Still running.
        if self._popen.returncode is None:
            return None

        # Finished. Set the time to run it next and return the output.
        self._popen = None
        self.header_time = time.localtime()
        self.next_run = time.time() + self.interval
        return self._buffer

    def calculate_sizes(self):
        """Calculate the screen and page heights, plus the x- and y-positions of
        the bottom and right hand side of the content. Call whenever the
        content changes or a screen resize notification is received.

        """
        # Get the screen size, and from this the size of the page we can
        # display. Note we need to subtract one to get the 'index' of the last
        # available column and row.
        screenh, screenw = self.screen.getmaxyx()
        self.screen_height = screenh - 1
        self.screen_width = screenw - 1
        self.page_height = self.screen_height - 2
        self.page_width = self.screen_width

        # Calculate the maximum x and y positions for the pad. Note that this is
        # the (x, y) coordinate within the pad that should be at the top-left of
        # the available area so that the bottom/right content is visible at the
        # bottom-right corner of the display.
        self.right = self.content_width - self.page_width
        self.bottom = self.content_height - self.page_height

    def handle_keys(self):
        """Receive any keys pressed by the user and update the instance
        variables appropriately. If the display of the content needs to be
        changed (e.g., if the user scrolled the page), the ``dirty`` attribute
        is set to ``True``. Since curses reports screen resize events as a key
        press, resizes are also handled by this method.

        This method is designed to work in a non-blocking manner.

        NB. The x- and y-position attributes are not bounds checked after being
        changed; this needs to be performed by the caller. The reasoning behind
        this is that the bounds may change anyway (e.g., if the content has
        changed), so the caller would have to do the check anyway.

        """
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

        # Resize signals are sent via getch (go figure). When the screen is
        # resized, we need to recalculate the page area etc. A full screen
        # refresh (in addition to the pad refresh to update the content) is
        # needed to clear any artifacts.
        elif key == curses.KEY_RESIZE:
            self.calculate_sizes()
            self.update_header()
            self.screen.refresh()
            self.dirty = True

    def update_header(self):
        """Updates the header at the top of the screen with the command being
        executed and the time that the last execution finished. Should be called
        whenever execution finished or the screen is resized.

        """
        # Clear the existing header.
        self.screen.move(0, 0)
        self.screen.clrtoeol()

        # If the command has been executed, show the time the execution
        # completed.
        if self.header_time:
            # Let the time module convert it to a string in the appropriate
            # locale.
            tstr = time.strftime('%c', self.header_time)
            tlen = len(tstr)
            tpos = self.screen_width - tlen
            if tpos < 0:
                self.screen.addstr(0, 0, tstr[:self.screen_width])
            else:
                self.screen.addstr(0, tpos, tstr)
        else:
            tpos = self.screen_width

        # The 'Every Ns: ' bit takes at least 10 characters. Add in the space
        # between the command and the date, plus at least one character for the
        # command, and we need an absolute minimum of 12 characters to show the
        # command string in.
        if tpos >= 12:
            # If the whole command string cannot fit before the date, truncate it
            # and append an ellipsis.
            if self.cmd_str_len > (tpos - 2):
                self.screen.addstr(0, 0, self.cmd_str[:tpos-5])
                self.screen.addstr(0, tpos-5, "...")
            else:
                self.screen.addstr(0, 0, self.cmd_str)

        # No point doing all this work if we don't show it...
        self.screen.refresh()

    def run(self, screen):
        """Run the display. This takes control of the execution and blocks until
        the user stops it.

        :param screen: The curses screen to display the content on.

        """
        # Save the screen for future reference.
        self.screen = screen

        # If this terminal supports colours, tell it to use its default colours
        # for this screen.
        if curses.has_colors():
            curses.use_default_colors()

        # Disable the cursor if possible.
        try:
            curses.curs_set(0)
        except curses.error:
            # Try to set it to 'normal' rather than 'very visible' if we can.
            try:
                curses.curs_set(1)
            except curses.error:
                pass

        # Enter no-delay mode so that getch() is non-blocking.
        self.screen.nodelay(True)

        # Create a pad for the output of the command.
        self.pad = curses.newpad(1, 1)

        # Calculate size of page area etc.
        self.calculate_sizes()

        # Show the header so the user knows things have started up.
        self.update_header()

        # Keep going as long as we need to.
        while True:
            # Handle any key presses.
            self.handle_keys()

            # Check for output.
            content = self.process_command()
            if content is not None:
                # There is no point going through the output twice, once to
                # calculate the width and once to add it to the pad. Instead,
                # we'll resize as we go. To avoid too much resizing, we'll
                # double the width each time its too small, and then do a final
                # resize at the end. The width of the previous output is a
                # reasonable starting point.
                self.content_height = len(content)
                w = self.content_width or 1
                self.pad.resize(self.content_height + 1, w + 1)

                # Add each line.
                for y, line in enumerate(content):
                    # Update the approximate and real widths of the pad.
                    l = len(line)
                    if l > w:
                        while l > w:
                            w *= 2
                            self.content_width = l
                        self.pad.resize(self.content_height + 1, w + 1)

                    # Add this line.
                    self.pad.addstr(y, 0, line)

                # Resize the pad to the final size.
                self.pad.resize(self.content_height + 1, self.content_width + 1)

                # Recalculate page boundaries etc and mark for redrawing.
                self.calculate_sizes()
                self.dirty = True
                self.update_header()

            # We need to refresh the screen.
            if self.dirty:
                # Ensure the position is kept within limits.
                self.y = max(min(self.y, self.bottom), 0)
                self.x = max(min(self.x, self.right), 0)

                # Redraw and we're done.
                self.pad.refresh(self.y, self.x, 2, 0, self.screen_height, self.screen_width)
                self.dirty = False

            # Sleep a bit to avoid hogging all the CPU.
            time.sleep(0.01)

if __name__ == '__main__':
    wl = WatchLess(command=sys.argv[1:])
    curses.wrapper(wl.run)
