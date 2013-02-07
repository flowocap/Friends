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
    'ProtocolBase',
    'ShortenerBase',
    ]


from urllib.request import urlopen


class ProtocolBase:
    """Base class for PROTOCOL_INFO."""

    name = None
    version = None
    fqdn = None

    def __getitem__(self, name):
        try:
            return getattr(self, name)
        except AttributeError as error:
            raise KeyError from error


class ShortenerBase:
    URL_TEMPLATE = None

    def shorten(self, url):
        with urlopen(self.URL_TEMPLATE.format(url)) as page:
            return page.read()
