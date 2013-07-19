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

"""Test the FourSquare plugin."""

__all__ = [
    'TestFourSquare',
    ]


import unittest

from friends.protocols.foursquare import FourSquare
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock
from friends.tests.mocks import TestModel, mock
from friends.errors import AuthorizationError


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
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
        self.assertEqual(FourSquare.get_features(),
                         ['delete_contacts', 'receive'])

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    @mock.patch('friends.utils.http.Downloader.get_json',
                return_value=None)
    def test_unsuccessful_authentication(self, *mocks):
        self.assertRaises(AuthorizationError, self.protocol._login)
        self.assertIsNone(self.account.user_name)
        self.assertIsNone(self.account.user_id)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='tokeny goodness'))
    @mock.patch('friends.utils.authentication.Authentication.__init__',
                return_value=None)
    @mock.patch('friends.protocols.foursquare.Downloader.get_json',
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
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'foursquare-full.dat'))
    @mock.patch('friends.protocols.foursquare.FourSquare._login',
                return_value=True)
    def test_receive(self, *mocks):
        self.account.access_token = 'tokeny goodness'
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertEqual(self.protocol.receive(), 1)
        self.assertEqual(1, TestModel.get_n_rows())
        expected = [
            'foursquare', 88, '50574c9ce4b0a9a6e84433a0',
            'messages', 'Jimbob Smith', '', '', True, '2012-09-17T19:15:24Z',
            "Working on friends's foursquare plugin.",
            'https://irs0.4sqi.net/img/user/100x100/5IEW3VIX55BBEXAO.jpg',
            '', 0, False, '', '', '', '', '', '',
            'Pop Soda\'s Coffee House & Gallery',
            49.88873164336725, -97.158043384552,
            ]
        self.assertEqual(list(TestModel.get_row(0)), expected)
