watchless
=========

*Version 0.1.0 - 5 June 2012*

watchless is a Python clone of the standard Unix ``watch`` command with the
addition of paging support along the lines of another standard Unix command,
``less``.

Requirements
============

* Python 2.4 or greater with the curses module available (should be present on
  Unix-based systems; Windows has no support by default, although some Cygwin
  builds *may* have it and there are third-party libraries claim to implement
  it -- your mileage may vary).

Usage
=====

``./watchless.py [options] <command>``

Options
-------

* ``--version`` - show program's version number and exit
* ``-h``, ``--help`` - show a help message and exit
* ``-n <seconds>``, ``--interval=<seconds>`` - time to wait between updates [default: 2.0s]
* ``-p``, ``--precise`` - rather than waiting *interval* seconds between one
  run finishing and the next starting, try to time it so there are *interval*
  seconds between each run starting. If the command takes longer than
  *interval* seconds to run, then it will be run as often as possible.
* ``-d``, ``--differences`` - highlight the differences in the output of
  sequential runs of the command. If you want to highlight all the positions
  that have ever changed (i.e., a 'sticky' highlight), use
  ``--differences=cumulative``. Note you cannot use ``-d cumulative`` as this
  leads to an ambiguity (is ``cumulative`` an argument or the command to
  execute?) since the argument is optional.
* ``-b``, ``--beep`` - beep if the command exits with a non-zero return code.
* ``-e``, ``--errexit`` - exit if the command exits with a non-zero return code.
* ``-t``, ``--no-title`` - do not show the header with the command and last execution time.

Future work
===========

* Support more of the standard ``watch`` options.

Bug reports
===========

File any bug reports or feature requests in the project's GitHub issue tracker at
<https://github.com/blairbonnett/watchless/issues>.

Copyright
=========

watchless is copyright (c) 2012 Blair Bonnett

License
=======

watchless is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

watchless is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
watchless.  If not, see <http://www.gnu.org/licenses/>.
