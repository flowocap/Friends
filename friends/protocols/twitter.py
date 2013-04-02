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

"""The Twitter protocol plugin."""


__all__ = [
    'RateLimiter',
    'Twitter',
    ]


import time
import logging

from urllib.parse import quote

from friends.utils.avatar import Avatar
from friends.utils.base import Base, feature
from friends.utils.cache import JsonCache
from friends.utils.http import BaseRateLimiter, Downloader
from friends.utils.time import parsetime, iso8601utc
from friends.errors import FriendsError


TWITTER_ADDRESS_BOOK = 'friends-twitter-contacts'


log = logging.getLogger(__name__)


# https://dev.twitter.com/docs/api/1.1
class Twitter(Base):
    # Identi.ca's API mimicks Twitter's to such a high degree that it
    # is implemented just as a subclass of this, hence we need these
    # constants defined as instance attributes, so that the Identica
    # class can override them. If you make any changes to this class
    # you must confirm that your changes do not break Identi.ca!
    _api_base = 'https://api.twitter.com/1.1/{endpoint}.json'

    _timeline = _api_base.format(endpoint='statuses/{}_timeline')
    _user_timeline = _timeline.format('user') + '?screen_name={}'
    _mentions_timeline = _timeline.format('mentions')

    _lists = _api_base.format(endpoint='lists/statuses') + '?list_id={}'

    _destroy = _api_base.format(endpoint='statuses/destroy/{}')
    _retweet = _api_base.format(endpoint='statuses/retweet/{}')

    _search = _api_base.format(endpoint='search/tweets')
    _search_result_key = 'statuses'

    _tweet_permalink = 'https://twitter.com/{user_id}/status/{tweet_id}'

    def __init__(self, account):
        super().__init__(account)
        self._rate_limiter = RateLimiter()
        # Can be 'twitter_ids' or 'identica_ids'
        self._tweet_ids = TweetIdCache(self._name + '_ids')

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        self._account.secret_token = authdata.get('TokenSecret')
        self._account.user_id = authdata.get('UserId')
        self._account.user_name = authdata.get('ScreenName')

    def _get_url(self, url, data=None):
        """Access the Twitter API with correct OAuth signed headers."""
        do_post = data is not None
        method = 'POST' if do_post else 'GET'

        headers = self._get_oauth_headers(
            method=method,
            url=url,
            data=data,
            )

        response = Downloader(
            url, params=data, headers=headers, method=method,
            rate_limiter=self._rate_limiter).get_json()
        self._is_error(response)
        return response

    def _publish_tweet(self, tweet, stream='messages'):
        """Publish a single tweet into the Dee.SharedModel."""
        tweet_id = tweet.get('id_str') or str(tweet.get('id', ''))
        if not tweet_id:
            log.info('Ignoring tweet with no id_str value')
            return

        # We need to record tweet_ids for use with since_id. Note that
        # _tweet_ids is a special dict subclass that only accepts
        # tweet_ids that are larger than the existing value, so at any
        # given time it will map the stream to the largest (most
        # recent) tweet_id we've seen for that stream.
        self._tweet_ids[stream] = tweet_id

        # 'user' for tweets, 'sender' for direct messages.
        user = tweet.get('user', {}) or tweet.get('sender', {})
        screen_name = user.get('screen_name', '')
        avatar_url = (user.get('profile_image_url_https') or # Twitter, or
                      user.get('profile_image_url') or       # Identi.ca
                      '')

        permalink = self._tweet_permalink.format(
            user_id=screen_name,
            tweet_id=tweet_id)
        self._publish(
            message_id=tweet_id,
            message=tweet.get('text', ''),
            timestamp=iso8601utc(parsetime(tweet.get('created_at', ''))),
            stream=stream,
            sender=user.get('name', ''),
            sender_id=str(user.get('id', '')),
            sender_nick=screen_name,
            from_me=(screen_name == self._account.user_name),
            icon_uri=Avatar.get_image(
                avatar_url.replace('_normal.', '.')),
            liked=tweet.get('favorited', False),
            url=permalink,
            )
        return permalink

    def _append_since(self, url, stream='messages'):
        since = self._tweet_ids.get(stream)
        if since is not None:
            return '{}&since_id={}'.format(url, since)
        return url

