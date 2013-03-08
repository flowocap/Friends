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

"""Persistent data store using JSON."""

__all__ = [
    'JsonCache',
    ]

import os
import json
import errno
import logging

from gi.repository import GLib


log = logging.getLogger(__name__)


class JsonCache(dict):
    """Simple dict that is backed by JSON data in a text file.

    Serializes itself to disk with every call to __setitem__, so it's
    not well suited for large, frequently-changing dicts. But useful
    for small dicts that change infrequently. Typically I expect this
    to be used for dicts that only change once or twice during the
    lifetime of the program, but needs to remember its state between
    invocations.

    If, for some unforeseen reason, you do need to dump a lot of data
    into this dict without triggering a ton of disk writes, it is
    possible to call dict.update with all the new values, followed by
    a single call to .write(). Keep in mind that the more data you
    store in this dict, the slower read/writes will be with each
    invocation. At the time of this writing, there are only three
    instances used throughout Friends, and they are all under 200
    bytes.
    """
    # Where to store all the json files.
    _root = os.path.join(GLib.get_user_cache_dir(), 'friends', '{}.json')

    def __init__(self, name):
        dict.__init__(self)
        self._path = self._root.format(name)

        try:
            with open(self._path, 'r') as cache:
                self.update(json.loads(cache.read()))
        except IOError as error:
            if error.errno != errno.ENOENT:
                raise
            # This writes '{}' to self._filename on first run.
            self.write()

    def write(self):
        """Write our dict contents to disk as a JSON string."""
        with open(self._path, 'w') as cache:
            cache.write(json.dumps(self))

    def __setitem__(self, key, value):
        """Write to disk every time dict is updated."""
        dict.__setitem__(self, key, value)
        self.write()
