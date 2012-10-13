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

"""Test the authentication service.

We do a lot of mocking so that we don't have to talk to the actual backend
authentication service.
"""

__all__ = [
    'TestAuthentication',
    ]


import unittest

from friends.testing.helpers import FakeAccount
from friends.utils.authentication import Authentication


try:
    # Python 3.3
    from unittest import mock
except ImportError:
    import mock


class FakeSignon:
    class AuthSession:
        @classmethod
        def new(cls, id, method):
            return cls()

        def process(self, parameters, mechanism, callback, ignore):
            # Pass in fake data.  The callback expects a session, reply,
            # error, and user_data arguments.  We'll use the parameters
            # argument as a way to specify whether an error occurred during
            # authentication or not.  Beautiful cruft.
            callback(None, 'auth reply', parameters, None)


class Logger:
    def __init__(self):
        self.debug_messages = []
        self.error_messages = []

    def debug(self, message, *args):
        self.debug_messages.append(message.format(*args))

    def error(self, message, *args):
        self.error_messages.append(message.format(*args))


class TestAuthentication(unittest.TestCase):
    """Test authentication."""

    def setUp(self):
        self.account = FakeAccount()
        self.account.auth.id = 'my id'
        self.account.auth.method = 'some method'
        self.account.auth.parameters = 'change me'
        self.account.auth.mechanism = ['whatever']
        self.logger = Logger()

    @mock.patch('friends.utils.authentication.Signon', FakeSignon)
    def test_successful_login(self):
        # Prevent an error in the callback.
        self.account.auth.parameters = False
        authenticator = Authentication(self.account, self.logger)
        reply = authenticator.login()
        self.assertEqual(reply, 'auth reply')
        self.assertEqual(self.logger.debug_messages,
                         ['Login completed'])
        self.assertEqual(self.logger.error_messages, [])

    @mock.patch('friends.utils.authentication.Signon', FakeSignon)
    def test_failed_login(self):
        # Trigger an error in the callback.
        class Error:
            message = 'who are you?'
        self.account.auth.parameters = Error
        authenticator = Authentication(self.account, self.logger)
        reply = authenticator.login()
        self.assertIsNone(reply)
        self.assertEqual(self.logger.debug_messages, ['Login completed'])
        self.assertEqual(self.logger.error_messages,
                         ['Got authentication error: who are you?'])
