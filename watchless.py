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
import optparse
import subprocess
import sys
import time

# Version information.
version = '0.1.0'
version_info = (0, 1, 0, 'final', 0)
hexversion = 0x000100f0

# Set up a commandline parser.
usage = """Usage: %prog [options] <command>

Execute a command periodically and display the output."""
parser = optparse.OptionParser(usage=usage, version="%prog "+version)
parser.disable_interspersed_args()
parser.add_option('-n', '--interval', dest="interval", type="float", default=2.0,
                  help="time to wait between updates [default: %defaults]",
                  metavar="seconds")
parser.add_option('-p', '--precise', dest="precise_mode", action="store_true",
                  help="try to run the command every <interval> seconds, "
                  "rather than using <interval> second gaps between one "
                  "finishing and the next starting", default=False)
parser.add_option('-d', '--differences', dest="differences",
                  action="store_true", help="Show differences in output "
                  "between runs. Use --differences=cumulative to show all the "
                  "positions that have changed since the first run.",
                  default=False)
parser.add_option('-b', '--beep', dest="beep", action="store_true",
                  default=False, help="Beep when <command> exits with a "
                  "non-zero return code.")
parser.add_option('-e', '--errexit', dest="errexit", action="store_true",
                  default=False,
                  help="Exit when the return code from <command> is non-zero")
parser.add_option('-t', '--no-title', dest="header", action="store_false",
                  help="don't show the header at the top of the screen",
                  default=True)

# List of characters which if present in a command indicate it needs to be run
# in an external command.
shell_chars = ('*', '|', '&', '(', '[', ' ')

