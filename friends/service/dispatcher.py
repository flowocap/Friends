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

"""DBus service object for general dispatching of commands."""

__all__ = [
    'Dispatcher',
    ]


import json
import logging
import threading

import dbus
import dbus.service

from gi.repository import GLib

from friends.utils.account import AccountManager
from friends.utils.avatar import Avatar
from friends.utils.manager import protocol_manager
from friends.utils.signaler import signaler

log = logging.getLogger('friends.service')


class Dispatcher(dbus.service.Object):
    """This is the primary handler of dbus method calls."""
    __dbus_object_path__ = '/com/canonical/friends/Service'

    def __init__(self, mainloop, interval):
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(
            'com.canonical.Friends.Service', bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)
        self.mainloop = mainloop
        self._interval = interval
        self.account_manager = AccountManager(self.Refresh)
        self._timer_id = None
        signaler.add_signal('ConnectionOnline', self._on_connection_online)
        signaler.add_signal('ConnectionOffline', self._on_connection_offline)
        self._on_connection_online()

    def _on_connection_online(self):
        if not self._timer_id:
            self._timer_id = GLib.timeout_add_seconds(
                self._interval, self.Refresh)

    def _on_connection_offline(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    @property
    def online(self):
        return self._timer_id is not None

    @dbus.service.method('com.canonical.Friends.Service')
    def Refresh(self):
        # TODO this method is too untestable here; split it off somewhere
        # else for easier testing, then invoke it from here.
        log.debug('Refresh requested')
        # Wait for all previous actions to complete before
        # starting a load of new ones.
        current = threading.current_thread()
        for thread in threading.enumerate():
            if thread != current:
                thread.join()

        if not self.online:
            return

        # account.protocol() starts a new thread for each account present
        # and returns immediately. So this method should be quick unless
        # there are a bunch of old, incomplete jobs waiting around from
        # the last refresh.
        for account in self.account_manager.get_all():
            try:
                account.protocol('receive')
            except NotImplementedError:
                # If a protocol doesn't support receive then ignore it.
                pass

        # Always return True, or else GLib mainloop will stop invoking it.
        return True

    @dbus.service.method('com.canonical.Friends.Service', in_signature='s')
    def UpdateIndicators(self, stream):
        """Update counts in messaging indicators.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(
                'com.canonical.Friends.Service',
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, 'com.canonical.Friends.Service')
            service.UpdateIndicators('stream')
        """
        pass #TODO

    @dbus.service.method('com.canonical.Friends.Service', in_signature='sss')
    def Do(self, action, account_id=None, message_id=None):
        """Performs a certain operation specific to individual messages.

        This is how the client initiates retweeting, liking, unliking, etc.
        example:
            import dbus
            obj = dbus.SessionBus().get_object(
                'com.canonical.Friends.Service',
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, 'com.canonical.Friends.Service')
            service.Do('like', account, message_id)
        """
        if not self.online:
            return
        log.debug('{}-ing {}'.format(action, message_id))
        account = self.account_manager.get(account_id)
        if account is not None:
            account.protocol(action, message_id=message_id)

    @dbus.service.method('com.canonical.Friends.Service', in_signature='s')
    def SendMessage(self, message):
        """Posts a message/status update to all send_enabled accounts.

        It takes one argument, which is a message formated as a string.
        example:
            import dbus
            obj = dbus.SessionBus().get_object(
                'com.canonical.Friends.Service',
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, 'com.canonical.Friends.Service')
            service.SendMessage('Your message')
        """
        if not self.online:
            return
        for account in self.account_manager.get_all():
            if account.send_enabled:
                account.protocol('send', message)

    @dbus.service.method('com.canonical.Friends.Service', out_signature='s')
    def GetFeatures(self, protocol_name):
        """Returns a list of features supported by service as json string.

        example:
            import dbus, json
            obj = dbus.SessionBus().get_object(
                'com.canonical.Friends.Service',
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, 'com.canonical.Friends.Service')
            features = json.loads(service.GetFeatures('facebook'))
        """
        protocol = protocol_manager.protocols.get(protocol_name)
        return json.dumps(protocol.get_features())

    @dbus.service.method('com.canonical.Friends.Service',
                         in_signature='s',
                         out_signature='s')
    def GetAvatarPath(self, url):
        """Returns the path to the cached avatar image as a string.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(
                'com.canonical.Friends.Service',
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, 'com.canonical.Friends.Service')
            avatar = service.GetAvatar(url)
        """
        if self.online:
            # Download the image to the cache, if necessary.
            return Avatar.get_image(url)
        else:
            # Report the cache location without attempting download.
            return Avatar.get_path(url)

    @dbus.service.method('com.canonical.Friends.Service')
    def Quit(self):
        """Shutdown the service.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(
                'com.canonical.Friends.Service',
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, 'com.canonical.Friends.Service')
            service.Quit()
        """
        log.info('Friends Service is being shutdown')
        logging.shutdown()
        self.mainloop.quit()
