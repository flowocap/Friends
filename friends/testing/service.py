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

"""Additional DBus service to aid in testing."""

__all__ = [
    'TestService',
    ]


import logging

import dbus
import dbus.service

from friends.utils.signaler import signaler


log = logging.getLogger('friends.service')


class TestService(dbus.service.Object):
    __dbus_object_path__ = '/com/canonical/friends/Test'

    def __init__(self, monitor):
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(
            'com.canonical.Friends.Test', bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)
        self.id = 0
        self.connection_monitor = monitor
        # Connect signals
        self.signal_counter = 0
        def online_callback():
            self.signal_counter += 1
        def offline_callback():
            self.signal_counter -= 1
        signaler.add_signal('ConnectionOnline', online_callback)
        signaler.add_signal('ConnectionOffline', offline_callback)

    @dbus.service.method('com.canonical.Friends.Test', out_signature='i')
    def SignalTestOn(self):
        self.connection_monitor.ConnectionOnline()
        return self.signal_counter

    @dbus.service.method('com.canonical.Friends.Test', out_signature='i')
    def SignalTestOff(self):
        self.connection_monitor.ConnectionOffline()
        return self.signal_counter
