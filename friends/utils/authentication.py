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

"""Authentication through the single-sign-on service."""

__all__ = [
    'Authentication',
    ]


import logging

from threading import Lock

from gi.repository import GObject, Signon
GObject.threads_init(None)


class Authentication:
    def __init__(self, account, log=None):
        self.account = account
        self.log = log or logging.getLogger('friends.service')
        self._reply = None
        self._lock = Lock()
        # First call to acquire() returns immediately, but sets up the
        # lock so that our *next* call will block this thread.
        self._lock.acquire()

    def login(self):
        auth = self.account.auth
        self.auth_session = Signon.AuthSession.new(auth.id, auth.method)
        self.auth_session.process(
            auth.parameters, auth.mechanism,
            self._login_cb, None)
        if self._reply is None:
            # We're building a synchronous API on top of an inherently
            # async library, so we need to block this thread until the
            # callback gets called to give us the response to return.
            self._lock.acquire()
        return self._reply

    def _login_cb(self, session, reply, error, user_data):
        self._reply = reply
        if error:
            self.log.error('Got authentication error: {}'.format(error.message))
        self.log.debug('Login completed')
        if self._lock.locked():
            self._lock.release()
