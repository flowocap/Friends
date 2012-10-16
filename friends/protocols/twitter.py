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

"""The Twitter protocol plugin."""


__all__ = [
    'RateLimiter',
    'Twitter',
    ]


import time
import logging

from oauthlib.oauth1 import Client
from urllib.error import HTTPError
from urllib.parse import quote

from friends.utils.base import Base, feature
from friends.utils.download import RateLimiter as BaseRateLimiter, get_json
from friends.utils.time import parsetime, iso8601utc


log = logging.getLogger('friends.service')


# https://dev.twitter.com/docs/api/1.1
class Twitter(Base):
    # StatusNet claims to mimick the Twitter API very closely (so closely to
    # the point that they refer you to the Twitter API reference docs as a
    # starting point for learning about their API).  So these prefixes are
    # defined here as class attributes instead of the usual module globals, in
    # the hopes that the StatusNet class will be able to subclass Twitter and
    # change only the URLs, with minimal other changes, and magically work.
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

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        self._account.secret_token = authdata.get('TokenSecret')
        self._account.user_id = authdata.get('UserId')
        self._account.user_name = authdata.get('ScreenName')

    def _get_url(self, url, data=None):
        """Access the Twitter API with correct OAuth signed headers."""
        do_post = data is not None
        method = 'POST' if do_post else 'GET'

        # "Client" == "Consumer" in oauthlib parlance.
        client_key = self._account.auth.parameters['ConsumerKey']
        client_secret = self._account.auth.parameters['ConsumerSecret']

        # "resource_owner" == secret and token.
        resource_owner_key = self._get_access_token()
        resource_owner_secret = self._account.secret_token
        oauth_client = Client(client_key, client_secret,
                              resource_owner_key, resource_owner_secret)

        headers = {}
        if do_post:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        # All we care about is the headers, which will contain the
        # Authorization header necessary to satisfy OAuth.
        uri, headers, body = oauth_client.sign(
            url, body=data, headers=headers, http_method=method)

        return get_json(url, params=data, headers=headers, method=method,
                        rate_limiter=self._rate_limiter)

    def _publish_tweet(self, tweet, stream='messages'):
        """Publish a single tweet into the Dee.SharedModel."""
        tweet_id = tweet.get('id_str')
        if tweet_id is None:
            log.info('Ignoring tweet with no id_str value')
            return

        user = tweet.get('user', {})
        screen_name = user.get('screen_name', '')
        self._publish(
            message_id=tweet_id,
            message=tweet.get('text', ''),
            timestamp=iso8601utc(parsetime(tweet.get('created_at', ''))),
            stream=stream,
            sender=user.get('name', ''),
            sender_nick=screen_name,
            from_me=(screen_name == self._account.user_name),
            icon_uri=user.get('profile_image_url_https', ''),
            liked=tweet.get('favorited', False),
            url=self._tweet_permalink.format(user_id=screen_name,
                                             tweet_id=tweet_id),
            )

# https://dev.twitter.com/docs/api/1.1/get/statuses/home_timeline
    @feature
    def home(self):
        """Gather the user's home timeline."""
        url = self._timeline.format(
            'home') + '?count={}'.format(self._DOWNLOAD_LIMIT)
        for tweet in self._get_url(url):
            self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/get/statuses/mentions_timeline
    @feature
    def mentions(self):
        """Gather the tweets that mention us."""
        url = self._mentions_timeline
        for tweet in self._get_url(url):
            self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/get/statuses/user_timeline
    @feature
    def user(self, screen_name=''):
        """Gather the tweets from a specific user.

        If screen_name is not specified, then gather the tweets written by the
        currently authenticated user.
        """
        url = self._user_timeline.format(screen_name)
        for tweet in self._get_url(url):
            self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/get/lists/statuses
    @feature
    def list(self, list_id):
        """Gather the tweets from the specified list_id."""
        url = self._lists.format(list_id)
        for tweet in self._get_url(url):
            self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/get/lists/list
    @feature
    def lists(self):
        """Gather the tweets from the lists that the we are subscribed to."""
        url = self._api_base.format(endpoint='lists/list')
        for twitlist in self._get_url(url):
            self.list(twitlist.get('id_str', ''))

