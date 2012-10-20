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

"""DBus service object for URL shortening."""

__all__ = [
    'URLShorten',
    ]


import logging

import dbus
import dbus.service

from friends.shorteners import lookup

log = logging.getLogger(__name__)


class URLShorten(dbus.service.Object):
    __dbus_object_path__ = '/com/canonical/friends/URLShorten'

    def __init__(self, settings):
        self.settings = settings
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName('com.canonical.Friends.URLShorten',
                                        bus=self.bus)
        super().__init__(bus_name, self.__dbus_object_path__)

    @dbus.service.method('com.canonical.Friends.URLShorten',
                         in_signature='s', out_signature='s')
    def Shorten(self, url):
        """Shorten a URL.

        Takes a url as a string and returns a shortened url as a string.

        >>> import dbus
        >>> url = 'http://www.example.com/this/is/a/long/url'
        >>> obj = dbus.SessionBus().get_object(
        ...     'com.canonical.Friends.URLShorten',
        ...     '/com/canonical/friends/URLShorten')
        >>> shortener = dbus.Interface(obj, 'com.canonical.Friends.URLShorten')
        ... short_url = shortener.Shorten(url)
        """
        service_name = self.settings.get_string('urlshorter')
        log.info('Shortening URL {} with {}', url, service_name)
        if (lookup.is_shortened(url) or
            not self.settings.get_boolean('shorten-urls')):
            # It's already shortened, or the preference is not set.
            return url
        service = lookup.lookup(service_name)
        try:
            return service.shorten(url)
        except Exception:
            log.exception('URL shortening class: {}'.format(service))
            return url