# https://dev.twitter.com/docs/api/1.1/get/statuses/home_timeline
    @feature
    def home(self):
        """Gather the user's home timeline."""
        url = '{}?count={}'.format(
            self._timeline.format('home'),
            self._DOWNLOAD_LIMIT)
        url = self._append_since(url)
        for tweet in self._get_url(url):
            self._publish_tweet(tweet)
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/statuses/mentions_timeline
    @feature
    def mentions(self):
        """Gather the tweets that mention us."""
        url = '{}?count={}'.format(
            self._mentions_timeline,
            self._DOWNLOAD_LIMIT)
        url = self._append_since(url, 'mentions')
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream='mentions')
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/statuses/user_timeline
    @feature
    def user(self, screen_name=''):
        """Gather the tweets from a specific user.

        If screen_name is not specified, then gather the tweets written by the
        currently authenticated user.
        """
        url = self._user_timeline.format(screen_name)
        stream = 'user/{}'.format(screen_name) if screen_name else 'messages'
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream=stream)
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/lists/statuses
    @feature
    def list(self, list_id):
        """Gather the tweets from the specified list_id."""
        url = self._lists.format(list_id)
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream='list/{}'.format(list_id))
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/lists/list
    @feature
    def lists(self):
        """Gather the tweets from the lists that the we are subscribed to."""
        url = self._api_base.format(endpoint='lists/list')
        for twitlist in self._get_url(url):
            self.list(twitlist.get('id_str', ''))
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/direct_messages
# https://dev.twitter.com/docs/api/1.1/get/direct_messages/sent
    @feature
    def private(self):
        """Gather the direct messages sent to/from us."""
        url = '{}?count={}'.format(
            self._api_base.format(endpoint='direct_messages'),
            self._DOWNLOAD_LIMIT)
        url = self._append_since(url, 'private')
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream='private')

        url = '{}?count={}'.format(
            self._api_base.format(endpoint='direct_messages/sent'),
            self._DOWNLOAD_LIMIT)
        url = self._append_since(url, 'private')
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream='private')
        return self._get_n_rows()

    @feature
    def receive(self):
        """Gather and publish all incoming messages."""
        self.home()
        self.mentions()
        self.private()
        return self._get_n_rows()

    @feature
    def send_private(self, screen_name, message):
        """Send a direct message to the given screen name.

        This will error 403 if the person you are sending to does not follow
        you.
        """
        url = self._api_base.format(endpoint='direct_messages/new')
        tweet = self._get_url(
            url, dict(text=message, screen_name=screen_name))
        return self._publish_tweet(tweet, stream='private')

# https://dev.twitter.com/docs/api/1.1/post/statuses/update
    @feature
    def send(self, message):
        """Publish a public tweet."""
        url = self._api_base.format(endpoint='statuses/update')
        tweet = self._get_url(url, dict(status=message))
        return self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/post/statuses/update
    @feature
    def send_thread(self, message_id, message):
        """Send a reply message to message_id.

        This method takes care to prepend the @mention to the start of
        your tweet if you forgot it. Without this, Twitter will just
        consider it a regular message, and it won't be part of any
        conversation.
        """
        try:
            sender = '@{}'.format(self._fetch_cell(message_id, 'sender_nick'))
            if message.find(sender) < 0:
                message = sender + ' ' + message
        except FriendsError:
            pass
        url = self._api_base.format(endpoint='statuses/update')
        tweet = self._get_url(url, dict(in_reply_to_status_id=message_id,
                                        status=message))
        return self._publish_tweet(
            tweet, stream='reply_to/{}'.format(message_id))

# https://dev.twitter.com/docs/api/1.1/post/statuses/destroy/%3Aid
    @feature
    def delete(self, message_id):
        """Delete a tweet that you wrote."""
        url = self._destroy.format(message_id)
        # We can ignore the return value.
        self._get_url(url, dict(trim_user='true'))
        self._unpublish(message_id)
        return message_id

# https://dev.twitter.com/docs/api/1.1/post/statuses/retweet/%3Aid
    @feature
    def retweet(self, message_id):
        """Republish somebody else's tweet with your name on it."""
        url = self._retweet.format(message_id)
        tweet = self._get_url(url, dict(trim_user='true'))
        return self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/post/friendships/destroy
    @feature
    def unfollow(self, screen_name):
        """Stop following the given screen name."""
        url = self._api_base.format(endpoint='friendships/destroy')
        self._get_url(url, dict(screen_name=screen_name))
        return screen_name

# https://dev.twitter.com/docs/api/1.1/post/friendships/create
    @feature
    def follow(self, screen_name):
        """Start following the given screen name."""
        url = self._api_base.format(endpoint='friendships/create')
        self._get_url(url, dict(screen_name=screen_name, follow='true'))
        return screen_name

# https://dev.twitter.com/docs/api/1.1/post/favorites/create
    @feature
    def like(self, message_id):
        """Announce to the world your undying love for a tweet."""
        url = self._api_base.format(endpoint='favorites/create')
        self._get_url(url, dict(id=message_id))
        self._inc_cell(message_id, 'likes')
        self._set_cell(message_id, 'liked', True)
        return message_id

# https://dev.twitter.com/docs/api/1.1/post/favorites/destroy
    @feature
    def unlike(self, message_id):
        """Renounce your undying love for a tweet."""
        url = self._api_base.format(endpoint='favorites/destroy')
        self._get_url(url, dict(id=message_id))
        self._dec_cell(message_id, 'likes')
        self._set_cell(message_id, 'liked', False)
        return message_id

