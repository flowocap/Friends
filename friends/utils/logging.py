# friends-service -- send & receive messages from any social network
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
import errno
import logging
import logging.handlers

from gi.repository import GLib


LOG_FILENAME = os.path.join(
    os.path.realpath(os.path.abspath(GLib.get_user_cache_dir())),
    'friends', 'friends.log')
LOG_FORMAT = '{levelname:5}  {threadName:10}  {asctime}  {name:18}  {message}'
CSL_FORMAT = LOG_FORMAT.replace('  {asctime}', '')


def find_modules(prefix, result=[]):
    """Recursively searches for modules for which to enable logging."""
    for name in os.listdir(prefix):
        path = os.path.join(prefix, name)
        base, ext = os.path.splitext(name)
        if ext == '.py':
            result.append(
                '{}.{}'.format(prefix, base).replace(os.sep, '.'))
        elif os.path.isdir(path):
            find_modules(path, result)
    return result


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
    try:
        os.makedirs(os.path.dirname(filename))
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise

    # Set a global default of no logging. This is a workaround for a bug
    # where we were getting duplicated log records.
    logging.basicConfig(filename='/dev/null', level=100)

    # Install a rotating log file handler.  XXX There should be a
    # configuration file rather than hard-coded values.
    text_handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=20971520, backupCount=5)
    # Use str.format() style format strings.
    text_formatter = logging.Formatter(LOG_FORMAT, style='{')
    text_handler.setFormatter(text_formatter)

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(CSL_FORMAT, style='{')
    console_handler.setFormatter(console_formatter)

    for log_name in find_modules('friends'):
        log = logging.getLogger(log_name)
        if debug:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)
        if console:
            log.addHandler(console_handler)
        else:
            log.addHandler(text_handler)
