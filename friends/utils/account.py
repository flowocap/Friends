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
from friends.utils.model import COLUMN_INDICES, Model


log = logging.getLogger('friends.service')


class AccountManager:
    """Manage the accounts that we know about."""

    def __init__(self, refresh_callback):
        self._callback = refresh_callback
        self._accounts = {}
        # Ask libaccounts for a manager of the microblogging services.
        # Connect callbacks to the manager so that we can react when accounts
        # are added or deleted.
        manager = Accounts.Manager.new_for_service_type('microblogging')
        manager.connect('enabled-event', self._on_enabled_event)
        manager.connect('account-deleted', self._on_account_deleted)
        # Add all the currently known accounts.
        for account_service in manager.get_enabled_account_services():
            self.add_new_account(account_service)
        log.info('Accounts found: {}'.format(len(self._accounts)))

    def _on_enabled_event(self, manager, account_id):
        """React to new microblogging accounts being added."""
        log.debug('Adding account {}', account_id)
        account = manager.get_account(account_id)
        for service in account.list_services():
            account_service = Accounts.AccountService.new(account, service)
            if account_service.get_enabled():
                self.add_new_account(account_service)
        self._callback()

    def _on_account_deleted(self, manager, account_id):
        log.debug('Deleting account {}', account_id)
        # If we don't know about the given account id, just return and do not
        # call the refresh callback.
        try:
            account = self._accounts.pop(account_id)
        except KeyError:
            log.debug('Attempting to delete unknown account: {}', account_id)
            return

        for row in Model:
            for triple in row[COLUMN_INDICES['message_ids']]:
                if account_id in triple:
                    account.protocol._unpublish(triple[-1])

        self._callback()

    def add_new_account(self, account_service):
        new_account = Account(account_service)
        self._accounts[new_account.id] = new_account

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

    @property
    def enabled(self):
        return self.account_service.get_enabled()

    def __eq__(self, other):
        return self.account_service == other.account_service

    def __ne__(self, other):
        return self.account_service != other.account_service