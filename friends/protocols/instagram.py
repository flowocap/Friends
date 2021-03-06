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


import logging

from friends.utils.base import Base, feature
from friends.utils.http import Downloader
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
        self._account.user_id = result.get('data').get('id')
        self._account.user_name = result.get('data').get('username')

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
        timestamp = entry.get('created_time')
        if timestamp is not None:
            timestamp = iso8601utc(parsetime(timestamp))
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
                self._publish_comment(
                    comment, stream='reply_to/{}'.format(parent_id))
        return args['url']

    def _publish_comment(self, comment, stream):
        """Publish a single comment into the Dee.SharedModel."""
        message_id = comment.get('id')
        if message_id is None:
            return
        message = comment.get('text', '')
        person = comment.get('from', {})
        sender_nick = person.get('username')
        timestamp = comment.get('created_time')
        if timestamp is not None:
            timestamp = iso8601utc(parsetime(timestamp))
        icon_uri = person.get('profile_picture')
        sender_id = person.get('id')
        sender = person.get('full_name')

        args = dict(
             stream=stream,
             message_id=message_id,
             message=message,
             timestamp=timestamp,
             sender_nick=sender_nick,
             icon_uri=icon_uri,
             sender_id=sender_id,
             sender=sender,
             )
        self._publish(**args)

    @feature
    def home(self):
        """Gather and publish public timeline messages."""
        url = self._api_base.format(
            endpoint='users/self/feed',
            token=self._get_access_token())
        result = Downloader(url).get_json()
        values = result.get('data', {})
        for update in values:
            self._publish_entry(update)

    @feature
    def receive(self):
        """Gather and publish all incoming messages."""
        self.home()
        return self._get_n_rows()

    def _send(self, obj_id, message, endpoint, stream='messages'):
        """Used for posting a message or comment."""
        token = self._get_access_token()

        url = self._api_base.format(endpoint=endpoint, token=token)

        result = Downloader(
            url,
            method='POST',
            params=dict(access_token=token, text=message)).get_json()
        new_id = result.get('id')
        if new_id is None:
            raise FriendsError(
                'Failed sending to Instagram: {!r}'.format(result))
        url = self._api_base.format(endpoint=endpoint, token=token)
        comment = Downloader(url, params=dict(access_token=token)).get_json()
        return self._publish_entry(entry=comment, stream=stream)

    @feature
    def send_thread(self, obj_id, message):
        """Write a comment on some existing picture."""
        return self._send(
            obj_id,
            message,
            'media/{}/comments'.format(obj_id),
            stream='reply_to/{}'.format(obj_id))

    def _like(self, obj_id, endpoint, method):
        """Used for liking or unliking an object."""
        token = self._get_access_token()
        url = self._api_base.format(endpoint=endpoint, token=token)

        if not Downloader(
                url,
                method=method,
                params=dict(access_token=token)).get_json():
            raise FriendsError(
                'Failed to {} like {} on Instagram'.format(
                    method, obj_id))

    @feature
    def like(self, obj_id):
        endpoint = 'media/{}/likes'.format(obj_id)
        self._like(obj_id, endpoint, 'POST')
        self._inc_cell(obj_id, 'likes')
        self._set_cell(obj_id, 'liked', True)
        return obj_id

    @feature
    def unlike(self, obj_id):
        endpoint = 'media/{}/likes'.format(obj_id)
        self._like(obj_id, endpoint, 'DELETE')
        self._dec_cell(obj_id, 'likes')
        self._set_cell(obj_id, 'liked', False)
        return obj_id
