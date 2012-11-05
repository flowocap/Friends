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

from friends.errors import AuthorizationError
from friends.utils.base import Base, feature
from friends.utils.download import get_json
from friends.utils.time import iso8601utc, parsetime


log = logging.getLogger(__name__)


# This is contact information for the Flickr REST service.
# http://www.flickr.com/services/api/
API_KEY = '36f660117e6555a9cbda4309cfaf72d0'

# http://www.flickr.com/services/api/request.rest.html
REST_SERVER = 'http://api.flickr.com/services/rest'
UPLOAD_SERVER = 'http://api.flickr.com/services/upload'

# http://www.flickr.com/services/api/misc.buddyicons.html
FARM = 'http://farm{farm}.static.flickr.com/{server}/'
BUDDY_ICON_URL = FARM + 'buddyicons/{nsid}.jpg'
IMAGE_URL = FARM + '{nsid}_{secret}_{type}.jpg'
IMAGE_PAGE_URL = 'http://www.flickr.com/photos/{owner}/{nsid}'
PEOPLE_URL = 'http://www.flickr.com/people/{owner}'


class Flickr(Base):
    def _get_nsid(self):
        """Get the user's Flickr id.

        :return: The id, called NSID by the Flickr service.
        :rtype: str
        """
        if self._account.user_id is None:
            # Try to log in.
            if not self._login():
                return None
        return self._account.user_id

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        self._account.secret_token = authdata.get('TokenSecret')
        self._account.user_id = authdata.get('user_nsid')
        self._account.user_name = authdata.get('username')

    @feature
    def upload(self, picture_url, message='', obj_id='me'):
        pass

# http://www.flickr.com/services/api/flickr.photos.getContactsPublicPhotos.html
    @feature
    def receive(self):
        """Download all of a user's public photos."""
        user_id = self._get_nsid()
        if user_id is None:
            if self._account.user_id is None:
                # It's possible the login gave us a user_id but still failed.
                log.error('Flickr: No NSID available')
            raise AuthorizationError(
                self._account.id, 'No Flickr user id available')
        # The user is logged into Flickr.
        GET_arguments = dict(
            api_key         = API_KEY,
            user_id         = user_id,
            method          = 'flickr.photos.getContactsPublicPhotos',
            format          = 'json',
            nojsoncallback  = '1',
            extras          = 'date_upload,owner_name,icon_server',
            )
        response = get_json(REST_SERVER, GET_arguments)
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
            if (icon_farm is not None and
                icon_server is not None and
                owner is not None):
                # Then...
                icon_uri = BUDDY_ICON_URL.format(
                    farm=icon_farm, server=icon_server, nsid=owner)
                url = PEOPLE_URL.format(owner=owner)
            # Calculate the ISO 8601 UTC time string.
            raw_time = data.get('dateupload')
            timestamp = ''
            if raw_time is not None:
                try:
                    timestamp = iso8601utc(parsetime(raw_time))
                except ValueError:
                    pass
            # Images.
            farm = data.get('farm')
            server = data.get('server')
            secret = data.get('secret')
            img_url = ''
            img_src = ''
            img_thumb = ''
            if None not in (farm, server, secret):
                img_url = IMAGE_URL.format(farm=farm, server=server,
                                           nsid=owner, secret=secret, type='b')
                img_src = IMAGE_URL.format(farm=farm, server=server,
                                           nsid=owner, secret=secret, type='m')
                img_thumb = IMAGE_URL.format(farm=farm, server=server,
                                             nsid=owner, secret=secret,
                                             type='t')
            self._publish(
                message_id=data.get('id', ''),
                stream='images',
                sender=owner,
                sender_nick=ownername,
                icon_uri=icon_uri,
                url=url,
                from_me=from_me,
                message=data.get('title', ''),
                html=data.get('title', ''),
                timestamp=timestamp,
                img_url=img_url,
                img_src=img_src,
                img_thumb=img_thumb)