class WatchLess(object):
    """The main class which implements the periodic execution and paged display
    of its output.
    """

    # Copy module version numbering to class.
    version = version
    version_info = version_info
    hexversion = hexversion

    def __init__(self, command, interval=2, precise_mode=False, shell=None,
                 differences=None, beep=False, errexit=False, header=True):
        """The standard Python subprocess module is used to execute the command.
        This can either do so within the current process (``shell=False``) or
        using an external shell (``shell=True``). In general, ``shell=False`` is
        preferred except when the command contains special shell characters
        (e.g., the globbing character '*') which needs to be run in a shell to
        work properly. In this case, it usually has to be escaped when entering
        it and so the command passed in is a single-entry list.

        If the ``shell`` parameter is ``None``, the class will try to guess the
        appropriate setting using the following two steps:

            1. If the command list has more than one item, assume the command
               was not escaped when entered and therefore has no special
               characters; set ``shell`` to ``False``. Otherwise go to 2.
            2. If the single entry has any special characters (the list of which
               is defined in the module-level variable ``shell_chars``), then
               set ``shell`` to ``True``. Otherwise set it to ``False``.

        :param command: The command to run as a list of one or more strings.
        :param interval: The interval, in seconds, between execution.
        :param shell: Whether to spawn an external shell to run the command in.
                      If ``None``, the class tries to guess the appropriate
                      value based on the command.
        :param precise_mode: Normally, ``interval`` seconds are left between one
                             execution finishing and the next starting. Enabling
                             precise mode means that the class will try to time
                             it so there are ``interval`` seconds between the
                             start of each execution. If the command takes
                             longer than ``interval`` seconds to complete, then
                             this target obviously cannot be met; instead, the
                             command will be executed as often as possible.
        :param differences: Whether or not to highlight differences in the
                            output. Can be ``None``, for no highlighting,
                            ``'sequential'`` to show the differences between
                            sequential runs of the output, or ``'cumulative'``
                            to show all the characters that have changed at
                            least once since the first run.
        :param beep: Beep when the command results in a non-zero return code.
        :param errexit: Exit when the command results in a non-zero return code.
        :param header: Whether or not to show the header at the top of the
                       screen.

        """
        # Details for the header. The time of the last execution is stored so it
        # can be used when the window is resized etc.
        # We do this before checking the command is in the right format for the
        # shell setting to avoid having to special-case depending on whether the
        # command is then a string or a list -- at this point it is a list in
        # either case and this gives the correct display.
        self.cmd_str = 'Every ' + str(interval) + 's: ' + ' '.join(command)
        self.cmd_str_len = len(self.cmd_str)
        self.header_time = None

        # Try to auto-detect if we need shell mode.
        if shell is None:
            # Multiple arguments --> shell not needed.
            if len(command) > 1:
                shell = False

            # One argument --> check for presence of special characters which
            # need an external shell to handle properly.
            else:
                shell = any(char in command[0] for char in shell_chars)

                # Shell mode needed --> command needs to be a single string.
                if shell:
                    command = command[0]

        # Shell mode forced on. In this case the command needs to be a single
        # string.
        elif shell:
            command = ' '.join(command)

        # Store the details we were given.
        self.command = command
        self.shell = shell
        self.interval = interval
        self.precise_mode = precise_mode
        self.errexit = errexit
        self.beep = beep
        self.header = header

        # Precompute difference info for efficiency.
        self.differences = differences is not None
        if self.differences:
            if differences.lower().startswith('c'):
                self.c_diff = True
            else:
                self.c_diff = False

        # Some basic variables.
        self._process = None
        self.dirty = False
        self.screen = None
        self.pad = None
        self.next_run = None

        # The width and height of the screen (i.e., the controlling terminal).
        self.screen_width = 0
        self.screen_height = 0

        # The y-position, width and height of the content we wish to display.
        self.content_y = 2 if self.header else 0
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

        # In Python 3 and above, the subprocess returns raw bytes which we need
        # to decode into strings. Lets figure out the appropriate encoding to
        # decode with.
        if sys.hexversion >= 0x03000000:
            import locale
            locale.setlocale(locale.LC_ALL, '')
            self.decode = locale.getpreferredencoding()
        else:
            self.decode = False

    @classmethod
    def from_arguments(klass, program_name, *args):
        """Factory method which takes a set of command line arguments and
        returns an instance of WatchLess set up as per those arguments. If the
        user asks for a help message, or there are errors in the arguments, the
        appropriate output will be printed and a SystemExit raised to indicate
        processing is complete.

        :param program_name: The name of the program as it should be displayed
                             in any help/usage messages.

        """
        args = list(args)

        # Figure out the difference mode the user wants, if any. optparse does
        # not allow optional arguments to options, so to make the command-line
        # interface to match that of the original watch command, we need to do a
        # bit of pre-processing here.
        diff_mode = 'sequential'
        for i, arg in enumerate(args):
            if arg.startswith('--differences='):
                args[i], diff_mode = arg.split('=', 1)

        # Run the arguments through the parser. This will print errors/help and
        # exit as appropriate.
        parser.prog = program_name
        options, command = parser.parse_args(args)

        # No command given.
        if not command:
            sys.stdout.write('Error: no command given.\n\n')
            parser.print_help()
            raise SystemExit(1)

        # Pull the arguments that were given into a dictionary.
        initargs = {}
        if options.interval is not None:
            initargs['interval'] = options.interval
        initargs['precise_mode'] = options.precise_mode
        initargs['errexit'] = options.errexit
        initargs['beep'] = options.beep
        initargs['header'] = options.header

        # Translate command line difference setting into the format the
        # initialiser expects.
        if options.differences:
            initargs['differences'] = diff_mode

        # Create the object and we're done.
        return klass(command, **initargs)

    def process_command(self):
        """Execute the command if it is time to and return the results. This
        takes care of timing the repetition, watching for the output etc. in a
        non-blocking manner. Call it regularly.

        :return: A tuple (return_code, output), where the output is in a list of
                 lines. If the command has not finished, the return code is
                 ``None``. If there is no new output to return at this time, an
                 empty list is returned.

        """
        # Not currently running.
        if self._process is None:
            t = time.time()

            # Time to run it again.
            if self.next_run is None or t >= self.next_run:
                # Start the command running.
                self._process = subprocess.Popen(self.command, shell=self.shell,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)

                # If we are running under precise mode, set the time for the
                # next run.
                if self.precise_mode:
                    self.next_run = (self.next_run or t) + self.interval

                # Update the header so that the inverted version is shown to
                # indicate the command is being run.
                self.update_header()

            # Nothing to return at this point.
            return None, []

        # Gather any current output.
        output = self._process.stdout.readlines()
        output.extend(self._process.stderr.readlines())

        # Update the status of the process.
        self._process.poll()

        # Still running.
        if self._process.returncode is None:
            return None, output

        # Finished. Set the time to run it next and return the output.
        rcode = self._process.returncode
        self._process = None
        self.header_time = time.localtime()
        if not self.precise_mode:
            self.next_run = time.time() + self.interval
        return rcode, output

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
        self.page_height = self.screen_height - self.content_y
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
        if not self.header:
            return

        # How to display the header: inverted if the command is currently
        # running, normal if it is not.
        if self._process is not None:
            mode = curses.A_REVERSE
        else:
            mode = curses.A_NORMAL

        # Write over the existing header. By clearing it this way rather than
        # with the curses clrtoeol() function, the 'background' of the header
        # will also be inverted if appropriate.
        self.screen.addstr(0, 0, ' ' * self.screen_width, mode)

        # If the command has been executed, show the time the execution
        # completed.
        if self.header_time:
            # Let the time module convert it to a string in the appropriate
            # locale.
            tstr = time.strftime('%c', self.header_time)
            tlen = len(tstr)
            tpos = self.screen_width - tlen
            if tpos < 0:
                self.screen.addstr(0, 0, tstr[:self.screen_width], mode)
            else:
                self.screen.addstr(0, tpos, tstr, mode)
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
                self.screen.addstr(0, 0, self.cmd_str[:tpos-5], mode)
                self.screen.addstr(0, tpos-5, "...", mode)
            else:
                self.screen.addstr(0, 0, self.cmd_str, mode)

    def run(self, screen):
        """Run the display. This takes control of the execution and blocks until
        the user stops it.

        :param screen: The curses screen to display the content on.

        """
        # Wrap the whole thing in a try-except block so we can detect the user
        # pressing Ctrl-C to exit.
        try:
            # Save the screen for future reference.
            self.screen = screen

            # If this terminal supports colours, tell it to use its default
            # colours for this screen.
            if curses.has_colors():
                curses.use_default_colors()

            # Disable the cursor if possible.
            try:
                curses.curs_set(0)
            except curses.error:
                # Try to set it to 'normal' rather than 'very visible' if we
                # can.
                try:
                    curses.curs_set(1)
                except curses.error:
                    pass

            # Enter no-delay mode so that getch() is non-blocking.
            self.screen.nodelay(True)

            # Create a pad for the output of the command.
            self.pad = curses.newpad(1, 1)

            # And a second one for new output.
            newpad = curses.newpad(1, 1)

            # State variables used when updating the new pad.
            new_h = 0
            new_w = 0
            cur_l = 0

            # Calculate size of page area etc.
            self.calculate_sizes()

            # Show the header so the user knows things have started up.
            self.update_header()
            self.screen.refresh()

            # Keep going as long as we need to.
            first_run = True
            while True:
                # Handle any key presses.
                self.handle_keys()

                # Check for output.
                rcode, output = self.process_command()

                # New output.
                if output:
                    # Increase the height of the pad to suit.
                    new_h += len(output)
                    newpad.resize(new_h + 1, new_w + 1)

                    # Process the output line by line.
                    for line in output:
                        # Decode the line to a string if needed.
                        if self.decode:
                            line = line.decode(self.decode)

                        # Increase the width of the output if needed.
                        if len(line) > new_w:
                            new_w = len(line)
                            newpad.resize(new_h + 1, new_w + 1)

                        # If we are doing a diff, we need to add the output
                        # character by character.
                        if self.differences and not first_run:
                            for x, c in enumerate(line):
                                # Get the character previously in this position.
                                # The lower 8 bits of the returned value is the
                                # character itself, the rest is the display
                                # attributes.
                                temp = self.pad.inch(cur_l, x)

                                # If we are doing a cumulative diff, we start
                                # with the previous attributes, otherwise we
                                # start from normal.
                                if self.c_diff:
                                    attr = temp & ~0xFF
                                else:
                                    attr = curses.A_NORMAL

                                # Highlight the display if the new character
                                # differs from the old.
                                c = ord(c)
                                oldc = temp & 0xFF
                                if c != oldc:
                                    attr |= curses.A_STANDOUT

                                # Add this character.
                                newpad.addch(cur_l, x, c, attr)

                        # Not doing a diff, we can just add the line.
                        else:
                            newpad.addstr(cur_l, 0, line)

                        # Done with this line.
                        cur_l += 1

                # Process has finished.
                if rcode is not None:
                    # Non-zero return code.
                    if rcode != 0:
                        if self.beep:
                            sys.stdout.write(chr(7))
                            sys.stdout.flush()
                        if self.errexit:
                            break

                    # Switch the pads over.
                    self.pad, newpad = newpad, self.pad
                    self.content_width = new_w
                    self.content_height = new_h

                    # Prepare for the refresh.
                    self.calculate_sizes()
                    self.screen.clear()
                    self.update_header()
                    self.dirty = True

                    # Prepare the 'new' pad for the next run.
                    newpad.clear()
                    first_run = False
                    new_w = 0
                    new_h = 0
                    cur_l = 0

                # We need to refresh the screen.
                if self.dirty:
                    # Ensure the position is kept within limits.
                    self.y = max(min(self.y, self.bottom), 0)
                    self.x = max(min(self.x, self.right), 0)

                    # Redraw and we're done.
                    self.screen.refresh()
                    self.pad.refresh(self.y, self.x, self.content_y, 0, self.screen_height,
                                     self.screen_width)
                    self.dirty = False

                # Sleep a bit to avoid hogging all the CPU.
                time.sleep(0.01)

        # User pressed Ctrl-C.
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    wl = WatchLess.from_arguments(*sys.argv)
    curses.wrapper(wl.run)
