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

"""Flickr plugin."""

__all__ = [
    'Flickr',
    ]


import logging

from friends.utils.avatar import Avatar
from friends.utils.base import Base, feature
from friends.utils.http import Downloader, Uploader
from friends.utils.time import iso8601utc, parsetime


log = logging.getLogger(__name__)


# This is contact information for the Flickr REST service.
# http://www.flickr.com/services/api/
API_KEY = '36f660117e6555a9cbda4309cfaf72d0'

# http://www.flickr.com/services/api/request.rest.html
REST_SERVER = 'http://api.flickr.com/services/rest'

# http://www.flickr.com/services/api/misc.buddyicons.html
FARM = 'http://farm{farm}.static.flickr.com/{server}/'
BUDDY_ICON_URL = FARM + 'buddyicons/{nsid}.jpg'
IMAGE_URL = FARM + '{nsid}_{secret}_{type}.jpg'
IMAGE_PAGE_URL = 'http://www.flickr.com/photos/{owner}/{nsid}'
PEOPLE_URL = 'http://www.flickr.com/people/{owner}'


class Flickr(Base):
    def _whoami(self, authdata):
        """Identify the authenticating user."""
        self._account.secret_token = authdata.get('TokenSecret')
        self._account.user_id = authdata.get('user_nsid')
        self._account.user_name = authdata.get('username')

# http://www.flickr.com/services/api/flickr.photos.getContactsPublicPhotos.html
    @feature
    def receive(self):
        """Download all of a user's public photos."""
        # This triggers logging in, if necessary.
        self._get_access_token()

        GET_arguments = dict(
            api_key         = API_KEY,
            user_id         = self._account.user_id,
            method          = 'flickr.photos.getContactsPublicPhotos',
            format          = 'json',
            nojsoncallback  = '1',
            extras          = 'date_upload,owner_name,icon_server',
            )

        response = Downloader(REST_SERVER, GET_arguments).get_json()
        for data in response.get('photos', {}).get('photo', []):
            # Pre-calculate some values to publish.
            username = data.get('username', '')
            ownername = data.get('ownername', '')

            # Icons.
            icon_farm = data.get('iconfarm')
            icon_server = data.get('iconserver')
            owner = data.get('owner')
            icon_uri = ''
            url = ''
            from_me = (ownername == username)
            if None not in (icon_farm, icon_server, owner):
                icon_uri = Avatar.get_image(BUDDY_ICON_URL.format(
                    farm=icon_farm, server=icon_server, nsid=owner))
                url = PEOPLE_URL.format(owner=owner)

            # Calculate the ISO 8601 UTC time string.
            try:
                timestamp = iso8601utc(parsetime(data.get('dateupload', '')))
            except ValueError:
                timestamp = ''

            # Images.
            farm = data.get('farm')
            server = data.get('server')
            secret = data.get('secret')
            img_url = ''
            img_src = ''
            img_thumb = ''
            if None not in (farm, server, secret):
                args = dict(farm=farm, server=server, nsid=owner, secret=secret)
                img_url = IMAGE_URL.format(type='b', **args)
                img_src = IMAGE_URL.format(type='m', **args)
                img_thumb = IMAGE_URL.format(type='t', **args)

            self._publish(
                message_id=data.get('id', ''),
                stream='images',
                sender=ownername,
                sender_id=owner,
                sender_nick=ownername,
                icon_uri=icon_uri,
                url=url,
                from_me=from_me,
                message=data.get('title', ''),
                timestamp=timestamp,
                img_url=img_url,
                img_src=img_src,
                img_thumb=img_thumb)
