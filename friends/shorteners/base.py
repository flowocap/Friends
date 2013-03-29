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

"""Convenient base class for URL shorteners."""

__all__ = [
    'ShortenerBase',
    ]


from urllib.parse import quote

from friends.utils.http import Downloader


class ShortenerBase:
    URL_TEMPLATE = None
    name = None
    fqdn = None

    def shorten(self, url):
        return Downloader(
            self.URL_TEMPLATE.format(quote(url, safe=''))).get_string().rstrip()
