# friends-dispatcher -- send & receive messages from any social network
# Copyright (C) 2013  Canonical Ltd
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

"""linkee.com URL shortener for Friends"""

__all__ = [
    'URLShortener',
    ]


from friends.shorteners.base import ShortenerBase


class URLShortener(ShortenerBase):
    URL_TEMPLATE = 'http://api.linkee.com/1.0/shorten?format=text&input={}'
    fqdn = 'http://linkee.com'
    name = 'linkee.com'
