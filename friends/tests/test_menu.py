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

"""Test the MenuManager class."""

__all__ = [
    'TestMenu',
    ]


import unittest

from friends.utils.menus import MenuManager
from friends.tests.mocks import mock


def callback_stub(*ignore):
    pass


class TestMenu(unittest.TestCase):
    """Test MenuManager class."""

    def setUp(self):
        self.menu = MenuManager(callback_stub, callback_stub)
        self.menu.messaging = mock.Mock()

    def test_unread_count_visible(self):
        # Calling update_unread_count() with a non-zero value will make the
        # count visible.
        self.menu.update_unread_count(42)
        self.menu.messaging.set_source_count.assert_called_once_with(
            'unread', 42)

    def test_unread_count_invisible(self):
        # Calling update_unread_count() with a zero value will make the count
        # invisible.
        self.menu.update_unread_count(0)
        self.menu.messaging.remove_source.assert_called_once_with(
            'unread')
