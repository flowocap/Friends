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

"""Internal Friends exceptions."""

__all__ = [
    'AuthorizationError',
    'FriendsError',
    'UnsupportedProtocolError',
    ]


class FriendsError(Exception):
    """Base class for all internal Friends exceptions."""


class AuthorizationError(FriendsError):
    """Backend service authorization errors."""

    def __init__(self, account, message):
        self.account = account
        self.message = message

    def __str__(self):
        return '{} (account: {})'.format(self.message, self.account)


class UnsupportedProtocolError(FriendsError):
    def __init__(self, protocol):
        self.protocol = protocol

    def __str__(self):
        return 'Unsupported protocol: {}'.format(self.protocol)