# https://dev.twitter.com/docs/api/1.1/get/direct_messages
# https://dev.twitter.com/docs/api/1.1/get/direct_messages/sent
    @feature
    def private(self):
        """Gather the direct messages sent to/from us."""
        url = self._api_base.format(endpoint='direct_messages')
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream='private')

        url = self._api_base.format(endpoint='direct_messages/sent')
        for tweet in self._get_url(url):
            self._publish_tweet(tweet, stream='private')

    @feature
    def receive(self):
        """Gather and publish all incoming messages."""
        self.home()
        self.mentions()
        self.private()

    @feature
    def send_private(self, screen_name, message):
        """Send a direct message to the given screen name.

        This will error 403 if the person you are sending to does not follow
        you.
        """
        url = self._api_base.format(endpoint='direct_messages/new')
        try:
            tweet = self._get_url(
                url, dict(text=message, screen_name=screen_name))
        except HTTPError as error:
            log.error('{}: Does that user follow you?'.format(error))
        else:
            self._publish_tweet(tweet, stream='private')

# https://dev.twitter.com/docs/api/1.1/post/statuses/update
    @feature
    def send(self, message):
        """Publish a public tweet."""
        url = self._api_base.format(endpoint='statuses/update')
        tweet = self._get_url(url, dict(status=message))
        self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/post/statuses/update
    @feature
    def send_thread(self, message_id, message):
        """Send a reply message to message_id.

        Note that you have to @mention the message_id owner's screen name in
        order for Twitter to actually accept this as a reply.  Otherwise it
        will just be an ordinary tweet.
        """
        url = self._api_base.format(endpoint='statuses/update')
        tweet = self._get_url(url, dict(in_reply_to_status_id=message_id,
                                        status=message))
        self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/post/statuses/destroy/%3Aid
    @feature
    def delete(self, message_id):
        """Delete a tweet that you wrote."""
        url = self._destroy.format(message_id)
        # We can ignore the return value.
        self._get_url(url, dict(trim_user='true'))
        self._unpublish(message_id)

# https://dev.twitter.com/docs/api/1.1/post/statuses/retweet/%3Aid
    @feature
    def retweet(self, message_id):
        """Republish somebody else's tweet with your name on it."""
        url = self._retweet.format(message_id)
        tweet = self._get_url(url, dict(trim_user='true'))
        self._publish_tweet(tweet)

# https://dev.twitter.com/docs/api/1.1/post/friendships/destroy
    @feature
    def unfollow(self, screen_name):
        """Stop following the given screen name."""
        url = self._api_base.format(endpoint='friendships/destroy')
        self._get_url(url, dict(screen_name=screen_name))

# https://dev.twitter.com/docs/api/1.1/post/friendships/create
    @feature
    def follow(self, screen_name):
        """Start following the given screen name."""
        url = self._api_base.format(endpoint='friendships/create')
        self._get_url(url, dict(screen_name=screen_name, follow='true'))

# https://dev.twitter.com/docs/api/1.1/post/favorites/create
    @feature
    def like(self, message_id):
        """Announce to the world your undying love for a tweet."""
        url = self._api_base.format(endpoint='favorites/create')
        self._get_url(url, dict(id=message_id))
        # I don't think we need to publish this tweet because presumably the
        # user has clicked the 'favorite' button on the message that's already
        # in the stream.

# https://dev.twitter.com/docs/api/1.1/post/favorites/destroy
    @feature
    def unlike(self, message_id):
        """Renounce your undying love for a tweet."""
        url = self._api_base.format(endpoint='favorites/destroy')
        self._get_url(url, dict(id=message_id))

# https://dev.twitter.com/docs/api/1.1/get/search/tweets
    @feature
    def tag(self, hashtag):
        """Return a list of some recent tweets mentioning hashtag."""
        self.search('#' + hashtag.lstrip('#'))

# https://dev.twitter.com/docs/api/1.1/get/search/tweets
    @feature
    def search(self, query):
        """Search for any arbitrary string."""
        url = self._search

        response = self._get_url('{}?q={}'.format(url, quote(query, safe='')))
        for tweet in response.get(self._search_result_key, []):
            self._publish_tweet(tweet, stream='search/{}'.format(query))


class RateLimiter(BaseRateLimiter):
    """Twitter rate limiter."""

    def __init__(self):
        self._limits = {}

    def _sanitize_url(self, uri):
        # Cache the URL sans any query parameters.
        return uri.host + uri.path

    def wait(self, message):
        # If we haven't seen this URL, default to no wait.
        seconds = self._limits.get(self._sanitize_url(message.get_uri()), 0)
        time.sleep(seconds)

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
