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
    'TestDispatcher',
    ]


import dbus.service
import unittest
import json

from dbus.mainloop.glib import DBusGMainLoop

from friends.service.dispatcher import Dispatcher, ManageTimers, STUB
from friends.tests.mocks import LogMock, mock


# Set up the DBus main loop.
DBusGMainLoop(set_as_default=True)


@mock.patch('friends.service.dispatcher.GLib.timeout_add_seconds',
            mock.Mock(return_value=42))
@mock.patch('friends.service.dispatcher.GLib.source_remove',
            mock.Mock(return_value=True))
class TestDispatcher(unittest.TestCase):
    """Test the dispatcher's ability to dispatch."""

    @mock.patch('dbus.service.BusName')
    @mock.patch('friends.service.dispatcher.find_accounts')
    @mock.patch('dbus.service.Object.__init__')
    def setUp(self, *mocks):
        self.log_mock = LogMock('friends.service.dispatcher',
                                'friends.utils.account')
        self.dispatcher = Dispatcher(mock.Mock(), mock.Mock())
        self.dispatcher.accounts = {}

    def tearDown(self):
        self.log_mock.stop()

    @mock.patch('friends.service.dispatcher.threading')
    def test_refresh(self, threading_mock):
        account = mock.Mock()
        threading_mock.activeCount.return_value = 1
        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.values.return_value = [account]

        self.assertIsNone(self.dispatcher.Refresh())

        self.dispatcher.accounts.values.assert_called_once_with()
        account.protocol.assert_called_once_with('receive')

        self.assertEqual(self.log_mock.empty(),
                         'Clearing timer id: 42\n'
                         'Refresh requested\n'
                         'Starting new shutdown timer...\n')

    def test_clear_indicators(self):
        self.dispatcher.menu_manager = mock.Mock()
        self.dispatcher.ClearIndicators()
        self.dispatcher.menu_manager.update_unread_count.assert_called_once_with(0)

    def test_do(self):
        account = mock.Mock()
        account.id = '345'
        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.get.return_value = account

        self.dispatcher.Do('like', '345', '23346356767354626')
        self.dispatcher.accounts.get.assert_called_once_with(345)
        account.protocol.assert_called_once_with(
            'like', '23346356767354626', success=STUB, failure=STUB)

        self.assertEqual(self.log_mock.empty(),
                         'Clearing timer id: 42\n'
                         '345: like 23346356767354626\n'
                         'Starting new shutdown timer...\n')

    def test_failing_do(self):
        account = mock.Mock()
        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.get.return_value = None

        self.dispatcher.Do('unlike', '6', '23346356767354626')
        self.dispatcher.accounts.get.assert_called_once_with(6)
        self.assertEqual(account.protocol.call_count, 0)

        self.assertEqual(self.log_mock.empty(),
                         'Clearing timer id: 42\n'
                         'Could not find account: 6\n'
                         'Starting new shutdown timer...\n')

    def test_send_message(self):
        account1 = mock.Mock()
        account2 = mock.Mock()
        account3 = mock.Mock()
        account2.send_enabled = False

        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.values.return_value = [
            account1,
            account2,
            account3,
            ]

        self.dispatcher.SendMessage('Howdy friends!')
        self.dispatcher.accounts.values.assert_called_once_with()
        account1.protocol.assert_called_once_with(
            'send', 'Howdy friends!', success=STUB, failure=STUB)
        account3.protocol.assert_called_once_with(
            'send', 'Howdy friends!', success=STUB, failure=STUB)
        self.assertEqual(account2.protocol.call_count, 0)

    def test_send_reply(self):
        account = mock.Mock()
        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.get.return_value = account

        self.dispatcher.SendReply('2', 'objid', '[Hilarious Response]')
        self.dispatcher.accounts.get.assert_called_once_with(2)
        account.protocol.assert_called_once_with(
            'send_thread', 'objid', '[Hilarious Response]',
            success=STUB, failure=STUB)

        self.assertEqual(self.log_mock.empty(),
                         'Clearing timer id: 42\n'
                         'Replying to 2, objid\n'
                         'Starting new shutdown timer...\n')

    def test_send_reply_failed(self):
        account = mock.Mock()
        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.get.return_value = None

        self.dispatcher.SendReply('2', 'objid', '[Hilarious Response]')
        self.dispatcher.accounts.get.assert_called_once_with(2)
        self.assertEqual(account.protocol.call_count, 0)

        self.assertEqual(self.log_mock.empty(),
                         'Clearing timer id: 42\n'
                         'Replying to 2, objid\n'
                         'Could not find account: 2\n'
                         'Starting new shutdown timer...\n')

    def test_upload_async(self):
        account = mock.Mock()
        self.dispatcher.accounts = mock.Mock()
        self.dispatcher.accounts.get.return_value = account

        success = mock.Mock()
        failure = mock.Mock()

        self.dispatcher.Upload('2',
                               'file://path/to/image.png',
                               'A thousand words',
                               success=success,
                               failure=failure)
        self.dispatcher.accounts.get.assert_called_once_with(2)
        account.protocol.assert_called_once_with(
            'upload',
            'file://path/to/image.png',
            'A thousand words',
            success=success,
            failure=failure,
            )

        self.assertEqual(self.log_mock.empty(),
                         'Clearing timer id: 42\n'
                         'Uploading file://path/to/image.png to 2\n'
                         'Starting new shutdown timer...\n')

    def test_get_features(self):
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('facebook')),
                         ['contacts', 'delete', 'delete_contacts',
                          'home', 'like', 'receive', 'search', 'send',
                          'send_thread', 'unlike', 'upload', 'wall'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('twitter')),
                         ['contacts', 'delete', 'delete_contacts',
                          'follow', 'home', 'like', 'list', 'lists',
                          'mentions', 'private', 'receive', 'retweet',
                          'search', 'send', 'send_private',
                          'send_thread', 'tag', 'unfollow', 'unlike',
                          'user'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('identica')),
                         ['contacts', 'delete', 'delete_contacts',
                          'follow', 'home', 'like', 'mentions',
                          'private', 'receive', 'retweet', 'search',
                          'send', 'send_private', 'send_thread',
                          'unfollow', 'unlike', 'user'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('flickr')),
                         ['delete_contacts', 'receive', 'upload'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('foursquare')),
                         ['delete_contacts', 'receive'])

    @mock.patch('friends.service.dispatcher.logging')
    def test_urlshorten_already_shortened(self, logging_mock):
        self.assertEqual(
            'http://tinyurl.com/foo',
            self.dispatcher.URLShorten('http://tinyurl.com/foo'))

    @mock.patch('friends.service.dispatcher.logging')
    @mock.patch('friends.service.dispatcher.Short')
    def test_urlshorten(self, short_mock, logging_mock):
        short_mock().sub.return_value = 'short url'
        short_mock.reset_mock()
        self.dispatcher.settings.get_string.return_value = 'is.gd'
        long_url = 'http://example.com/really/really/long'
        self.assertEqual(
            self.dispatcher.URLShorten(long_url),
            'short url')
        self.dispatcher.settings.get_boolean.assert_called_once_with(
            'shorten-urls')
        short_mock.assert_called_once_with('is.gd')
        short_mock.return_value.sub.assert_called_once_with(
            long_url)

    @mock.patch('friends.service.dispatcher.GLib')
    def test_manage_timers_clear(self, glib):
        glib.source_remove.reset_mock()
        manager = ManageTimers()
        manager.timers = {1}
        manager.__enter__()
        glib.source_remove.assert_called_once_with(1)
        manager.timers = {1, 2, 3}
        manager.clear_all_timers()
        self.assertEqual(glib.source_remove.call_count, 4)

    @mock.patch('friends.service.dispatcher.GLib')
    def test_manage_timers_set(self, glib):
        glib.timeout_add_seconds.reset_mock()
        manager = ManageTimers()
        manager.timers = set()
        manager.clear_all_timers = mock.Mock()
        manager.__exit__()
        glib.timeout_add_seconds.assert_called_once_with(30, manager.terminate)
        manager.clear_all_timers.assert_called_once_with()
        self.assertEqual(len(manager.timers), 1)

    @mock.patch('friends.service.dispatcher.persist_model')
    @mock.patch('friends.service.dispatcher.threading')
    @mock.patch('friends.service.dispatcher.GLib')
    def test_manage_timers_terminate(self, glib, thread, persist):
        manager = ManageTimers()
        manager.timers = set()
        thread.activeCount.return_value = 1
        manager.terminate()
        thread.activeCount.assert_called_once_with()
        persist.assert_called_once_with()
        glib.idle_add.assert_called_once_with(manager.callback)

    @mock.patch('friends.service.dispatcher.persist_model')
    @mock.patch('friends.service.dispatcher.threading')
    @mock.patch('friends.service.dispatcher.GLib')
    def test_manage_timers_dont_kill_threads(self, glib, thread, persist):
        manager = ManageTimers()
        manager.timers = set()
        manager.set_new_timer = mock.Mock()
        thread.activeCount.return_value = 10
        manager.terminate()
        thread.activeCount.assert_called_once_with()
        manager.set_new_timer.assert_called_once_with()
