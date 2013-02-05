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

"""is.gd URL shortener for Friends

macno (Michele Azzolari) - 02/13/2008
"""

__all__ = [
    'PROTOCOL_INFO',
    'URLShortener',
    ]


from friends.shorteners.base import ProtocolBase, ShortenerBase


class _PROTOCOL_INFO(ProtocolBase):
    name = 'is.gd'
    version = 0.1
    fqdn = 'http://is.gd'


PROTOCOL_INFO = _PROTOCOL_INFO()


class URLShortener(ShortenerBase):
    URL_TEMPLATE = 'http://is.gd/api.php?longurl={}'
