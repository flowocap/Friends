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
from friends.utils.model import Model
from friends.shorteners import lookup


log = logging.getLogger(__name__)

DBUS_INTERFACE = 'com.canonical.Friends.Service'
STUB = lambda *ignore, **kwignore: None


class Dispatcher(dbus.service.Object):
    """This is the primary handler of dbus method calls."""
    __dbus_object_path__ = '/com/canonical/friends/Service'

    def __init__(self, settings, mainloop, interval):
        self.settings = settings
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

        if threading.activeCount() > 1:
            log.debug('Aborting refresh because previous refresh incomplete!')
            return True

        if not self.online:
            return

        # account.protocol() starts a new thread and then returns
        # immediately, so there is no delay or blocking during the
        # execution of this method.
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

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='sss',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def Do(self, action, account_id='', arg='',
           success=STUB, failure=STUB):
        """Performs an arbitrary operation with an optional argument.

        This is how the client initiates retweeting, liking,
        searching, etc. See Dispatcher.Upload for an example of how to
        use the callbacks.

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
            failure('No internet connection available.')
            return
        if account_id:
            accounts = [self.account_manager.get(account_id)]
            if accounts == [None]:
                message = 'Could not find account: {}'.format(account_id)
                failure(message)
                log.error(message)
                return
        else:
            accounts = list(self.account_manager.get_all())

        called = False
        for account in accounts:
            log.debug('{}: {} {}'.format(account.id, action, arg))
            args = (action, arg) if arg else (action,)
            try:
                account.protocol(*args, success=success, failure=failure)
                called = True
            except NotImplementedError:
                # Not all accounts are expected to implement every action.
                pass
        if not called:
            failure('No accounts supporting {} found.'.format(action))

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='s',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def SendMessage(self, message, success=STUB, failure=STUB):
        """Posts a message/status update to all send_enabled accounts.

        It takes one argument, which is a message formated as a
        string. See Dispatcher.Upload for an example of how to use the
        callbacks.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/Friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.SendMessage('Your message')
        """
        if not self.online:
            failure('No internet connection available.')
            return
        sent = False
        for account in self.account_manager.get_all():
            if account.send_enabled:
                sent = True
                log.debug(
                    'Sending message to {}'.format(
                        account.protocol.__class__.__name__))
                account.protocol(
                    'send',
                    message,
                    success=success,
                    failure=failure,
                    )
        if not sent:
            failure('No send_enabled accounts found.')

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='sss',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def SendReply(self, account_id, message_id, message,
                  success=STUB, failure=STUB):
        """Posts a reply to the indicate message_id on account_id.

        It takes three arguments, all strings. See Dispatcher.Upload
        for an example of how to use the callbacks.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.SendReply('6/twitter', '34245645347345626', 'Your reply')
        """
        if not self.online:
            failure('No internet connection available.')
            return
        log.debug('Replying to {}, {}'.format(account_id, message_id))
        account = self.account_manager.get(account_id)
        if account is not None:
            account.protocol(
                'send_thread',
                message_id,
                message,
                success=success,
                failure=failure,
                )
        else:
            message = 'Could not find account: {}'.format(account_id)
            failure(message)
            log.error(message)

    @dbus.service.method(DBUS_INTERFACE,
                         in_signature='sss',
                         out_signature='s',
                         async_callbacks=('success','failure'))
    def Upload(self, account_id, uri, description, success=STUB, failure=STUB):
        """Upload an image to the specified account_id, asynchronously.

        It takes five arguments, three strings and two callback
        functions. The URI option is parsed by GFile and thus
        seamlessly supports uploading from http:// URLs as well as
        file:// paths.

        example:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib

            DBusGMainLoop(set_as_default=True)
            loop = GLib.MainLoop()

            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/Service')
            service = dbus.Interface(obj, DBUS_INTERFACE)

            def success(destination_url):
                print('successfully uploaded to {}.'.format(destination_url))

            def failure(message):
                print('failed to upload: {}'.format(message))

            service.Upload(
                '6/twitter',
                'file:///path/to/image.png',
                'A beautiful picture.',
                reply_handler=success,
                error_handler=failure)

            loop.run()

        Note also that the callbacks are actually optional; you are
        free to ignore error conditions at your peril.
        """
        if not self.online:
            failure('No internet connection available.')
            return
        log.debug('Uploading {} to {}'.format(uri, account_id))
        account = self.account_manager.get(account_id)
        if account is not None:
            account.protocol(
                'upload',
                uri,
                description,
                success=success,
                failure=failure,
                )
        else:
            message = 'Could not find account: {}'.format(account_id)
            failure(message)
            log.error(message)

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

    @dbus.service.method(DBUS_INTERFACE, in_signature='s', out_signature='s')
    def URLShorten(self, url):
        """Shorten a URL.

        Takes a url as a string and returns a shortened url as a string.

        example:
            import dbus
            url = 'http://www.example.com/this/is/a/long/url'
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/URLShorten')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            short_url = service.URLShorten(url)
        """
        service_name = self.settings.get_string('urlshorter')
        log.info('Shortening URL {} with {}'.format(url, service_name))
        if (lookup.is_shortened(url) or
            not self.settings.get_boolean('shorten-urls')):
            # It's already shortened, or the preference is not set.
            return url
        service = lookup.lookup(service_name)
        try:
            return service.shorten(url)
        except Exception:
            log.exception('URL shortening class: {}'.format(service))
            return url
