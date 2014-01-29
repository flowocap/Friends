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

"""The Facebook protocol plugin."""


__all__ = [
    'Facebook',
    ]


import time
import logging

from friends.utils.base import Base, feature
from friends.utils.cache import JsonCache
from friends.utils.http import Downloader, Uploader
from friends.utils.time import parsetime, iso8601utc
from friends.errors import FriendsError


# 'id' can be the id of *any* Facebook object
# https://developers.facebook.com/docs/reference/api/
URL_BASE = 'https://{subdomain}.facebook.com/'
PERMALINK = URL_BASE.format(subdomain='www') + '{id}'
API_BASE = URL_BASE.format(subdomain='graph') + '{id}'
ME_URL = API_BASE.format(id='me')
STORY_PERMALINK = PERMALINK + '/posts/{post_id}'


TEN_DAYS = 864000 # seconds


log = logging.getLogger(__name__)


class Facebook(Base):
    def __init__(self, account):
        super().__init__(account)
        self._timestamps = PostIdCache(self._name + '_ids')

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        me_data = Downloader(
            ME_URL, dict(access_token=self._account.access_token)).get_json()
        self._account.user_id = me_data.get('id')
        self._account.user_name = me_data.get('name')

    def _publish_entry(self, entry, stream='messages'):
        message_id = entry.get('id')
        message_type = entry.get('type')

        if "reply" in stream:
            message_type = "reply"

        if None in (message_id, message_type):
            # We can't do much with this entry.
            return

        if 'to' in entry:
            # Somebody posted on somebodies wall
            # This cannot be displayed properly in friends so ignore
            return

        place = entry.get('place', {})
        location = place.get('location', {})

        link_pic = entry.get('picture', '')

        # Use objectID to get a highres version of the picture
        # Does not seem to work for links
        object_id = entry.get('object_id')
        if object_id and ('photo' in message_type):
            link_pic = "http://graph.facebook.com/" + object_id + "/picture?type=normal"

        args = dict(
            message_id=message_id,
            stream='images' if ('photo' in message_type) else stream,
            message=entry.get('message', '') or entry.get('story', ''),
            icon_uri=entry.get('icon', ''),
            link_picture=link_pic,
            link_name=entry.get('name', ''),
            link_url=entry.get('link', ''),
            link_desc=entry.get('description', ''),
            link_caption=entry.get('caption', ''),
            location=place.get('name', ''),
            latitude=location.get('latitude', 0.0),
            longitude=location.get('longitude', 0.0),
            )

        # Posts gives us a likes dict, while replies give us an int.
        likes = entry.get('likes', 0)
        if isinstance(likes, dict):
            likes = likes.get('count', 0)
        args['likes'] = likes

        # Fix for LP:1185684 - JPM
        post_id = message_id.split('_')[1] if '_' in message_id else message_id

        from_record = entry.get('from')
        if from_record is not None:
            args['sender'] = from_record.get('name', '')
            args['sender_id'] = sender_id = from_record.get('id', '')
            args['url'] = STORY_PERMALINK.format(
                id=sender_id, post_id=post_id)
            args['icon_uri'] = (API_BASE.format(id=sender_id) +
                                '/picture?width=840&height=840')
            args['sender_nick'] = from_record.get('name', '')
            args['from_me'] = (sender_id == self._account.user_id)

        # Normalize the timestamp.
        timestamp = entry.get('updated_time', entry.get('created_time'))
        if timestamp is not None:
            timestamp = args['timestamp'] = iso8601utc(parsetime(timestamp))
            # We need to record timestamps for use with since=. Note that
            # _timestamps is a special dict subclass that only accepts
            # timestamps that are larger than the existing value, so at any
            # given time it will map the stream to the most
            # recent timestamp we've seen for that stream.
            self._timestamps[stream] = timestamp

        # Publish this message into the SharedModel.
        self._publish(**args)

        # If there are any replies, publish them as well.
        for comment in entry.get('comments', {}).get('data', []):
            if comment:
                self._publish_entry(
                    stream='reply_to/{}'.format(message_id),
                    entry=comment)
        return args['url']

    def _follow_pagination(self, url, params, limit=None):
        """Follow Facebook's pagination until we hit the limit."""
        limit = limit or self._DOWNLOAD_LIMIT
        entries = []

        while True:
            response = Downloader(url, params).get_json()

            if self._is_error(response):
                break

            data = response.get('data')
            if data is None:
                break

            entries.extend(data)
            if len(entries) >= limit:
                break

            # We haven't gotten the requested number of entries.  Follow the
            # next page if there is one to try to get more.
            pages = response.get('paging')
            if pages is None:
                break

            # The 'next' key has the full link to follow; no additional
            # parameters are needed.  Specifically, this link will already
            # include the access_token, and any since/limit values.
            url = pages.get('next')
            params = None
            if url is None:
                break

        # We've gotten everything Facebook is going to give us.
        return entries

    def _get(self, url, stream):
        """Retrieve a list of Facebook objects.

        A maximum of 50 objects are requested.
        """
        access_token = self._get_access_token()
        since = self._timestamps.get(
            stream, iso8601utc(int(time.time()) - TEN_DAYS))

        entries = []
        params = dict(access_token=access_token,
                      since=since,
                      limit=self._DOWNLOAD_LIMIT)

        entries = self._follow_pagination(url, params)
        # https://developers.facebook.com/docs/reference/api/post/
        for entry in entries:
            self._publish_entry(entry, stream=stream)

    @feature
    def home(self):
        """Gather and publish public timeline messages."""
        self._get(ME_URL + '/home', 'messages')
        return self._get_n_rows()

    @feature
    def wall(self):
        """Gather and publish messages written on user's wall."""
        self._get(ME_URL + '/feed', 'mentions')
        return self._get_n_rows()

    @feature
    def receive(self):
        self.wall()
        self.home()
        return self._get_n_rows()

    @feature
    def search(self, query):
        """Search for up to 50 items matching query."""
        access_token = self._get_access_token()
        entries = []
        url = API_BASE.format(id='search')
        params = dict(
            access_token=access_token,
            q=query)

        entries = self._follow_pagination(url, params)
        # https://developers.facebook.com/docs/reference/api/post/
        for entry in entries:
            self._publish_entry(entry, 'search/{}'.format(query))
        return len(entries)

    def _like(self, obj_id, method):
        url = API_BASE.format(id=obj_id) + '/likes'
        token = self._get_access_token()

        if not Downloader(url, method=method,
                          params=dict(access_token=token)).get_json():
            raise FriendsError('Failed to {} like {} on Facebook'.format(
                method, obj_id))

    @feature
    def like(self, obj_id):
        """Like any arbitrary object on Facebook.

        This includes messages, statuses, wall posts, events, etc.
        """
        self._like(obj_id, 'POST')
        self._inc_cell(obj_id, 'likes')
        self._set_cell(obj_id, 'liked', True)
        return obj_id

    @feature
    def unlike(self, obj_id):
        """Unlike any arbitrary object on Facebook.

        This includes messages, statuses, wall posts, events, etc.
        """
        self._like(obj_id, 'DELETE')
        self._dec_cell(obj_id, 'likes')
        self._set_cell(obj_id, 'liked', False)
        return obj_id

    def _send(self, obj_id, message, endpoint, stream='messages'):
        url = API_BASE.format(id=obj_id) + endpoint
        token = self._get_access_token()

        result = Downloader(
            url,
            method='POST',
            params=dict(access_token=token, message=message)).get_json()
        new_id = result.get('id')
        if new_id is None:
            raise FriendsError('Failed sending to Facebook: {!r}'.format(result))

        url = API_BASE.format(id=new_id)
        entry = Downloader(url, params=dict(access_token=token)).get_json()
        return self._publish_entry(
            stream=stream,
            entry=entry)

    @feature
    def send(self, message, obj_id='me'):
        """Write a message on somebody or something's wall.

        If you don't specify an obj_id, it defaults to your wall.  obj_id can
        be any type of Facebook object that has a wall, be it a user, an app,
        a company, an event, etc.
        """
        return self._send(obj_id, message, '/feed')

    @feature
    def send_thread(self, obj_id, message):
        """Write a comment on some existing status message.

        obj_id can be the id of any Facebook object that supports being
        commented on, which will generally be Posts.
        """
        return self._send(obj_id, message, '/comments',
                          stream='reply_to/{}'.format(obj_id))

    @feature
    def delete(self, obj_id):
        """Delete any Facebook object that you are the owner of."""
        url = API_BASE.format(id=obj_id)
        token = self._get_access_token()

        if not Downloader(url, method='DELETE',
                          params=dict(access_token=token)).get_json():
            raise FriendsError('Failed to delete {} on Facebook'.format(obj_id))
        else:
            self._unpublish(obj_id)

        return obj_id

    @feature
    def upload(self, picture_uri, description=''):
        # http://developers.facebook.com/docs/reference/api/photo/
        """Upload local or remote image or video to album."""
        url = '{}/photos?access_token={}'.format(
            ME_URL, self._get_access_token())
        response = Uploader(
            url, picture_uri, description,
            picture_key='source', desc_key='message').get_json()
        self._is_error(response)

        post_id = response.get('post_id')
        if post_id is not None:
            destination_url = PERMALINK.format(id=post_id)
            self._publish(
                from_me=True,
                stream='images',
                message_id=post_id,
                message=description,
                sender=self._account.user_name,
                sender_id=self._account.user_id,
                sender_nick=self._account.user_name,
                timestamp=iso8601utc(int(time.time())),
                url=destination_url,
                icon_uri=(API_BASE.format(id=self._account.user_id) +
                          '/picture?type=large'))
            return destination_url
        else:
            raise FriendsError(str(response))

    @feature
    def contacts(self):
        access_token=self._get_access_token()
        contacts = self._follow_pagination(
            url=ME_URL + '/friends',
            params=dict(access_token=access_token, limit=1000),
            limit=1000)
        log.debug('Found {} contacts'.format(len(contacts)))

        for contact in contacts:
            contact_id = contact.get('id')
            if not self._previously_stored_contact(contact_id):
                full_contact = Downloader(
                    url=API_BASE.format(id=contact_id),
                    params=dict(access_token=access_token)).get_json()
                self._push_to_eds(
                    uid=contact_id,
                    name=full_contact.get('name'),
                    nick=full_contact.get('username'),
                    link=full_contact.get('link'),
                    gender=full_contact.get('gender'),
                    jabber='-{}@chat.facebook.com'.format(contact_id))

        return len(contacts)


class PostIdCache(JsonCache):
    """Persist most-recent timestamps as JSON."""

    def __setitem__(self, key, value):
        if key.find('/') >= 0:
            # Don't flood the cache with irrelevant "reply_to/..." and
            # "search/..." streams, we only need the main streams.
            return
        # Thank SCIENCE for lexically-sortable timestamp strings!
        if value > self.get(key, ''):
            JsonCache.__setitem__(self, key, value)
