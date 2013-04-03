# friends-dispatcher -- send & receive messages from any social network
# Copyright (C) 2012  Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Logging utilities."""

import os
import logging
import logging.handlers
import oauthlib.oauth1

from gi.repository import GLib

from friends.errors import ignored


# Set a global default of no logging. This is a workaround for a bug
# where we were getting duplicated log records.
logging.basicConfig(filename='/dev/null', level=100)


# Disable logging in oauthlib because it is very verbose.
oauthlib.oauth1.rfc5849.logging.debug = lambda *ignore: None


LOG_FILENAME = os.path.join(
    os.path.realpath(os.path.abspath(GLib.get_user_cache_dir())),
    'friends', 'friends.log')
LOG_FORMAT = '{levelname:5}  {threadName:10}  {asctime}  {name:18}  {message}'
CSL_FORMAT = LOG_FORMAT.replace('  {asctime}', '')


def initialize(console=False, debug=False, filename=None):
    """Initialize the Friends service logger.

    :param console: Add a console logger.
    :type console: bool
    :param debug: Set the log level to DEBUG instead of INFO.
    :type debug: bool
    :param filename: Alternate file to log messages to.
    :type filename: string
    """
    # Start by ensuring that the directory containing the log file exists.
    if filename is None:
        filename = LOG_FILENAME
    with ignored(FileExistsError):
        os.makedirs(os.path.dirname(filename))

    # Install a rotating log file handler.  XXX There should be a
    # configuration file rather than hard-coded values.
    text_handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=20971520, backupCount=5)
    # Use str.format() style format strings.
    text_formatter = logging.Formatter(LOG_FORMAT, style='{')
    text_handler.setFormatter(text_formatter)

    log = logging.getLogger()
    log.addHandler(text_handler)

    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    if console:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(CSL_FORMAT, style='{')
        console_handler.setFormatter(console_formatter)
        log.addHandler(console_handler)
