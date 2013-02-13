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

"""TinyURL.com URL shortener for Friends

macno (Michele Azzolari) - 02/13/2008
"""

__all__ = [
    'URLShortener',
    ]


from friends.shorteners.base import ShortenerBase


class URLShortener(ShortenerBase):
    URL_TEMPLATE = 'http://tinyurl.com/api-create.php?url={}'
    fqdn = 'http://tinyurl.com'
    name = 'tinyurl.com'
