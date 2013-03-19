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

"""Test the authentication service.

We do a lot of mocking so that we don't have to talk to the actual backend
authentication service.
"""

__all__ = [
    'TestAuthentication',
    ]


import unittest

from friends.utils.authentication import Authentication
from friends.tests.mocks import FakeAccount, LogMock, mock
from friends.errors import AuthorizationError


class FakeAuthSession:
    results = None

    @classmethod
    def new(cls, id, method):
        return cls()

    def process(self, parameters, mechanism, callback, ignore):
        # Pass in fake data.  The callback expects a session, reply,
        # error, and user_data arguments.  We'll use the parameters
        # argument as a way to specify whether an error occurred during
        # authentication or not.
        callback(
            None,
            self.results,
            parameters if hasattr(parameters, 'message') else None,
            None)


class FakeSignon:
    class AuthSession(FakeAuthSession):
        results = dict(AccessToken='auth reply')


class FailingSignon:
    class AuthSession(FakeAuthSession):
        results = dict(NoAccessToken='fail')


class TestAuthentication(unittest.TestCase):
    """Test authentication."""

    def setUp(self):
        self.log_mock = LogMock('friends.utils.authentication')
        self.account = FakeAccount()
        self.account.auth.get_credentials_id = lambda *ignore: 'my id'
        self.account.auth.get_method = lambda *ignore: 'some method'
        self.account.auth.get_parameters = lambda *ignore: 'change me'
        self.account.auth.get_mechanism = lambda *ignore: 'whatever'

    def tearDown(self):
        self.log_mock.stop()

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Signon', FakeSignon)
    @mock.patch('friends.utils.authentication.Accounts')
    def test_successful_login(self, accounts, *mocks):
        # Prevent an error in the callback.
        accounts.AccountService.new().get_auth_data(
            ).get_parameters.return_value = False
        authenticator = Authentication(self.account.id)
        reply = authenticator.login()
        self.assertEqual(reply, dict(AccessToken='auth reply'))
        self.assertEqual(self.log_mock.empty(), 'Login completed\n')

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch('friends.utils.authentication.Signon', FailingSignon)
    def test_missing_access_token(self, *mocks):
        # Prevent an error in the callback.
        self.account.auth.get_parameters = lambda *ignore: False
        authenticator = Authentication(self.account.id)
        self.assertRaises(AuthorizationError, authenticator.login)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Signon', FakeSignon)
    @mock.patch('friends.utils.authentication.Accounts')
    def test_failed_login(self, accounts, *mocks):
        # Trigger an error in the callback.
        class Error:
            message = 'who are you?'
        accounts.AccountService.new(
            ).get_auth_data().get_parameters.return_value = Error
        authenticator = Authentication(self.account.id)
        self.assertRaises(AuthorizationError, authenticator.login)
