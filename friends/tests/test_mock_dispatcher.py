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

"""Test the dispatcher directly, without dbus."""

__all__ = [
    'TestMockDispatcher',
    ]


import dbus.service
import unittest
import json

from dbus.mainloop.glib import DBusGMainLoop

from friends.service.mock_service import Dispatcher as MockDispatcher
from friends.service.dispatcher import Dispatcher
from friends.tests.mocks import LogMock, mock


# Set up the DBus main loop.
DBusGMainLoop(set_as_default=True)


def get_signature(klass, signature):
    """Extract dbus in/out signatures from a dbus class."""
    return [
        (m, getattr(getattr(klass, m), signature))
        for m in dir(klass)
        if hasattr(getattr(klass, m), signature)
        ]


class TestMockDispatcher(unittest.TestCase):
    """Ensure our mock Dispatcher has the same API as the real one."""

    def test_api_similarity(self):
        real = [m for m in dir(Dispatcher)
                if hasattr(getattr(Dispatcher, m), '_dbus_interface')]
        mock = [m for m in dir(MockDispatcher)
                if hasattr(getattr(MockDispatcher, m), '_dbus_interface')]
        self.assertEqual(real, mock)

    def test_in_signatures(self):
        real = get_signature(Dispatcher, '_dbus_in_signature')
        mock = get_signature(MockDispatcher, '_dbus_in_signature')
        self.assertEqual(real, mock)

    def test_out_signatures(self):
        real = get_signature(Dispatcher, '_dbus_out_signature')
        mock = get_signature(MockDispatcher, '_dbus_out_signature')
        self.assertEqual(real, mock)
