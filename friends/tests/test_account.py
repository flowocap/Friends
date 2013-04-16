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

"""Test the Account class."""

__all__ = [
    'TestAccount',
    ]


import unittest

from friends.errors import UnsupportedProtocolError
from friends.protocols.flickr import Flickr
from friends.tests.mocks import FakeAccount, LogMock
from friends.tests.mocks import TestModel, LogMock, mock
from friends.utils.account import Account, _find_accounts_uoa


class TestAccount(unittest.TestCase):
    """Test Account class."""

    def setUp(self):
        self.log_mock = LogMock('friends.utils.account')
        def connect_side_effect(signal, callback, account):
            # The account service provides a .connect method that connects a
            # signal to a callback.  We have to mock a side effect into the
            # connect() method to record this connection, which some of the
            # tests can then call.
            self._callback_signal = signal
            self._callback = callback
            self._callback_account = account
        # Set up the mock to return some useful values in the API expected by
        # the Account constructor.
        self.account_service = mock.Mock(**{
            'get_auth_data.return_value': mock.Mock(**{
                'get_credentials_id.return_value': 'fake credentials',
                'get_method.return_value': 'fake method',
                'get_mechanism.return_value': 'fake mechanism',
                'get_parameters.return_value': {
                            'ConsumerKey': 'fake_key',
                            'ConsumerSecret': 'fake_secret'},
                }),
            'get_account.return_value': mock.Mock(**{
                'get_settings_dict.return_value': dict(send_enabled=True),
                'id': 'fake_id',
                'get_provider_name.return_value': 'flickr',
                }),
            'get_service.return_value': mock.Mock(**{
                'get_name.return_value': 'fake_service',
                }),
            'connect.side_effect': connect_side_effect,
            })
        self.account = Account(self.account_service)

    def tearDown(self):
        self.log_mock.stop()

    def test_account_auth(self):
        # Test that the constructor initializes the 'auth' attribute.
        auth = self.account.auth
        self.assertEqual(auth.get_credentials_id(), 'fake credentials')
        self.assertEqual(auth.get_method(), 'fake method')
        self.assertEqual(auth.get_mechanism(), 'fake mechanism')
        self.assertEqual(auth.get_parameters(),
                         dict(ConsumerKey='fake_key',
                              ConsumerSecret='fake_secret'))

    def test_account_id(self):
        self.assertEqual(self.account.id, 'fake_id')

    def test_account_service(self):
        # The protocol attribute refers directly to the protocol used.
        self.assertIsInstance(self.account.protocol, Flickr)

    def test_account_unsupported(self):
        # Unsupported protocols raise exceptions in the Account constructor.
        mock = self.account_service.get_account()
        mock.get_provider_name.return_value = 'no service'
        with self.assertRaises(UnsupportedProtocolError) as cm:
            Account(self.account_service)
        self.assertEqual(cm.exception.protocol, 'no service')

    def test_on_account_changed(self):
        # Account.on_account_changed() gets called during the Account
        # constructor.  Test that it has the expected original key value.
        self.assertEqual(self.account.send_enabled, True)

    def test_dict_filter(self):
        # The get_settings_dict() filters everything that doesn't start with
        # 'friends/'
        self._callback_account.get_settings_dict.assert_called_with('friends/')

    def test_on_account_changed_signal(self):
        # Test that when the account changes, and a 'changed' signal is
        # received, the callback is called and the account is updated.
        #
        # Start by simulating a change in the account service.
        other_dict = dict(
            send_enabled=False,
            bee='two',
            cat='three',
            )
        adict = self.account_service.get_account().get_settings_dict
        adict.return_value = other_dict
        # Check that the signal has been connected.
        self.assertEqual(self._callback_signal, 'changed')
        # Check that the account is the object we expect it to be.
        self.assertEqual(self._callback_account,
                         self.account_service.get_account())
        # Simulate the signal.
        self._callback(self.account_service, self._callback_account)
        # Have the expected updates occurred?
        self.assertEqual(self.account.send_enabled, False)
        self.assertFalse(hasattr(self.account, 'bee'))
        self.assertFalse(hasattr(self.account, 'cat'))

    @mock.patch('friends.utils.account.manager')
    @mock.patch('friends.utils.account.Account')
    @mock.patch('friends.utils.account.Accounts')
    def test_find_accounts(self, accts, acct, manager):
        service = mock.Mock()
        get_enabled = manager.get_enabled_account_services
        get_enabled.return_value = [service]
        manager.reset_mock()
        accounts = _find_accounts_uoa()
        get_enabled.assert_called_once_with()
        acct.assert_called_once_with(service)
        self.assertEqual(accounts, {acct().id: acct()})
        self.assertEqual(self.log_mock.empty(),
                         'Flickr (fake_id) got send_enabled: True\n'
                         'Accounts found: 1\n')