# https://dev.twitter.com/docs/api/1.1/get/search/tweets
    @feature
    def tag(self, hashtag):
        """Return a list of some recent tweets mentioning hashtag."""
        self.search('#' + hashtag.lstrip('#'))
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/search/tweets
    @feature
    def search(self, query):
        """Search for any arbitrary string."""
        url = self._search

        response = self._get_url('{}?q={}'.format(url, quote(query, safe='')))
        for tweet in response.get(self._search_result_key, []):
            self._publish_tweet(tweet, stream='search/{}'.format(query))
        return self._get_n_rows()

# https://dev.twitter.com/docs/api/1.1/get/friends/ids
    def _getfriendsids(self):
        """Get a list of the twitter id's of our twitter friends."""
        url = self._api_base.format(endpoint="friends/ids")
        response = self._get_url(url)

        try:
            # Twitter
            return response["ids"]
        except TypeError:
            # Identica
            return response

# https://dev.twitter.com/docs/api/1.1/get/users/show
    def _showuser(self, uid):
        """Get all the information about a twitter user."""
        url = self._api_base.format(endpoint="users/show") + "?user_id={}".format(uid)
        return self._get_url(url)

    def _create_contact(self, userdata):
        """Build a VCard based on a dict representation of a contact."""

        if userdata.get('error'):
            raise FriendsError(userdata)

        user_fullname = userdata['name']
        user_nickname = userdata['screen_name']

        attrs = {}
        attrs['twitter-id'] = str(userdata['id'])
        attrs['twitter-name'] = user_fullname
        attrs['X-URIS'] = 'https://twitter.com/{}'.format(user_nickname)
        attrs['X-FOLKS-WEB-SERVICES-IDS'] = {
            'remote-full-name': user_fullname,
            'twitter-id': str(userdata['id']),
            }

        contact = Base._create_contact(
            self, user_fullname, user_nickname, attrs)

        return contact

    @feature
    def contacts(self):
        contacts = self._getfriendsids()
        log.debug('Size of the contacts returned {}'.format(len(contacts)))
        source = self._get_eds_source(TWITTER_ADDRESS_BOOK)
        if source is None:
            source = self._create_eds_source(TWITTER_ADDRESS_BOOK)

        for contact in contacts:
            twitterid = str(contact)
            if self._previously_stored_contact(source, 'twitter-id', twitterid):
                continue
            full_contact = self._showuser(twitterid)
            try:
                eds_contact = self._create_contact(full_contact)
            except FriendsError:
                continue
            self._push_to_eds(TWITTER_ADDRESS_BOOK, eds_contact)
        return len(contacts)

    def delete_contacts(self):
        source = self._get_eds_source(TWITTER_ADDRESS_BOOK)
        return self._delete_service_contacts(source)


class TweetIdCache(JsonCache):
    """Persist most-recent tweet_ids as JSON."""

    def __setitem__(self, key, value):
        if key.find('/') >= 0:
            # Don't flood the cache with irrelevant "reply_to/..." and
            # "search/..." streams, we only need the main streams.
            return
        value = int(value)
        if value > self.get(key, 0):
            JsonCache.__setitem__(self, key, value)


class RateLimiter(BaseRateLimiter):
    """Twitter rate limiter."""

    def __init__(self):
        self._limits = JsonCache('twitter-ratelimiter')

    def _sanitize_url(self, uri):
        # Cache the URL sans any query parameters.
        return uri.host + uri.path

    def wait(self, message):
        # If we haven't seen this URL, default to no wait.
        seconds = self._limits.pop(self._sanitize_url(message.get_uri()), 0)
        log.debug('Sleeping for {} seconds!'.format(seconds))
        time.sleep(seconds)
        # Don't sleep the same length of time more than once!
        self._limits.write()

    def update(self, message):
        info = message.response_headers
        url = self._sanitize_url(message.get_uri())
        # This is time in the future, in UTC epoch seconds, at which the
        # current rate limiting window expires.
        rate_reset = info.get('X-Rate-Limit-Reset')
        # This is the number of calls still allowed in this window.
        rate_count = info.get('X-Rate-Limit-Remaining')
        if None not in (rate_reset, rate_count):
            rate_reset = int(rate_reset)
            rate_count = int(rate_count)
            rate_delta = abs(rate_reset - time.time())
            if rate_count > 5:
                # If there are more than 5 calls allowed in this window, then
                # do no rate limiting.
                pass
            elif rate_count < 1:
                # There are no calls remaining, so wait until the close of the
                # current window.
                self._limits[url] = rate_delta
            else:
                wait_secs = rate_delta / rate_count
                self._limits[url] = wait_secs
            log.debug(
                'Next access to {} must wait {} seconds!'.format(
                    url, self._limits.get(url, 0)))
