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


log = logging.getLogger(__name__)


def _find_accounts_uoa():
    """Consult Ubuntu Online Accounts for the accounts we have."""
    accounts = {}
    manager = Accounts.Manager.new_for_service_type('microblogging')
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
        settings = account.get_settings_iter('friends/')
        # This is horrible on several fronts.  Ideally, we'd like to just get
        # the small set of values that we care about, but the Python bindings
        # for gi.repository.Accounts does not make this easy.  First, there's
        # no direct mapping to .get_value() - you have to use .get_string(),
        # .get_int(), and .get_bool().  But even there, it's not clear that
        # the values its returning are the right settings values.  E.g. in my
        # tests, I received *different* values than the ones I expected, or
        # the ones returned from the iterator below.  It's also way to easy to
        # segfault .get_value() -- try this:
        #
        # account_service.get_bool('friends/send_enabled')
        #
        # KABOOM!
        #
        # The other problem here is that libaccounts doesn't provide an
        # override for AgAccountSettingIter so that it supports the Python
        # iteration protocol.  We could use 2-argument built-in iter() with a
        # sentinel of (False, None, None), but afaict, the second and third
        # items are undocumented when the first is False, so that would just
        # be crossing our fingers.
        #
        # Of all the options, this appears to be the most reliable and safest
        # way until the libaccounts API improves.
        while True:
            success, key, value = settings.next()
            if success:
                log.debug('{} got {}: {}'.format(self.id, key, value))
                # Testing for tuple membership makes this easy to expand
                # later, if necessary.
                if key in Account._LIBACCOUNTS_PROPERTIES:
                    setattr(self, key, value)
            else:
                break
