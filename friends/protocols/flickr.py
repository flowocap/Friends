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

"""Flickr plugin."""


__all__ = [
    'Flickr',
    ]


import re
import time
import logging

from friends.utils.avatar import Avatar
from friends.utils.base import Base, feature
from friends.utils.http import Downloader, Uploader
from friends.utils.time import iso8601utc, parsetime
from friends.errors import FriendsError


log = logging.getLogger(__name__)


# http://www.flickr.com/services/api/request.rest.html
REST_SERVER = 'http://api.flickr.com/services/rest'

# http://www.flickr.com/services/api/upload.api.html
UPLOAD_SERVER = 'http://api.flickr.com/services/upload'

# http://www.flickr.com/services/api/misc.buddyicons.html
FARM = 'http://farm{farm}.static.flickr.com/{server}/'
BUDDY_ICON_URL = FARM + 'buddyicons/{nsid}.jpg'
IMAGE_URL = FARM + '{nsid}_{secret}_{type}.jpg'
IMAGE_PAGE_URL = 'http://www.flickr.com/photos/{owner}/{nsid}'
PEOPLE_URL = 'http://www.flickr.com/people/{owner}'


# Some regex for parsing XML when JSON is not available.
PHOTOID = re.compile('<photoid>(\d+)</photoid>').search


class Flickr(Base):
    def _whoami(self, authdata):
        """Identify the authenticating user."""
        self._account.secret_token = authdata.get('TokenSecret')
        self._account.user_id = authdata.get('user_nsid')
        self._account.user_name = authdata.get('username')
        self._account.user_full_name = authdata.get('fullname')

    def _get_url(self, params=None):
        """Access the Flickr API with correct OAuth signed headers."""
        method = 'GET'
        headers = self._get_oauth_headers(
            method=method,
            url=REST_SERVER,
            data=params or {},
            )

        response = Downloader(
            REST_SERVER,
            params=params,
            headers=headers,
            method=method,
            ).get_json()
        self._is_error(response)
        return response

# http://www.flickr.com/services/api/flickr.people.getInfo.html
    def _get_avatar(self, nsid):
        args = dict(
            api_key=self._account.consumer_key,
            method='flickr.people.getInfo',
            format='json',
            nojsoncallback='1',
            user_id=nsid,
            )
        response = self._get_url(args)
        person = response.get('person', {})
        iconfarm = person.get('iconfarm')
        iconserver = person.get('iconserver')
        if None in (iconfarm, iconserver):
            return Avatar.get_image(
                'http://www.flickr.com/images/buddyicon.gif')
        avatar = BUDDY_ICON_URL.format(
            farm=iconfarm,
            server=iconserver,
            nsid=nsid)
        return Avatar.get_image(avatar)

# http://www.flickr.com/services/api/flickr.photos.getContactsPhotos.html
    @feature
    def receive(self):
        """Download all of a user's public photos."""
        # Trigger loggin in.
        self._get_access_token()

        args = dict(
            api_key=self._account.consumer_key,
            method='flickr.photos.getContactsPhotos',
            format='json',
            nojsoncallback='1',
            extras='date_upload,owner_name,icon_server,geo',
            )

        response = self._get_url(args)
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
                timestamp=timestamp,
                link_caption=data.get('title', ''),
                link_url=img_url,
                link_picture=img_src,
                link_icon=img_thumb,
                latitude=data.get('latitude', 0.0),
                longitude=data.get('longitude', 0.0),
                )
        return self._get_n_rows()

# http://www.flickr.com/services/api/upload.api.html
    @feature
    def upload(self, picture_uri, title=''):
        """Upload local or remote image or video to album."""
        self._get_access_token()

        args = dict(
            api_key=self._account.consumer_key,
            title=title,
            )

        headers = self._get_oauth_headers(
            method='POST',
            url=UPLOAD_SERVER,
            data=args,
            )

        response = Uploader(
            UPLOAD_SERVER,
            picture_uri,
            picture_key='photo',
            headers=headers,
            **args
            ).get_string()

        try:
            post_id = PHOTOID(response).group(1)
        except AttributeError:
            raise FriendsError(response)
        else:
            destination_url = IMAGE_PAGE_URL.format(
                owner=self._account.user_name,
                nsid=post_id,
                )
            self._publish(
                from_me=True,
                stream='images',
                message_id=post_id,
                message=title,
                sender=self._account.user_full_name,
                sender_id=self._account.user_id,
                sender_nick=self._account.user_name,
                timestamp=iso8601utc(int(time.time())),
                url=destination_url,
                icon_uri=self._get_avatar(self._account.user_id),
                )
            return destination_url
