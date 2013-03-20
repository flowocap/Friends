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
import threading

import dbus
import dbus.service

from gi.repository import GLib
from contextlib import ContextDecorator

from friends.utils.avatar import Avatar
from friends.utils.account import find_accounts
from friends.utils.manager import protocol_manager
from friends.utils.menus import MenuManager
from friends.utils.model import Model, persist_model
from friends.shorteners import lookup


log = logging.getLogger(__name__)

DBUS_INTERFACE = 'com.canonical.Friends.Dispatcher'
STUB = lambda *ignore, **kwignore: None


# Avoid race condition during shut-down
_exit_lock = threading.Lock()


class ManageTimers(ContextDecorator):
    """Exit the dispatcher 30s after the most recent method call returns."""
    timers = set()
    callback = STUB

    def __enter__(self):
        self.clear_all_timers()

    def __exit__(self, *ignore):
        self.set_new_timer()

    def clear_all_timers(self):
        log.debug('Clearing {} shutdown timer(s)...'.format(len(self.timers)))
        while self.timers:
            GLib.source_remove(self.timers.pop())

    def set_new_timer(self):
        # Concurrency will cause two methods to exit near each other,
        # causing two timers to be set, so we have to clear them again.
        self.clear_all_timers()
        log.debug('Starting new shutdown timer...')
        self.timers.add(GLib.timeout_add_seconds(30, self.terminate))

    def terminate(self, *ignore):
        """Exit the dispatcher, but only if there are no active subthreads."""
        with _exit_lock:
            if threading.activeCount() < 2:
                log.debug('No threads found, shutting down.')
                persist_model()
                self.timers.add(GLib.idle_add(self.callback))
            else:
                log.debug('Delaying shutdown because active threads found.')
                self.set_new_timer()


exit_after_idle = ManageTimers()


class Dispatcher(dbus.service.Object):
    """This is the primary handler of dbus method calls."""
    __dbus_object_path__ = '/com/canonical/friends/Dispatcher'

    def __init__(self, settings, mainloop):
        self.settings = settings
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(DBUS_INTERFACE, bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)
        self.mainloop = mainloop

        self.accounts = find_accounts()

        self._unread_count = 0
        self.menu_manager = MenuManager(self.Refresh, self.mainloop.quit)
        Model.connect('row-added', self._increment_unread_count)

        ManageTimers.callback = mainloop.quit

    def _increment_unread_count(self, model, itr):
        self._unread_count += 1
        self.menu_manager.update_unread_count(self._unread_count)

    @exit_after_idle
    @dbus.service.method(DBUS_INTERFACE)
    def Refresh(self):
        """Download new messages from each connected protocol."""
        self._unread_count = 0

        log.debug('Refresh requested')

        # account.protocol() starts a new thread and then returns
        # immediately, so there is no delay or blocking during the
        # execution of this method.
        for account in self.accounts.values():
            try:
                account.protocol('receive')
            except NotImplementedError:
                # If a protocol doesn't support receive then ignore it.
                pass

    @exit_after_idle
    @dbus.service.method(DBUS_INTERFACE)
    def ClearIndicators(self):
        """Indicate that messages have been read.

        example:
            import dbus
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/Dispatcher')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.ClearIndicators()
        """
        self.menu_manager.update_unread_count(0)

    @exit_after_idle
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
                '/com/canonical/friends/Dispatcher')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.Do('like', '3', 'post_id') # Likes that FB post.
            service.Do('search', '', 'search terms') # Searches all accounts.
            service.Do('list', '6', 'list_id') # Fetch a single list.
        """
        if account_id:
            accounts = [self.accounts.get(int(account_id))]
            if None in accounts:
                message = 'Could not find account: {}'.format(account_id)
                failure(message)
                log.error(message)
                return
        else:
            accounts = list(self.accounts.values())

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

    @exit_after_idle
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
                '/com/canonical/friends/Dispatcher')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.SendMessage('Your message')
        """
        sent = False
        for account in self.accounts.values():
            if account.send_enabled:
                sent = True
                log.debug(
                    'Sending message to {}'.format(
                        account.protocol._Name))
                account.protocol(
                    'send',
                    message,
                    success=success,
                    failure=failure,
                    )
        if not sent:
            failure('No send_enabled accounts found.')

    @exit_after_idle
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
                '/com/canonical/friends/Dispatcher')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            service.SendReply('6', '34245645347345626', 'Your reply')
        """
        log.debug('Replying to {}, {}'.format(account_id, message_id))
        account = self.accounts.get(int(account_id))
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

    @exit_after_idle
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
                '/com/canonical/friends/Dispatcher')
            service = dbus.Interface(obj, DBUS_INTERFACE)

            def success(destination_url):
                print('successfully uploaded to {}.'.format(destination_url))

            def failure(message):
                print('failed to upload: {}'.format(message))

            service.Upload(
                '6',
                'file:///path/to/image.png',
                'A beautiful picture.',
                reply_handler=success,
                error_handler=failure)

            loop.run()

        Note also that the callbacks are actually optional; you are
        free to ignore error conditions at your peril.
        """
        log.debug('Uploading {} to {}'.format(uri, account_id))
        account = self.accounts.get(int(account_id))
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

    @exit_after_idle
    @dbus.service.method(DBUS_INTERFACE, in_signature='s', out_signature='s')
    def GetFeatures(self, protocol_name):
        """Returns a list of features supported by service as json string.

        example:
            import dbus, json
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/Dispatcher')
            service = dbus.Interface(obj, DBUS_INTERFACE)
            features = json.loads(service.GetFeatures('facebook'))
        """
        protocol = protocol_manager.protocols.get(protocol_name)
        return json.dumps(protocol.get_features() if protocol else [])

    @exit_after_idle
    @dbus.service.method(DBUS_INTERFACE, in_signature='s', out_signature='s')
    def URLShorten(self, url):
        """Shorten a URL.

        Takes a url as a string and returns a shortened url as a string.

        example:
            import dbus
            url = 'http://www.example.com/this/is/a/long/url'
            obj = dbus.SessionBus().get_object(DBUS_INTERFACE,
                '/com/canonical/friends/Dispatcher')
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

    @exit_after_idle
    @dbus.service.method(DBUS_INTERFACE)
    def ExpireAvatars(self):
        Avatar.expire_old_avatars()
