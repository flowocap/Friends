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

"""Test the dispatcher directly, without dbus."""

__all__ = [
    'TestDispatcher',
    ]


import dbus.service
import unittest
import json

from dbus.mainloop.glib import DBusGMainLoop

from friends.service.dispatcher import Dispatcher, STUB
from friends.tests.mocks import LogMock, mock


# Set up the DBus main loop.
DBusGMainLoop(set_as_default=True)


class TestDispatcher(unittest.TestCase):
    """Test the dispatcher's ability to dispatch."""

    @mock.patch('dbus.service.BusName')
    @mock.patch('friends.service.dispatcher.AccountManager')
    @mock.patch('friends.service.dispatcher.Dispatcher.Refresh')
    @mock.patch('dbus.service.Object.__init__')
    def setUp(self, *mocks):
        self.log_mock = LogMock('friends.service.dispatcher',
                                'friends.utils.account')
        self.dispatcher = Dispatcher(mock.Mock(), mock.Mock())

    def tearDown(self):
        self.log_mock.stop()

    @mock.patch('friends.service.dispatcher.threading')
    def test_refresh(self, threading_mock):
        account = mock.Mock()
        threading_mock.activeCount.return_value = 1
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get_all.return_value = [account]

        self.assertIsNone(self.dispatcher.Refresh())

        self.dispatcher.account_manager.get_all.assert_called_once_with()
        account.protocol.assert_called_once_with('receive')

        self.assertEqual(self.log_mock.empty(), 'Refresh requested\n')

    def test_clear_indicators(self):
        self.dispatcher.menu_manager = mock.Mock()
        self.dispatcher.ClearIndicators()
        self.dispatcher.menu_manager.update_unread_count.assert_called_once_with(0)

    def test_do(self):
        account = mock.Mock()
        account.id = '345'
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = account

        self.dispatcher.Do('like', '345', '23346356767354626')
        self.dispatcher.account_manager.get.assert_called_once_with(
            '345')
        account.protocol.assert_called_once_with(
            'like', '23346356767354626', success=STUB, failure=STUB)

        self.assertEqual(self.log_mock.empty(),
                         '345: like 23346356767354626\n')

    def test_failing_do(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = None

        self.dispatcher.Do('unlike', '6', '23346356767354626')
        self.dispatcher.account_manager.get.assert_called_once_with('6')
        self.assertEqual(account.protocol.call_count, 0)

        self.assertEqual(self.log_mock.empty(),
                         'Could not find account: 6\n')

    def test_send_message(self):
        account1 = mock.Mock()
        account2 = mock.Mock()
        account3 = mock.Mock()
        account2.send_enabled = False

        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get_all.return_value = [
            account1,
            account2,
            account3,
            ]

        self.dispatcher.SendMessage('Howdy friends!')
        self.dispatcher.account_manager.get_all.assert_called_once_with()
        account1.protocol.assert_called_once_with(
            'send', 'Howdy friends!', success=STUB, failure=STUB)
        account3.protocol.assert_called_once_with(
            'send', 'Howdy friends!', success=STUB, failure=STUB)
        self.assertEqual(account2.protocol.call_count, 0)

    def test_send_reply(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = account

        self.dispatcher.SendReply('2', 'objid', '[Hilarious Response]')
        self.dispatcher.account_manager.get.assert_called_once_with('2')
        account.protocol.assert_called_once_with(
            'send_thread', 'objid', '[Hilarious Response]',
            success=STUB, failure=STUB)

        self.assertEqual(self.log_mock.empty(),
                         'Replying to 2, objid\n')

    def test_send_reply_failed(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = None

        self.dispatcher.SendReply('2', 'objid', '[Hilarious Response]')
        self.dispatcher.account_manager.get.assert_called_once_with('2')
        self.assertEqual(account.protocol.call_count, 0)

        self.assertEqual(self.log_mock.empty(),
                         'Replying to 2, objid\n' +
                         'Could not find account: 2\n')

    def test_upload_async(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = account

        success = mock.Mock()
        failure = mock.Mock()

        self.dispatcher.Upload('2',
                               'file://path/to/image.png',
                               'A thousand words',
                               success=success,
                               failure=failure)
        self.dispatcher.account_manager.get.assert_called_once_with('2')
        account.protocol.assert_called_once_with(
            'upload',
            'file://path/to/image.png',
            'A thousand words',
            success=success,
            failure=failure,
            )

        self.assertEqual(self.log_mock.empty(),
                         'Uploading file://path/to/image.png to 2\n')

    def test_get_features(self):
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('facebook')),
                         ['contacts', 'delete', 'home', 'like', 'receive',
                          'search', 'send', 'send_thread', 'unlike', 'upload',
                          'wall'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('twitter')),
                         ['contacts', 'delete', 'follow', 'home', 'like',
                          'list', 'lists', 'mentions', 'private', 'receive',
                          'retweet', 'search', 'send', 'send_private',
                          'send_thread', 'tag', 'unfollow', 'unlike', 'user'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('identica')),
                         ['contacts', 'delete', 'follow', 'home', 'mentions',
                          'private', 'receive', 'retweet', 'search', 'send',
                          'send_private', 'send_thread', 'unfollow', 'user'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('flickr')),
                         ['receive'])
        self.assertEqual(json.loads(self.dispatcher.GetFeatures('foursquare')),
                         ['receive'])

    @mock.patch('friends.service.dispatcher.logging')
    def test_urlshorten_already_shortened(self, logging_mock):
        self.assertEqual(
            'http://tinyurl.com/foo',
            self.dispatcher.URLShorten('http://tinyurl.com/foo'))

    @mock.patch('friends.service.dispatcher.logging')
    @mock.patch('friends.service.dispatcher.lookup')
    def test_urlshorten(self, lookup_mock, logging_mock):
        lookup_mock.is_shortened.return_value = False
        lookup_mock.lookup.return_value = mock.Mock()
        lookup_mock.lookup.return_value.shorten.return_value = 'short url'
        self.dispatcher.settings.get_string.return_value = 'is.gd'
        long_url = 'http://example.com/really/really/long'
        self.assertEqual(
            self.dispatcher.URLShorten(long_url),
            'short url')
        lookup_mock.is_shortened.assert_called_once_with(long_url)
        self.dispatcher.settings.get_boolean.assert_called_once_with('shorten-urls')
        lookup_mock.lookup.assert_called_once_with('is.gd')
        lookup_mock.lookup.return_value.shorten.assert_called_once_with(long_url)
