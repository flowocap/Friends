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

"""Connection monitoring dbus service."""

__all__ = [
    'ConnectionMonitor',
    ]


import logging

import dbus
import dbus.exceptions
import dbus.service

from friends.utils.signaler import signaler


NM_DBUS_SERVICE = 'org.freedesktop.NetworkManager'
NM_DBUS_OBJECT_PATH = '/org/freedesktop/NetworkManager'
NM_DBUS_INTERFACE = 'org.freedesktop.NetworkManager'


class _States08998:
    """State values when network manager version >= 0.8.998."""
    ASLEEP = 10
    DISCONNECTED = 20
    CONNECTING = 40
    CONNECTED = 70


class _States08997:
    """State values when network manager version < 0.8.998."""
    ASLEEP = 1
    CONNECTING = 2
    CONNECTED = 3
    DISCONNECTED = 4


log = logging.getLogger('friends.service')
_State = None


class ConnectionMonitor(dbus.service.Object):
    """Connection monitoring dbus service."""
    __dbus_object_path__ = '/com/canonical/friends/Connection'

    def __init__(self):
        global _State
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(
            'com.canonical.Friends.Connection', bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)
        # Grab a connection to the system bus so that we can react to network
        # manager events.
        try:
            self.system_bus = dbus.SystemBus()
            self.network_manager = self.system_bus.get_object(
                NM_DBUS_SERVICE, NM_DBUS_OBJECT_PATH)
            self.network_manager.connect_to_signal(
                'StateChanged', self._on_connection_changed)
            # What version of network manager is being used?
            version = str(
                self.network_manager.Get(NM_DBUS_INTERFACE, 'Version'))
            log.debug('Network manager {} found'.format(version))
            version_tuple = tuple(int(part) for part in version.split('.'))
            _State = (_States08998
                      if version_tuple >= (0, 8, 998)
                      else _States08997)
        except dbus.exceptions.DBusException:
            log.exception('Cannot communicate with network manager')
            self.network_manager = None

    def _on_connection_changed(self, state):
        """React to changes in network manager state."""
        log.debug('Network status received: {:d}'.format(state))
        if state == _State.CONNECTED:
            log.info('Network state changed to Online')
            self.ConnectionOnline()
        elif state == _State.DISCONNECTED:
            log.info('Network stated changed to Offline')
            self.ConnectionOffline()

    @dbus.service.signal('com.canonical.Friends.Connection')
    def ConnectionOnline(self):
        # Perform internal callbacks.
        signaler.signal('ConnectionOnline')

    @dbus.service.signal('com.canonical.Friends.Connection')
    def ConnectionOffline(self):
        # Perform internal callbacks.
        signaler.signal('ConnectionOffline')

    @dbus.service.method('com.canonical.Friends.Connection')
    def isConnected(self):
        if self.network_manager is None:
            log.info('Cannot determine network status, assuming online')
            return True
        try:
            return self.network_manager.state() == _State.CONNECTED
        except dbus.exceptions.DBusException:
            log.exception('Cannot determine network manager state')
            return True
