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

"""The Instagram protocol plugin."""


__all__ = [
    'Instagram',
    ]

import time
import logging

from friends.utils.base import Base, feature
from friends.utils.cache import JsonCache
from friends.utils.http import Downloader, Uploader
from friends.utils.time import parsetime, iso8601utc
from friends.errors import FriendsError

log = logging.getLogger(__name__)

class Instagram(Base):
    _api_base = 'https://api.instagram.com/v1/{endpoint}?access_token={token}'
    def _whoami(self, authdata):
        """Identify the authenticating user."""
        url = self._api_base.format(
            endpoint='users/self',
            token=self._get_access_token())
        result = Downloader(url).get_json()
        self._account.user_id = result.get('id')
        self._account.user_name = result.get('username')

    def _publish_entry(self, entry, stream='messages'):
        """Publish a single update into the Dee.SharedModel."""
        message_id = entry.get('id')

        if message_id is None:
            # We can't do much with this entry.
            return

        person = entry.get('user')
        nick = person.get('username')
        name = person.get('full_name')
        person_id = person.get('id')
        message= '%s shared a picture on Instagram.' % nick
        person_icon = person.get('profile_picture')
        person_url = 'http://instagram.com/' + nick
        picture = entry.get('images').get('thumbnail').get('url')
        if entry.get('caption'):
            desc = entry.get('caption').get('text', '')
        else:
            desc = ''
        url = entry.get('link')
        timestamp = iso8601utc(parsetime(entry.get('created_time')))
        likes = entry.get('likes').get('count')
        liked = entry.get('user_has_liked')
        location = entry.get('location', {})
        if location:
            latitude = location.get('latitude', '')
            longitude = location.get('longitude', '')
        else:
            latitude = 0
            longitude = 0

        args = dict(
             message_id=message_id,
             message=message,
             stream=stream,
             likes=likes,
             sender_id=person_id,
             sender=name,
             sender_nick=nick,
             url=person_url,
             icon_uri=person_icon,
             link_url=url,
             link_picture=picture,
             link_desc=desc,
             timestamp=timestamp,
             liked=liked,
             latitude=latitude,
             longitude=longitude
             )

        self._publish(**args)

        # If there are any replies, publish them as well.
        parent_id = message_id
        for comment in entry.get('comments', {}).get('data', []):
            if comment:
                message_id = comment.get('id')
                message = comment.get('text')
                person = comment.get('from')
                sender_nick = person.get('username')
                timestamp = iso8601utc(parsetime(comment.get('created_time')))
                icon_uri = person.get('profile_picture')
                sender_id = person.get('id')
                sender = person.get('full_name')
                log.debug('Comment from: ' + sender_nick)
                args = dict(
                     stream='reply_to/{}'.format(parent_id),
                     message_id=message_id,
                     message=message,
                     timestamp=timestamp,
                     sender_nick=sender_nick,
                     icon_uri=icon_uri,
                     sender_id=sender_id,
                     sender=sender
                     )
                self._publish(**args)

    @feature
    def home(self):
        """Gather and publish public timeline messages."""
        url = self._api_base.format(
            endpoint='users/self/feed',
            token=self._get_access_token())
        result = Downloader(url).get_json()
        values = result.get('data')
        for update in values:
            self._publish_entry(update)
    
    @feature
    def receive(self):
        """Gather and publish all incoming messages."""
        self.home()
        return self._get_n_rows()
