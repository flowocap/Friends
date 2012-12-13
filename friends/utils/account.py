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

"""The libaccounts account service wrapper."""

__all__ = [
    'Account',
    'AccountManager',
    ]


import logging

from gi.repository import Accounts
from threading import Lock

from friends.errors import UnsupportedProtocolError
from friends.utils.manager import protocol_manager


log = logging.getLogger(__name__)


class AccountManager:
    """Manage the accounts that we know about."""

    def __init__(self):
        self._accounts = {}
        # Ask libaccounts for a manager of the microblogging services.
        # Connect callbacks to the manager so that we can react when accounts
        # are added or deleted.
        manager = Accounts.Manager.new_for_service_type('microblogging')
        manager.connect('enabled-event', self._on_enabled_event)
        manager.connect('account-deleted', self._on_account_deleted)
        # Add all the currently known accounts.
        for account_service in manager.get_enabled_account_services():
            self._add_new_account(account_service)
        log.info('Accounts found: {}'.format(len(self._accounts)))

    def _get_id(self, manager, account_id):
        """Instantiate an AccountService and identify it."""
        account = manager.get_account(account_id)
        for service in account.list_services():
            account_service = Accounts.AccountService.new(account, service)
            id_ = '{}/{}'.format(
                account_id,
                account_service.get_service().get_display_name().lower())
            return account_service, id_
        return (None, None)

    def _on_enabled_event(self, manager, account_id):
        """React to new microblogging accounts being enabled or disabled."""
        account_service, id_ = self._get_id(manager, account_id)
        if account_service is not None and account_service.get_enabled():
            log.debug('Adding account {}'.format(id_))
            account = self._add_new_account(account_service)
            if account is not None:
                account.protocol('receive')
        else:
            # If an account has been disabled in UOA, we should remove
            # it's messages from the SharedModel.
            self._unpublish_entire_account(id_)

    def _on_account_deleted(self, manager, account_id):
        account_service, id_ = self._get_id(manager, account_id)
        if id_ is not None:
            log.debug('Deleting account {}'.format(id_))
            self._unpublish_entire_account(id_)

    def _unpublish_entire_account(self, id_):
        """Delete all the account's messages from the SharedModel."""
        log.debug('Deleting all messages from {}.'.format(id_))
        account = self._accounts.pop(id_, None)
        if account is not None:
            account.protocol._unpublish_all()

    def _add_new_account(self, account_service):
        try:
            new_account = Account(account_service)
        except UnsupportedProtocolError as error:
            log.info(error)
        else:
            self._accounts[new_account.id] = new_account
            return new_account

    def get_all(self):
        return self._accounts.values()

    def get(self, account_id, default=None):
        return self._accounts.get(account_id, default)


class AuthData:
    """This class serves as a sub-namespace for Account instances."""

    def __init__(self, auth_data):
        self.id = auth_data.get_credentials_id()
        self.method = auth_data.get_method()
        self.mechanism = auth_data.get_mechanism()
        self.parameters = auth_data.get_parameters()


class Account:
    """A thin wrapper around libaccounts API."""

    # Properties to pull out of the libaccounts iterator.  See the discussion
    # below for more details.
    _LIBACCOUNTS_PROPERTIES = (
        'send_enabled',
        )

    # Defaults for the known and useful attributes.
    access_token = None
    secret_token = None
    send_enabled = None
    user_name = None
    user_id = None
    auth = None
    id = None

    def __init__(self, account_service):
        self.account_service = account_service
        self.auth = AuthData(account_service.get_auth_data())
        # The provider in libaccounts should match the name of our protocol.
        account = account_service.get_account()
        protocol_name = account.get_provider_name()
        protocol_class = protocol_manager.protocols.get(protocol_name)
        if protocol_class is None:
            raise UnsupportedProtocolError(protocol_name)
        self.protocol = protocol_class(self)
        # account.id is a number, and the protocol_name is a word, so the
        # resulting id will look something like '6/twitter' or '2/facebook'
        self.id = '{}/{}'.format(account.id, protocol_name)
        # Connect responders to changes in the account information.
        account_service.connect('changed', self._on_account_changed, account)
        self._on_account_changed(account_service, account)
        # This is used to prevent multiple simultaneous login attempts.
        self.login_lock = Lock()

    def _on_account_changed(self, account_service, account):
        settings = account.get_settings_dict('friends/')
        for (key, value) in settings.items():
            if key in Account._LIBACCOUNTS_PROPERTIES:
                log.debug('{} got {}: {}'.format(self.id, key, value))
                setattr(self, key, value)

    @property
    def enabled(self):
        return self.account_service.get_enabled()

    def __eq__(self, other):
        if other is None:
            return False
        return self.account_service == other.account_service

    def __ne__(self, other):
        if other is None:
            return True
        return self.account_service != other.account_service
