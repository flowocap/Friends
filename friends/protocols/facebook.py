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


import logging

from datetime import datetime, timedelta

from friends.utils.base import Base, feature
from friends.utils.download import get_json
from friends.utils.time import parsetime, iso8601utc


# 'id' can be the id of *any* Facebook object
# https://developers.facebook.com/docs/reference/api/
URL_BASE = 'https://{subdomain}.facebook.com/'
PERMALINK = URL_BASE.format(subdomain='www') + '{id}'
API_BASE = URL_BASE.format(subdomain='graph') + '{id}'
ME_URL = API_BASE.format(id='me')


log = logging.getLogger('friends.service')


class Facebook(Base):
    def _whoami(self, authdata):
        """Identify the authenticating user."""
        me_data = get_json(
            ME_URL, dict(access_token=self._account.access_token))
        self._account.user_id = me_data.get('id')
        self._account.user_name = me_data.get('name')

    def _is_error(self, data):
        """Is the return data an error response?"""
        error = data.get('error')
        if error is None:
            return False
        log.error('Facebook error ({} {}): {}'.format(
            error.get('code'), error.get('type'), error.get('message')))
        return True

    def _publish_entry(self, entry):
        message_id = entry.get('id')
        if message_id is None:
            # We can't do much with this entry.
            return

        args = dict(
            stream='messages',
            message=entry.get('message', ''),
            url=PERMALINK.format(id=message_id),
            icon_uri=entry.get('icon', ''),
            link_picture=entry.get('picture', ''),
            link_name=entry.get('name', ''),
            link_url=entry.get('link', ''),
            link_desc=entry.get('description', ''),
            link_caption=entry.get('caption', ''),
            )
        from_record = entry.get('from')
        if from_record is not None:
            args['sender'] = sender_id = from_record.get('id', '')
            args['sender_nick'] = from_record.get('name', '')
            args['from_me'] = (sender_id == self._account.user_id)
        # Normalize the timestamp.
        timestamp = entry.get('updated_time', entry.get('created_time'))
        if timestamp is not None:
            args['timestamp'] = iso8601utc(parsetime(timestamp))
        like_count = entry.get('likes', {}).get('count')
        if like_count is not None:
            args['likes'] = like_count
            args['liked'] = (like_count > 0)
        # Parse comments now.
        all_comments = []
        for comment_data in entry.get('comments', {}).get('data', []):
            comment_message = comment_data.get('message')
            if comment_message is not None:
                all_comments.append(comment_message)
        args['comments'] = all_comments
        self._publish(message_id, **args)

    @feature
    def receive(self, since=None):
        """Retrieve a list of Facebook objects.

        A maximum of 100 objects are requested.

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
        url = ME_URL + '/home'
        params = dict(access_token=access_token,
                      since=when.isoformat(),
                      limit=self._DOWNLOAD_LIMIT)
        # Now access Facebook and follow pagination until we have at least
        # _DOWNLOAD_LIMIT number of entries, or we've reached the end of pages.
        while True:
            response = get_json(url, params)
            if self._is_error(response):
                # We'll just use what we have so far, if anything.
                break
            data = response.get('data')
            if data is None:
                # I guess we're done.
                break
            entries.extend(data)
            if len(entries) >= self._DOWNLOAD_LIMIT:
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
                # I guess there are no more next pages.
                break
        # We've gotten everything Facebook is going to give us.  Now, decipher
        # the data and publish it.
        # https://developers.facebook.com/docs/reference/api/post/
        for entry in entries:
            self._publish_entry(entry)

    def _like(self, obj_id, method):
        url = API_BASE.format(id=obj_id) + '/likes'
        token = self._get_access_token()

        if not get_json(url, method=method, params=dict(access_token=token)):
            log.error('Failed to {} like {} on Facebook'.format(
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

        result = get_json(
            url,
            method='POST',
            params=dict(access_token=token, message=message))
        new_id = result.get('id')
        if new_id is None:
            log.error('Failed sending to Facebook: {!r}'.format(result))
            return

        url = API_BASE.format(id=new_id)
        entry = get_json(url, params=dict(access_token=token))
        self._publish_entry(entry)

    @feature
    def send(self, message, obj_id='me'):
        """Write a message on somebody or something's wall.

        If you don't specify an obj_id, it defaults to your wall.  obj_id can
        be any type of Facebook object that has a wall, be it a user, an app,
        a company, an event, etc.
        """
        self._send(obj_id, message, '/feed')

    @feature
    def send_thread(self, obj_id, message):
        """Write a comment on some existing status message.

        obj_id can be the id of any Facebook object that supports being
        commented on, which will generally be Posts.
        """
        self._send(obj_id, message, '/comments')

    @feature
    def delete(self, obj_id):
        """Delete any Facebook object that you are the owner of."""
        url = API_BASE.format(id=obj_id)
        token = self._get_access_token()

        if not get_json(url, method='DELETE', params=dict(access_token=token)):
            log.error('Failed to delete {} on Facebook'.format(obj_id))
        else:
            self._unpublish(obj_id)
