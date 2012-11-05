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

"""Test the FourSquare plugin."""

__all__ = [
    'TestFourSquare',
    ]


import unittest

from gi.repository import Dee

from friends.protocols.foursquare import FourSquare
from friends.testing.helpers import FakeAccount
from friends.testing.mocks import FakeSoupMessage, LogMock, mock
from friends.utils.base import Base
from friends.utils.model import COLUMN_TYPES


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


@mock.patch('friends.utils.download._soup', mock.Mock())
class TestFourSquare(unittest.TestCase):
    """Test the FourSquare API."""

    def setUp(self):
        self.account = FakeAccount()
        self.protocol = FourSquare(self.account)
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.foursquare')

    def tearDown(self):
        # Ensure that any log entries we haven't tested just get consumed so
        # as to isolate out test logger from other tests.
        self.log_mock.stop()
        # Reset the database.
        TestModel.clear()

    def test_features(self):
        # The set of public features.
        self.assertEqual(FourSquare.get_features(), ['receive'])

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=None)
    @mock.patch('friends.utils.download.get_json',
                return_value=None)
    def test_unsuccessful_authentication(self, *mocks):
        self.assertFalse(self.protocol._login())
        self.assertIsNone(self.account.user_name)
        self.assertIsNone(self.account.user_id)

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='tokeny goodness'))
    @mock.patch('friends.protocols.foursquare.get_json',
                return_value=dict(
                    response=dict(
                        user=dict(firstName='Bob',
                                  lastName='Loblaw',
                                  id='1234567'))))
    def test_successful_authentication(self, *mocks):
        self.assertTrue(self.protocol._login())
        self.assertEqual(self.account.user_name, 'Bob Loblaw')
        self.assertEqual(self.account.user_id, '1234567')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'foursquare-full.dat'))
    @mock.patch('friends.protocols.foursquare.FourSquare._login',
                return_value=True)
    @mock.patch('friends.protocols.foursquare.Avatar.get_image',
                return_value='~/.cache/friends/avatar/hash')
    def test_receive(self, *mocks):
        self.account.access_token = 'tokeny goodness'
        self.assertEqual(0, TestModel.get_n_rows())
        self.protocol.receive()
        self.assertEqual(1, TestModel.get_n_rows())
        expected = [
            [['foursquare', 'faker/than fake', '50574c9ce4b0a9a6e84433a0']],
            'messages', 'Jimbob Smith', '', '', True, '2012-09-17T19:15:24Z',
            "Working on friends's foursquare plugin.", '',
            '~/.cache/friends/avatar/hash',
            'https://api.foursquare.com/v2/checkins/50574c9ce4b0a9a6e84433a0' +
            '?oauth_token=tokeny goodness&v=20121104', '', '', '', '', 0.0,
            False, '', '', '', '', '', '', '', '', '', '', '', '', '', '',
            '', '', '', '', '', '',
            ]
        for got, want in zip(TestModel.get_row(0), expected):
            self.assertEqual(got, want)
