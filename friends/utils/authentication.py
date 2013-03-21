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

"""Authentication through the single-sign-on service."""

__all__ = [
    'Authentication',
    ]


import logging
import time

from gi.repository import GObject, Accounts, Signon

from friends.errors import AuthorizationError


GObject.threads_init(None)


log = logging.getLogger(__name__)


LOGIN_TIMEOUT = 30 # Currently this is measured in half-seconds.


# Yes, this is not the most logical place to instantiate this, but I
# couldn't do it in account.py due to cyclical import dependencies.
manager = Accounts.Manager.new_for_service_type('microblogging')


class Authentication:
    def __init__(self, account_id):
        self.account_id = account_id
        account = manager.get_account(account_id)
        for service in account.list_services():
            self.auth = Accounts.AccountService.new(
                account, service).get_auth_data()
            break
        else:
            raise AuthorizationError(
                account_id,
                'No AgService found, is your UOA plugin written correctly?')
        self._reply = None

    def login(self):
        auth = self.auth
        self.auth_session = Signon.AuthSession.new(
            auth.get_credentials_id(),
            auth.get_method())
        self.auth_session.process(
            auth.get_parameters(),
            auth.get_mechanism(),
            self._login_cb,
            None)
        timeout = LOGIN_TIMEOUT
        while self._reply is None and timeout > 0:
            # We're building a synchronous API on top of an inherently
            # async library, so we need to block this thread until the
            # callback gets called to give us the response to return.
            time.sleep(0.5)
            timeout -= 1
        if self._reply is None:
            raise AuthorizationError(self.account_id, 'Login timed out.')
        if 'AccessToken' not in self._reply:
            raise AuthorizationError(
                self.account_id,
                'No AccessToken found: {!r}'.format(self._reply))
        return self._reply

    def _login_cb(self, session, reply, error, user_data):
        self._reply = reply
        if error:
            exception = AuthorizationError(self.account_id, error.message)
            # Mardy says this error can happen during normal operation.
            if error.message.endswith('userActionFinished error: 10'):
                log.error(str(exception))
            else:
                raise exception
        log.debug('Login completed')
