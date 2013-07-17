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

"""Test the LinkedIn plugin."""


__all__ = [
    'TestLinkedIn',
    ]


import unittest

from friends.protocols.linkedin import LinkedIn
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock
from friends.tests.mocks import TestModel, mock
from friends.errors import AuthorizationError


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
class TestLinkedIn(unittest.TestCase):
    """Test the LinkedIn API."""

    def setUp(self):
        TestModel.clear()
        self.account = FakeAccount()
        self.protocol = LinkedIn(self.account)
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.linkedin')

    def tearDown(self):
        # Ensure that any log entries we haven't tested just get consumed so
        # as to isolate out test logger from other tests.
        self.log_mock.stop()

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    @mock.patch('friends.protocols.linkedin.Downloader.get_json',
                return_value=None)
    def test_unsuccessful_authentication(self, dload, login, *mocks):
        self.assertRaises(AuthorizationError, self.protocol._login)
        self.assertIsNone(self.account.user_name)
        self.assertIsNone(self.account.user_id)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch('friends.utils.authentication.Authentication.__init__',
                return_value=None)
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='some clever fake data'))
    @mock.patch('friends.protocols.linkedin.Downloader.get_json',
                return_value=dict(id='blerch', firstName='Bob', lastName='Loblaw'))
    def test_successful_authentication(self, *mocks):
        self.assertTrue(self.protocol._login())
        self.assertEqual(self.account.user_name, 'Bob Loblaw')
        self.assertEqual(self.account.user_id, 'blerch')
        self.assertEqual(self.account.access_token, 'some clever fake data')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'linkedin_receive.json'))
    @mock.patch('friends.protocols.linkedin.LinkedIn._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_home(self, *mocks):
        self.account.access_token = 'access'
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertEqual(self.protocol.home(), 1)
        self.assertEqual(1, TestModel.get_n_rows())
        self.maxDiff = None

        self.assertEqual(
            list(TestModel.get_row(0)),
            ['linkedin', 88, 'UNIU-73705-576270369559388-SHARE', 'messages',
             'Hobson L', 'ma0LLid', '', False, '2013-07-16T00:47:06Z',
             'I\'m looking forward to the Udacity Global meetup event here in '
             'Portland: <a href="http://lnkd.in/dh5MQz">http://lnkd.in/dh5MQz'
             '</a>\nGreat way to support the next big thing in c…',
             'http://m.c.lnkd.licdn.com/mpr/mprx/0_mVxsC0BnN52aqc24yWvoyA5haqc2Z'
             'wLCgzLv0EiBGp7n2jTwX-ls_dzgkSVIZu0',
             'https://www.linkedin.com/profile/view?id=7375&authType=name'
             '&authToken=-LNy&trk=api*a26127*s26893*',
             1, False, '', '', '', '', '', '', '', 0.0, 0.0])
