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

"""The libaccounts account service wrapper."""

__all__ = [
    'Account',
    'find_accounts',
    ]


import logging

from gi.repository import Accounts
from threading import Lock

from friends.errors import UnsupportedProtocolError
from friends.utils.manager import protocol_manager
from friends.utils.authentication import manager


log = logging.getLogger(__name__)


def _find_accounts_uoa():
    """Consult Ubuntu Online Accounts for the accounts we have."""
    accounts = {}
    for service in manager.get_enabled_account_services():
        try:
            account = Account(service)
        except UnsupportedProtocolError as error:
            log.info(error)
        else:
            accounts[account.id] = account
    log.info('Accounts found: {}'.format(len(accounts)))
    return accounts


def find_accounts():
    # TODO: Implement GOA support, then fill out this method with some
    # logic for determining whether to use UOA or GOA.
    return _find_accounts_uoa()


class Account:
    """A thin wrapper around libaccounts API."""

    # Properties to pull out of the libaccounts iterator.  See the discussion
    # below for more details.
    _LIBACCOUNTS_PROPERTIES = (
        'send_enabled',
        )

    # Defaults for the known and useful attributes.
    consumer_secret = None
    consumer_key = None
    access_token = None
    secret_token = None
    send_enabled = None
    user_name = None
    user_id = None
    auth = None
    id = None

    def __init__(self, account_service):
        self.auth = account_service.get_auth_data()
        if self.auth is not None:
            auth_params = self.auth.get_parameters()
            self.consumer_key = auth_params.get('ConsumerKey')
            self.consumer_secret = auth_params.get('ConsumerSecret')
        else:
            raise UnsupportedProtocolError(
                'This AgAccountService is missing AgAuthData!')

        # The provider in libaccounts should match the name of our protocol.
        account = account_service.get_account()
        self.id = account.id
        protocol_name = account.get_provider_name()
        protocol_class = protocol_manager.protocols.get(protocol_name)
        if protocol_class is None:
            raise UnsupportedProtocolError(protocol_name)
        self.protocol = protocol_class(self)
        # Connect responders to changes in the account information.
        account_service.connect('changed', self._on_account_changed, account)
        self._on_account_changed(account_service, account)
        # This is used to prevent multiple simultaneous login attempts.
        self.login_lock = Lock()

    def _on_account_changed(self, account_service, account):
        settings = account.get_settings_dict('friends/')
        for (key, value) in settings.items():
            if key in Account._LIBACCOUNTS_PROPERTIES:
                log.debug('{} ({}) got {}: {}'.format(
                        self.protocol._Name, self.id, key, value))
                setattr(self, key, value)
