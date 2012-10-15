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

"""Test the Account class."""

__all__ = [
    'TestAccount',
    'TestAccountManager',
    ]


import json
import unittest

from gi.repository import Dee

from friends.errors import UnsupportedProtocolError
from friends.protocols.flickr import Flickr
from friends.testing.helpers import FakeAccount
from friends.testing.mocks import SettingsIterMock
from friends.utils.account import Account, AccountManager
from friends.utils.base import Base
from friends.utils.model import COLUMN_INDICES, COLUMN_TYPES

try:
    # Python 3.3
    from unittest import mock
except ImportError:
    import mock


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


class TestAccount(unittest.TestCase):
    """Test Account class."""

    def setUp(self):
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
                'get_parameters.return_value': 'fake parameters',
                }),
            'get_account.return_value': mock.Mock(**{
                'get_settings_iter.return_value': SettingsIterMock(),
                'id': 'fake_id',
                'get_provider_name.return_value': 'flickr',
                }),
            'get_service.return_value': mock.Mock(**{
                'get_name.return_value': 'fake_service',
                }),
            'connect.side_effect': connect_side_effect,
            })
        self.account = Account(self.account_service)

    def test_account_auth(self):
        # Test that the constructor initializes the 'auth' attribute.
        auth = self.account.auth
        self.assertEqual(auth.id, 'fake credentials')
        self.assertEqual(auth.method, 'fake method')
        self.assertEqual(auth.mechanism, 'fake mechanism')
        self.assertEqual(auth.parameters, 'fake parameters')

    def test_account_id(self):
        # The 'id' key of the account gets the full service name.
        self.assertEqual(self.account.id, 'fake_id/flickr')

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

    def test_iter_filter(self):
        # The get_settings_iter() filters everything that doesn't start with
        # 'friends/'
        self._callback_account.get_settings_iter.assert_called_with('friends/')

    def test_on_account_changed_signal(self):
        # Test that when the account changes, and a 'changed' signal is
        # received, the callback is called and the account is updated.
        #
        # Start by simulating a change in the account service.
        other_iter = SettingsIterMock()
        other_iter.items = [
            (True, 'send_enabled', False),
            (True, 'bee', 'two'),
            (True, 'cat', 'three'),
            ]
        iter = self.account_service.get_account().get_settings_iter
        iter.return_value = other_iter
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

    def test_enabled(self):
        # .enabled() just passes through from the account service.
        self.account_service.get_enabled.return_value = True
        self.assertTrue(self.account.enabled)
        self.account_service.get_enabled.return_value = False
        self.assertFalse(self.account.enabled)

    def test_equal(self):
        # Two accounts are equal if their account services are equal.
        other = Account(self.account_service)
        self.assertEqual(self.account, other)

    def test_unequal(self):
        # Two accounts are unequal if their account services are unequal.  The
        # other mock service has to at least support the basic required API.
        other = Account(mock.Mock(**{
            'get_account.return_value': mock.Mock(**{
                'get_settings_iter.return_value': SettingsIterMock(),
                    # It's okay if the provider names are the same; the test
                    # is for whether the account services are the same or not,
                    # and in this test, they'll be different mock instances.
                    'get_provider_name.return_value': 'flickr',
                }),
            }))
        self.assertNotEqual(self.account, other)


accounts_manager = mock.Mock()
accounts_manager.new_for_service_type(
    'microblogging').get_enabled_account_services.return_value = []


@mock.patch('gi.repository.Accounts.Manager', accounts_manager)
@mock.patch('friends.utils.account.Account', FakeAccount)
class TestAccountManager(unittest.TestCase):
    """Test the AccountManager API."""

    def setUp(self):
        self.account_service = mock.Mock()

    def test_account_manager(self):
        # Test that the AccountManager adds the expected accounts to its
        # internal mapping.
        def refresh():
            pass
        AccountManager(refresh)

    def test_account_manager_add_new_account(self):
        # Explicitly adding a new account puts the account's global_id into
        # the account manager's mapping.
        def refresh():
            pass
        manager = AccountManager(refresh)
        manager.add_new_account(self.account_service)
        self.assertIn('faker/than fake', manager._accounts)

    def test_account_manager_enabled_event(self):
        # Mimic a reaction to the enabled-event callback.
        refreshed = False
        def refresh():
            nonlocal refreshed
            refreshed = True
        accounts_manager.get_account().list_services.return_value = []
        manager = AccountManager(refresh)
        manager._on_enabled_event(accounts_manager, 'faker/than fake')
        self.assertTrue(refreshed)

    def test_account_manager_delete_account_no_account(self):
        # Deleting an account removes the global_id from the mapping.  But if
        # that global id is missing, then it does not cause an exception.
        # Also, the refresh callback is *not* called.
        refreshed = False
        def refresh():
            nonlocal refreshed
            refreshed = True
        manager = AccountManager(refresh)
        self.assertNotIn('faker/than fake', manager._accounts)
        manager._on_account_deleted(accounts_manager, 'faker/than fake')
        self.assertNotIn('faker/than fake', manager._accounts)
        self.assertFalse(refreshed)

    def test_account_manager_delete_account(self):
        # Deleting an account removes the id from the mapping. But if
        # that id is missing, then it does not cause an exception.
        refreshed = False
        def refresh():
            nonlocal refreshed
            refreshed = True
        manager = AccountManager(refresh)
        manager.add_new_account(self.account_service)
        manager._on_account_deleted(accounts_manager, 'faker/than fake')
        self.assertNotIn('faker/than fake', manager._accounts)
        self.assertTrue(refreshed)

    @mock.patch('friends.utils.account.Model', TestModel)
    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_account_manager_delete_account_preserve_messages(self):
        # Deleting an Account should not delete messages from the row
        # that exist on other protocols too.
        manager = AccountManager(lambda:None)
        manager.add_new_account(self.account_service)
        example_row = [[['twitter', '6/twitter', '1234'],
             ['base', 'faker/than fake', '5678']],
            'messages', 'Fred Flintstone', 'fred', True,
            '2012-08-28T19:59:34', 'Yabba dabba dooooo!', '', '', '', '', '',
            '', '', 0.0, False, '', '', '', '', '', '', '', '', '', '', '',
            '', '', '', '', '', '', [], '', '', '']
        result_row = [[['twitter', '6/twitter', '1234']],
            'messages', 'Fred Flintstone', 'fred', True,
            '2012-08-28T19:59:34', 'Yabba dabba dooooo!', '', '', '', '', '',
            '', '', 0.0, False, '', '', '', '', '', '', '', '', '', '', '',
            '', '', '', '', '', '', [], '', '', '']
        row_iter = TestModel.append(*example_row)
        from friends.utils.base import _seen_ids
        _seen_ids[('base', 'faker/than fake', '5678')] = row_iter
        self.assertEqual(list(TestModel.get_row(0)), example_row)
        manager._on_account_deleted(accounts_manager, 'faker/than fake')
        self.assertEqual(list(TestModel.get_row(0)), result_row)