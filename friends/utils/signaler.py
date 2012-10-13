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

"""Internal signaler.

Used similar to dbus signals, but avoids that overhead for signaling events to
other internal components.  Similar also to zope.events but without the extra
dependency.
"""

__all__ = [
    'Signaler',
    'signaler',
    ]


class Signaler:
    """Internal signaler."""

    def __init__(self):
        # Map signal names to lists of callbacks.
        self._callbacks = {}

    def add_signal(self, name, callback):
        self._callbacks.setdefault(name, []).append(callback)

    def signal(self, name):
        for callback in self._callbacks.get(name, []):
            callback()


# The global signaler.  You don't *have* to use this, but it's convenient.
signaler = Signaler()
