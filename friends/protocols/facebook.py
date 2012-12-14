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

"""The Facebook protocol plugin."""


__all__ = [
    'Facebook',
    ]


import time
import logging

from datetime import datetime, timedelta

from friends.utils.avatar import Avatar
from friends.utils.base import Base, feature
from friends.utils.http import Downloader, Uploader
from friends.utils.time import parsetime, iso8601utc
from friends.errors import FriendsError


# 'id' can be the id of *any* Facebook object
# https://developers.facebook.com/docs/reference/api/
URL_BASE = 'https://{subdomain}.facebook.com/'
PERMALINK = URL_BASE.format(subdomain='www') + '{id}'
API_BASE = URL_BASE.format(subdomain='graph') + '{id}'
ME_URL = API_BASE.format(id='me')
FACEBOOK_ADDRESS_BOOK = 'friends-facebook-contacts'


log = logging.getLogger(__name__)


class Facebook(Base):
    def _whoami(self, authdata):
        """Identify the authenticating user."""
        me_data = Downloader(
            ME_URL, dict(access_token=self._account.access_token)).get_json()
        self._account.user_id = me_data.get('id')
        self._account.user_name = me_data.get('name')

    def _is_error(self, data):
        """Is the return data an error response?"""
        error = data.get('error')
        if error is None:
            return False
        raise FriendsError('Facebook error ({} {}): {}'.format(
            error.get('code'), error.get('type'), error.get('message')))

    def _publish_entry(self, entry, stream='messages'):
        message_id = entry.get('id')
        if message_id is None:
            # We can't do much with this entry.
            return

        args = dict(
            stream=stream,
            message=entry.get('message', ''),
            url=PERMALINK.format(id=message_id),
            icon_uri=entry.get('icon', ''),
            link_picture=entry.get('picture', ''),
            link_name=entry.get('name', ''),
            link_url=entry.get('link', ''),
            link_desc=entry.get('description', ''),
            link_caption=entry.get('caption', ''),
            )

        # Posts gives us a likes dict, while replies give us an int.
        likes = entry.get('likes', 0)
        if isinstance(likes, dict):
            likes = likes.get('count', 0)
        args['likes'] = likes

        from_record = entry.get('from')
        if from_record is not None:
            args['sender'] = from_record.get('name', '')
            args['sender_id'] = sender_id = from_record.get('id', '')
            args['icon_uri'] = Avatar.get_image(
                API_BASE.format(id=sender_id) + '/picture?type=large')
            args['sender_nick'] = from_record.get('name', '')
            args['from_me'] = (sender_id == self._account.user_id)

        # Normalize the timestamp.
        timestamp = entry.get('updated_time', entry.get('created_time'))
        if timestamp is not None:
            args['timestamp'] = iso8601utc(parsetime(timestamp))

        # Publish this message into the SharedModel.
        self._publish(message_id, **args)

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

    def _get(self, url, stream, since=None):
        """Retrieve a list of Facebook objects.

        A maximum of 50 objects are requested.

        :param since: Only get objects posted since this date.  If not given,
            then only objects younger than 10 days are retrieved.  The value
            is a number seconds since the epoch.
        :type since: float
        """
        access_token = self._get_access_token()
        if since is None:
            when = datetime.now() - timedelta(days=10)
        else:
            when = datetime.fromtimestamp(since)
        entries = []
        params = dict(access_token=access_token,
                      since=when.isoformat(),
                      limit=self._DOWNLOAD_LIMIT)

        entries = self._follow_pagination(url, params)
        # https://developers.facebook.com/docs/reference/api/post/
        for entry in entries:
            self._publish_entry(entry, stream=stream)

    @feature
    def home(self, since=None):
        """Gather and publish public timeline messages."""
        self._get(ME_URL + '/home', 'messages', since)

    @feature
    def wall(self, since=None):
        """Gather and publish messages written on user's wall."""
        self._get(ME_URL + '/feed', 'mentions', since)

    @feature
    def receive(self):
        self.wall()
        self.home()

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

    @feature
    def unlike(self, obj_id):
        """Unlike any arbitrary object on Facebook.

        This includes messages, statuses, wall posts, events, etc.
        """
        self._like(obj_id, 'DELETE')

    def _send(self, obj_id, message, endpoint):
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
        return self._publish_entry(entry)

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
        return self._send(obj_id, message, '/comments')

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

    @feature
    def upload(self, picture_uri, description=''):
        # http://developers.facebook.com/docs/reference/api/photo/
        """Upload local or remote image or video to album."""
        url = '{}/photos?access_token={}'.format(
            ME_URL, self._get_access_token())
        response = Uploader(
            url, picture_uri, description,
            picture_key='source', desc_key='message').get_json()
        if response is None:
            raise FriendsError('No response from upload server.')
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
                icon_uri=Avatar.get_image(
                    API_BASE.format(id=self._account.user_id) +
                    '/picture?type=large'))
            return destination_url
        else:
            raise FriendsError(str(response))

    def _fetch_contacts(self):
        """Retrieve a list of up to 1,000 Facebook friends."""
        limit = 1000
        access_token = self._get_access_token()
        url = ME_URL + '/friends'
        params = dict(
            access_token=access_token,
            limit=limit)
        return self._follow_pagination(url, params, limit)

    def _fetch_contact(self, contact_id):
        """Fetch the full, individual contact info."""
        access_token = self._get_access_token()
        url = API_BASE.format(id=contact_id)
        params = dict(access_token=access_token)
        return Downloader(url, params).get_json()

    def _create_contact(self, contact_json):
        """Build a VCard based on a dict representation of a contact."""

        user_id = contact_json.get('id')
        user_fullname = contact_json.get('name')
        user_nickname = contact_json.get('username')
        user_link = contact_json.get('link')
        gender = contact_json.get('gender')

        attrs = {}
        attrs['facebook-id'] = user_id
        attrs['facebook-name'] = user_fullname
        attrs['X-URIS'] = user_link
        attrs['X-FOLKS-WEB-SERVICES-IDS'] = {
            'jabber':'-{}@chat.facebook.com'.format(user_id),
            'remote-full-name':user_fullname,
            'facebook-id': user_id}
        if gender is not None:
            attrs['X-GENDER'] = gender

        contact = Base._create_contact(
            self, user_fullname, user_nickname, attrs)

        return contact

    @feature
    def contacts(self):
        contacts = self._fetch_contacts()
        log.debug('Size of the contacts returned {}'.format(len(contacts)))
        source = self._get_eds_source(FACEBOOK_ADDRESS_BOOK)
        if source is None:
            source = self._create_eds_source(FACEBOOK_ADDRESS_BOOK)

        for contact in contacts:
            if self._previously_stored_contact(
                    source, 'facebook-id', contact['id']):
                continue
            log.debug(
                'Fetch full contact info for {} and id {}'.format(
                    contact['name'], contact['id']))
            full_contact = self._fetch_contact(contact['id'])
            eds_contact = self._create_contact(full_contact)
            self._push_to_eds(FACEBOOK_ADDRESS_BOOK, eds_contact)

    def delete_contacts(self):
        source = self._get_eds_source(FACEBOOK_ADDRESS_BOOK)
        return self._delete_service_contacts(source)
