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

"""Test our libnotify support."""

__all__ = [
    'TestNotifications',
    ]


import unittest

from gi.repository import Dee

from friends.testing.helpers import FakeAccount
from friends.testing.mocks import mock
from friends.utils.base import Base
from friends.utils.model import COLUMN_TYPES
from friends.utils.notify import notify


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


class TestNotifications(unittest.TestCase):
    """Test notification details."""

    def setUp(self):
        TestModel.clear()

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    @mock.patch('friends.utils.base.notify')
    def test_publish_all(self, notify):
        Base._do_notify = lambda protocol, stream: True
        base = Base(FakeAccount())
        base._publish(
            message='notify!',
            message_id='1234',
            sender='Benjamin',
            )
        notify.assert_called_once_with('Benjamin', 'notify!', '')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    @mock.patch('friends.utils.base.notify')
    def test_publish_mentions_private(self, notify):
        Base._do_notify = lambda protocol, stream: stream in (
            'mentions', 'private')
        base = Base(FakeAccount())
        base._publish(
            message='This message is private!',
            message_id='1234',
            sender='Benjamin',
            stream='private',
            )
        notify.assert_called_once_with('Benjamin', 'This message is private!', '')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    @mock.patch('friends.utils.base.notify')
    def test_publish_mention_fail(self, notify):
        Base._do_notify = lambda protocol, stream: stream in (
            'mentions', 'private')
        base = Base(FakeAccount())
        base._publish(
            message='notify!',
            message_id='1234',
            sender='Benjamin',
            stream='messages',
            )
        self.assertEqual(notify.call_count, 0)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    @mock.patch('friends.utils.base.notify')
    def test_publish_mention_none(self, notify):
        Base._do_notify = lambda protocol, stream: False
        base = Base(FakeAccount())
        base._publish(
            message='Ignore me!',
            message_id='1234',
            sender='Benjamin',
            stream='messages',
            )
        self.assertEqual(notify.call_count, 0)

    @mock.patch('friends.utils.notify.Notify')
    def test_dont_notify(self, Notify):
        notify('', '')
        notify('Bob Loblaw', '')
        notify('', 'hello, friend!')
        self.assertEqual(Notify.Notification.new.call_count, 0)

    @mock.patch('friends.utils.notify.Notify')
    def test_notify(self, Notify):
        notify('Bob Loblaw', 'hello, friend!', pixbuf='hi!')
        Notify.Notification.new.assert_called_once_with(
            'Bob Loblaw', 'hello, friend!', 'friends')
        notification = Notify.Notification.new()
        notification.set_icon_from_pixbuf.assert_called_once_with('hi!')
        notification.show.assert_called_once_with()
