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

"""Other testing helpers."""

__all__ = [
    'FakeAccount',
    ]


import threading

from friends.utils.base import Base


class FakeAuth:
    pass


class FakeAccount:
    """A fake account object for testing purposes."""

    def __init__(self, service=None):
        self.access_token = None
        self.user_name = None
        self.user_id = None
        self.auth = FakeAuth()
        self.login_lock = threading.Lock()
        self.id = 'faker/than fake'
        self.protocol = Base(self)
