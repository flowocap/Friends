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

"""Test the internal signaler."""

__all__ = [
    'TestSignaler',
    ]


import unittest

from friends.utils.signaler import Signaler


class TestSignaler(unittest.TestCase):
    """Test the internal signaler."""

    def test_signal(self):
        # Add a callback for a signal.
        happened = 0
        def callback():
            nonlocal happened
            happened += 1
        signaler = Signaler()
        signaler.add_signal('Happened', callback)
        signaler.signal('Happened')
        self.assertEqual(happened, 1)
