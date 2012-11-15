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
from friends.utils.manager import protocol_manager
from friends.utils.signaler import signaler
from friends.utils.menus import MenuManager
from friends.utils.model import persist_model, Model

log = logging.getLogger(__name__)

DBUS_INTERFACE = 'com.canonical.Friends.Service'


class Dispatcher(dbus.service.Object):
    """This is the primary handler of dbus method calls."""
    __dbus_object_path__ = '/com/canonical/friends/Service'

    def __init__(self, mainloop, interval):
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(DBUS_INTERFACE, bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)
        self.mainloop = mainloop
        self._interval = interval
        self.account_manager = AccountManager()

        self._unread_count = 0
        self.menu_manager = MenuManager(self.Refresh, self.mainloop.quit)
        Model.connect('row-added', self._increment_unread_count)

        self._timer_id = None
        signaler.add_signal('ConnectionOnline', self._on_connection_online)
        signaler.add_signal('ConnectionOffline', self._on_connection_offline)
        self._on_connection_online()

        # TODO: Everything from this line to the end of this method
        # will need to be removed from here if we ever move to an
        # event-based, dbus-invocation style architecture, as opposed
        # to the current long-running-process architecture.
        self.Refresh()

        # Eventually, this bit will need to be moved into it's own
        # dbus method, such that some cron-like service can invoke
        # that method periodically. For now we are just doing it at
        # startup.
        for account in self.account_manager.get_all():
            try:
                account.protocol('contacts')
            except NotImplementedError:
                # Not all protocols are expected to implement this.
                pass
            else:
                log.debug('{}: Fetched contacts.'.format(account.id))

    def _on_connection_online(self):
        if self._timer_id is None:
            self._timer_id = GLib.timeout_add_seconds(
                self._interval, self.Refresh)

    def _on_connection_offline(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    @property
    def online(self):
        return self._timer_id is not None

    def _increment_unread_count(self, model, itr):
        self._unread_count += 1
        self.menu_manager.update_unread_count(self._unread_count)

    @dbus.service.method(DBUS_INTERFACE)
    def Refresh(self):
        self._unread_count = 0

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

    @dbus.service.method(DBUS_INTERFACE)
    def ClearIndicators(self):
        """Indicate that messages have been read.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/Friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.ClearIndicators()
        """
        self.menu_manager.update_unread_count(0)

    @dbus.service.method(DBUS_INTERFACE, in_signature='sss')
    def Do(self, action, account_id='', arg=''):
        """Performs an arbitrary operation with an optional argument.

        This is how the client initiates retweeting, liking, searching, etc.
        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/Friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.Do('like', '3/facebook', 'post_id') # Likes that FB post.
            service.Do('search', '', 'search terms') # Searches all accounts.
            service.Do('list', '6/twitter', 'list_id') # Fetch a single list.
        """
        if not self.online:
            return
        if account_id:
            accounts = [self.account_manager.get(account_id)]
            if accounts == [None]:
                log.error('Could not find account: {}'.format(account_id))
                return
        else:
            accounts = list(self.account_manager.get_all())

        for account in accounts:
            log.debug('{}: {} {}'.format(account.id, action, arg))
            args = (action, arg) if arg else (action)
            try:
                account.protocol(*args)
            except NotImplementedError:
                # Not all accounts are expected to implement every action.
                pass

    @dbus.service.method(DBUS_INTERFACE, in_signature='s')
    def SendMessage(self, message):
        """Posts a message/status update to all send_enabled accounts.

        It takes one argument, which is a message formated as a string.
        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/Friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.SendMessage('Your message')
        """
        if not self.online:
            return
        for account in self.account_manager.get_all():
            if account.send_enabled:
                log.debug(
                    'Sending message to {}'.format(
                        account.protocol.__class__.__name__))
                account.protocol('send', message)

    @dbus.service.method(DBUS_INTERFACE, in_signature='sss')
    def SendReply(self, account_id, message_id, message):
        """Posts a reply to the indicate message_id on account_id.

        It takes three arguments, all strings.
        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.SendReply('6/twitter', '34245645347345626', 'Your reply')
        """
        if not self.online:
            return
        log.debug('Replying to {}, {}'.format(account_id, message_id))
        account = self.account_manager.get(account_id)
        if account is not None:
            account.protocol('send_thread', message_id, message)
        else:
            log.error('Could not find account: {}'.format(account_id))

    @dbus.service.method(DBUS_INTERFACE, out_signature='s')
    def GetFeatures(self, protocol_name):
        """Returns a list of features supported by service as json string.

        example:
            import dbus, json
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/Friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            features = json.loads(service.GetFeatures('facebook'))
        """
        protocol = protocol_manager.protocols.get(protocol_name)
        return json.dumps(protocol.get_features())

    @dbus.service.method(DBUS_INTERFACE)
    def Quit(self):
        """Shutdown the service.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/Friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.Quit()
        """
        log.info('Friends Service is being shutdown')
        logging.shutdown()
        self.mainloop.quit()
