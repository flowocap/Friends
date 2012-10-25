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


import json
import dbus
import dbus.service
import unittest

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GObject

from friends.service.dispatcher import Dispatcher
from friends.testing.mocks import LogMock


try:
    # Python 3.3
    from unittest import mock
except ImportError:
    import mock


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
        self.dispatcher = Dispatcher(mock.Mock(), 300)
        self.dispatcher.Refresh.assert_called_once_with()

    def tearDown(self):
        self.log_mock.stop()

    @mock.patch('friends.service.dispatcher.GLib')
    def test_connection_online_offline(self, glib_mock):
        self.assertIsNotNone(self.dispatcher._timer_id)
        self.assertTrue(self.dispatcher.online)

        timer_id = self.dispatcher._timer_id
        self.dispatcher._on_connection_offline()
        self.assertIsNone(self.dispatcher._timer_id)
        self.assertFalse(self.dispatcher.online)
        glib_mock.source_remove.assert_called_once_with(timer_id)

        self.dispatcher._on_connection_online()
        self.assertIsNotNone(self.dispatcher._timer_id)
        self.assertTrue(self.dispatcher.online)
        glib_mock.timeout_add_seconds.assert_called_once_with(
            300, self.dispatcher.Refresh)

    @mock.patch('friends.service.dispatcher.threading')
    def test_refresh(self, threading_mock):
        account = mock.Mock()
        thread = mock.Mock()
        threading_mock.enumerate.return_value = [thread]
        threading_mock.current_thread.return_value = 'MainThread'
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get_all.return_value = [account]

        self.assertTrue(self.dispatcher.Refresh())
        threading_mock.current_thread.assert_called_once_with()
        threading_mock.enumerate.assert_called_once_with()
        thread.join.assert_called_once_with()

        self.dispatcher.account_manager.get_all.assert_called_once_with()
        account.protocol.assert_called_once_with('receive')

        self.assertEqual(self.log_mock.empty(), 'Refresh requested\n')

    def test_update_indicators(self):
        # TODO
        self.assertIsNone(self.dispatcher.UpdateIndicators('stream'))

    def test_do(self):
        account = mock.Mock()
        account.id = '345/friendface'
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = account

        self.dispatcher.Do('like', '345/friendface', '23346356767354626')
        self.dispatcher.account_manager.get.assert_called_once_with(
            '345/friendface')
        account.protocol.assert_called_once_with(
            'like', '23346356767354626')

        self.assertEqual(self.log_mock.empty(),
                         '345/friendface: like 23346356767354626\n')

    def test_failing_do(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = None

        self.dispatcher.Do('unlike', '6/twitter', '23346356767354626')
        self.dispatcher.account_manager.get.assert_called_once_with('6/twitter')
        self.assertEqual(account.protocol.call_count, 0)

        self.assertEqual(self.log_mock.empty(),
                         'Could not find account: 6/twitter\n')

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
        account1.protocol.assert_called_once_with('send', 'Howdy friends!')
        account3.protocol.assert_called_once_with('send', 'Howdy friends!')
        self.assertEqual(account2.protocol.call_count, 0)

    def test_send_reply(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = account

        self.dispatcher.SendReply('2/facebook', 'objid', '[Hilarious Response]')
        self.dispatcher.account_manager.get.assert_called_once_with('2/facebook')
        account.protocol.assert_called_once_with(
            'send_thread', 'objid', '[Hilarious Response]')

        self.assertEqual(self.log_mock.empty(),
                         'Replying to 2/facebook, objid\n')

    def test_send_reply_failed(self):
        account = mock.Mock()
        self.dispatcher.account_manager = mock.Mock()
        self.dispatcher.account_manager.get.return_value = None

        self.dispatcher.SendReply('2/facebook', 'objid', '[Hilarious Response]')
        self.dispatcher.account_manager.get.assert_called_once_with('2/facebook')
        self.assertEqual(account.protocol.call_count, 0)

        self.assertEqual(self.log_mock.empty(),
                         'Replying to 2/facebook, objid\n' +
                         'Could not find account: 2/facebook\n')

    def test_get_features(self):
        """See test_dbus.py for a thorough test of Dispatcher.GetFeatures."""
        pass

    @mock.patch('friends.service.dispatcher.Avatar')
    def test_get_avatar_path(self, avatar):
        url = 'http://example.com/profile_photo.jpg'
        self.dispatcher.GetAvatarPath(url)
        avatar.get_image.assert_called_once_with(url)
        self.assertEqual(avatar.get_path.call_count, 0)

    @mock.patch('friends.service.dispatcher.Avatar')
    def test_get_avatar_path_offline(self, avatar):
        url = 'http://example.com/profile_photo.jpg'
        self.dispatcher._timer_id = None
        self.dispatcher.GetAvatarPath(url)
        avatar.get_path.assert_called_once_with(url)
        self.assertEqual(avatar.get_image.call_count, 0)

    @mock.patch('friends.service.dispatcher.logging')
    def test_quit(self, logging_mock):
        self.dispatcher.Quit()
        self.dispatcher.mainloop.quit.assert_called_once_with()
        logging_mock.shutdown.assert_called_once_with()

        self.assertEqual(self.log_mock.empty(),
                         'Friends Service is being shutdown\n')
