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

"""DBus service object for general dispatching of commands."""

__all__ = [
    'Dispatcher',
    ]


import json
import logging

import dbus
import dbus.service

from friends.service.dispatcher import DBUS_INTERFACE, STUB


log = logging.getLogger(__name__)


class Dispatcher(dbus.service.Object):
    """This object mocks the official friends-dispatcher dbus API."""
    __dbus_object_path__ = '/com/canonical/friends/Dispatcher'

    def __init__(self, *ignore):
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(DBUS_INTERFACE, bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)

        self._succeed = True

    @dbus.service.method(DBUS_INTERFACE)
    def Contacts(self):
        pass

    @dbus.service.method(DBUS_INTERFACE)
    def Refresh(self):
        pass

    @dbus.service.method(DBUS_INTERFACE)
    def ClearIndicators(self):
        self._succeed = False

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='sss',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def Do(self, action, account_id='', arg='',
           success=STUB, failure=STUB):
        message = "Called with: action={}, account_id={}, arg={}".format(
            action, account_id, arg)
        success(message) if self._succeed else failure(message)

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='s',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def SendMessage(self, message, success=STUB, failure=STUB):
        message = "Called with: message={}".format(message)
        success(message) if self._succeed else failure(message)

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='sss',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def SendReply(self, account_id, message_id, msg,
                  success=STUB, failure=STUB):
        message = "Called with: account_id={}, message_id={}, msg={}".format(
            account_id, message_id, msg)
        success(message) if self._succeed else failure(message)

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='sss',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def Upload(self, account_id, uri, description, success=STUB, failure=STUB):
        message = "Called with: account_id={}, uri={}, description={}".format(
            account_id, uri, description)
        success(message) if self._succeed else failure(message)

    @dbus.service.method(DBUS_INTERFACE, in_signature='s', out_signature='s')
    def GetFeatures(self, protocol_name):
        return json.dumps(protocol_name.split())

    @dbus.service.method(DBUS_INTERFACE, in_signature='s', out_signature='s')
    def URLShorten(self, url):
        return str(len(url))
