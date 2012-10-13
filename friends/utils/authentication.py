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

from gi.repository import GObject, Signon
GObject.threads_init(None)


class Authentication:
    def __init__(self, account, log=None):
        self.account = account
        self.log = (logging.getLogger('friends.service')
                    if log is None
                    else log)
        self._reply = None
        self._authenticating = False

    def login(self):
        auth = self.account.auth
        self.auth_session = Signon.AuthSession.new(auth.id, auth.method)
        self._authenticating = True
        self._loop = GObject.MainLoop()
        self.auth_session.process(
            auth.parameters, auth.mechanism,
            self._login_cb, None)
        if self._authenticating:
            self._loop.run()
        return self._reply

    def _login_cb(self, session, reply, error, user_data):
        self._authenticating = False
        if error:
            self.log.error('Got authentication error: {}', error.message)
        else:
            self._reply = reply
        self.log.debug('Login completed')
        self._loop.quit()
