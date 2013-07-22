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

"""Test the Twitter plugin."""


__all__ = [
    'TestTwitter',
    ]


import os
import tempfile
import unittest
import shutil

from urllib.error import HTTPError

from friends.protocols.twitter import RateLimiter, Twitter
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock
from friends.tests.mocks import TestModel, mock
from friends.utils.cache import JsonCache
from friends.errors import AuthorizationError


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
class TestTwitter(unittest.TestCase):
    """Test the Twitter API."""

    def setUp(self):
        self._temp_cache = tempfile.mkdtemp()
        self._root = JsonCache._root = os.path.join(
            self._temp_cache, '{}.json')
        TestModel.clear()
        self.account = FakeAccount()
        self.protocol = Twitter(self.account)
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.twitter')

    def tearDown(self):
        # Ensure that any log entries we haven't tested just get consumed so
        # as to isolate out test logger from other tests.
        self.log_mock.stop()
        shutil.rmtree(self._temp_cache)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    @mock.patch('friends.protocols.twitter.Downloader.get_json',
                return_value=None)
    def test_unsuccessful_authentication(self, dload, login, *mocks):
        self.assertRaises(AuthorizationError, self.protocol._login)
        self.assertIsNone(self.account.user_name)
        self.assertIsNone(self.account.user_id)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch('friends.utils.authentication.Authentication.__init__',
                return_value=None)
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='some clever fake data',
                                  TokenSecret='sssssshhh!',
                                  UserId='1234',
                                  ScreenName='stephenfry'))
    def test_successful_authentication(self, *mocks):
        self.assertTrue(self.protocol._login())
        self.assertEqual(self.account.user_name, 'stephenfry')
        self.assertEqual(self.account.user_id, '1234')
        self.assertEqual(self.account.access_token, 'some clever fake data')
        self.assertEqual(self.account.secret_token, 'sssssshhh!')

    @mock.patch('friends.protocols.twitter.Downloader')
    @mock.patch('oauthlib.oauth1.rfc5849.generate_nonce',
                lambda: 'once upon a nonce')
    @mock.patch('oauthlib.oauth1.rfc5849.generate_timestamp',
                lambda: '1348690628')
    def test_signatures(self, dload):
        self.account.secret_token = 'alpha'
        self.account.access_token = 'omega'
        self.account.consumer_secret = 'obey'
        self.account.consumer_key = 'consume'
        self.account.auth.get_credentials_id = lambda *ignore: 6
        self.account.auth.get_method = lambda *ignore: 'oauth2'
        self.account.auth.get_mechanism = lambda *ignore: 'HMAC-SHA1'

        result = '''\
OAuth oauth_nonce="once%20upon%20a%20nonce", \
oauth_timestamp="1348690628", \
oauth_version="1.0", \
oauth_signature_method="HMAC-SHA1", \
oauth_consumer_key="consume", \
oauth_token="omega", \
oauth_signature="2MlC4DOqcAdCUmU647izPmxiL%2F0%3D"'''

        self.protocol._rate_limiter = 'limits'
        class fake:
            def get_json():
                return None
        dload.return_value = fake
        self.protocol._get_url('http://example.com')
        dload.assert_called_once_with(
            'http://example.com',
            headers=dict(Authorization=result),
            rate_limiter='limits',
            params=None,
            method='GET')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-home.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_home(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertEqual(self.protocol.home(), 3)
        self.assertEqual(3, TestModel.get_n_rows())

        # This test data was ripped directly from Twitter's API docs.
        expected = [
            ['twitter', 88, '240558470661799936',
             'messages', 'OAuth Dancer', '119476949', 'oauth_dancer', False,
             '2012-08-28T21:16:23Z', 'just another test',
             'https://si0.twimg.com/profile_images/730275945/oauth-dancer.jpg',
             'https://twitter.com/oauth_dancer/status/240558470661799936',
             0, False, '', '', '', '', '', '', '', 0.0, 0.0,
             ],
            ['twitter', 88, '240556426106372096',
             'messages', 'Raffi Krikorian', '8285392', 'raffi', False,
             '2012-08-28T21:08:15Z', 'lecturing at the "analyzing big data '
             'with twitter" class at @cal with @othman  '
             '<a href="http://blogs.ischool.berkeley.edu/i290-abdt-s12/">'
             'http://blogs.ischool.berkeley.edu/i290-abdt-s12/</a>',
             'https://si0.twimg.com/profile_images/1270234259/'
             'raffi-headshot-casual.png',
             'https://twitter.com/raffi/status/240556426106372096',
             0, False, '', '', '', '', '', '', '', 0.0, 0.0,
             ],
            ['twitter', 88, '240539141056638977',
             'messages', 'Taylor Singletary', '819797', 'episod', False,
             '2012-08-28T19:59:34Z',
             'You\'d be right more often if you thought you were wrong.',
             'https://si0.twimg.com/profile_images/2546730059/'
             'f6a8zq58mg1hn0ha8vie.jpeg',
             'https://twitter.com/episod/status/240539141056638977',
             0, False, '', '', '', '', '', '', '', 0.0, 0.0,
             ],
            ]
        for i, expected_row in enumerate(expected):
            self.assertEqual(list(TestModel.get_row(i)), expected_row)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-home.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_home_since_id(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.assertEqual(self.protocol.home(), 3)

        with open(self._root.format('twitter_ids'), 'r') as fd:
            self.assertEqual(fd.read(), '{"messages": 240558470661799936}')

        get_url = self.protocol._get_url = mock.Mock()
        get_url.return_value = []
        self.assertEqual(self.protocol.home(), 3)
        get_url.assert_called_once_with(
            'https://api.twitter.com/1.1/statuses/' +
            'home_timeline.json?count=50&since_id=240558470661799936')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-send.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_from_me(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.account.user_name = 'oauth_dancer'
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertEqual(
            self.protocol.send('some message'),
            'https://twitter.com/oauth_dancer/status/240558470661799936')
        self.assertEqual(1, TestModel.get_n_rows())

        # This test data was ripped directly from Twitter's API docs.
        expected_row = [
            'twitter', 88, '240558470661799936',
            'messages', 'OAuth Dancer', '119476949', 'oauth_dancer', True,
            '2012-08-28T21:16:23Z', 'just another test',
            'https://si0.twimg.com/profile_images/730275945/oauth-dancer.jpg',
            'https://twitter.com/oauth_dancer/status/240558470661799936',
            0, False, '', '', '', '', '', '', '', 0.0, 0.0,
            ]
        self.assertEqual(list(TestModel.get_row(0)), expected_row)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_home_url(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.home(), 0)

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/home_timeline.json?count=50')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_mentions(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.mentions(), 0)

        publish.assert_called_with('tweet', stream='mentions')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/' +
            'mentions_timeline.json?count=50')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_user(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.user(), 0)

        publish.assert_called_with('tweet', stream='messages')
        get_url.assert_called_with(
        'https://api.twitter.com/1.1/statuses/user_timeline.json?screen_name=')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_list(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.list('some_list_id'), 0)

        publish.assert_called_with('tweet', stream='list/some_list_id')
        get_url.assert_called_with(
        'https://api.twitter.com/1.1/lists/statuses.json?list_id=some_list_id')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_lists(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=[dict(id_str='twitlist')])
        publish = self.protocol.list = mock.Mock()

        self.assertEqual(self.protocol.lists(), 0)

        publish.assert_called_with('twitlist')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/lists/list.json')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_private(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.private(), 0)

        publish.assert_called_with('tweet', stream='private')
        self.assertEqual(
            get_url.mock_calls,
            [mock.call('https://api.twitter.com/1.1/' +
                       'direct_messages.json?count=50'),
             mock.call('https://api.twitter.com/1.1/' +
                       'direct_messages/sent.json?count=50')
             ])

    def test_private_avatars(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=[
                dict(
                    created_at='Sun Nov 04 17:14:52 2012',
                    text='Does my avatar show up?',
                    id_str='1452456',
                    sender=dict(
                        screen_name='some_guy',
                        name='Bob',
                        profile_image_url_https='https://example.com/bob.jpg',
                        ),
                    )])
        publish = self.protocol._publish = mock.Mock()

        self.protocol.private()

        publish.assert_called_with(
            liked=False, sender='Bob', stream='private',
            url='https://twitter.com/some_guy/status/1452456',
            icon_uri='https://example.com/bob.jpg',
            sender_nick='some_guy', sender_id='', from_me=False,
            timestamp='2012-11-04T17:14:52Z', message='Does my avatar show up?',
            message_id='1452456')
        self.assertEqual(
            get_url.mock_calls,
            [mock.call('https://api.twitter.com/1.1/' +
                       'direct_messages.json?count=50'),
             mock.call('https://api.twitter.com/1.1/' +
                       'direct_messages/sent.json?count=50&since_id=1452456')
             ])

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_send_private(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock(
            return_value='https://twitter.com/screen_name/status/tweet_id')

        self.assertEqual(
            self.protocol.send_private('pumpichank', 'Are you mocking me?'),
            'https://twitter.com/screen_name/status/tweet_id')

        publish.assert_called_with('tweet', stream='private')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/direct_messages/new.json',
            dict(text='Are you mocking me?', screen_name='pumpichank'))

    def test_failing_send_private(self):
        def fail(*ignore):
            raise HTTPError('url', 403, 'Forbidden', 'Forbidden', mock.Mock())

        with mock.patch.object(self.protocol, '_get_url', side_effect=fail):
            self.assertRaises(
                HTTPError,
                self.protocol.send_private,
                'pumpichank',
                'Are you mocking me?',
                )

    def test_send(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock(
            return_value='https://twitter.com/u/status/id')

        self.assertEqual(
            self.protocol.send('Hello, twitterverse!'),
            'https://twitter.com/u/status/id')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/update.json',
            dict(status='Hello, twitterverse!'))

    def test_send_thread(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock(
            return_value='tweet permalink')

        self.assertEqual(
            self.protocol.send_thread(
                '1234',
                'Why yes, I would love to respond to your tweet @pumpichank!'),
            'tweet permalink')

        publish.assert_called_with('tweet', stream='reply_to/1234')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/update.json',
            dict(status='Why yes, I would love to respond to your '
                        'tweet @pumpichank!',
                 in_reply_to_status_id='1234'))

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-home.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_send_thread_prepend_nick(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertEqual(self.protocol.home(), 3)
        self.assertEqual(3, TestModel.get_n_rows())

        # If you forgot to @mention in your reply, we add it for you.
        get = self.protocol._get_url = mock.Mock()
        self.protocol._publish_tweet = mock.Mock()
        self.protocol.send_thread(
            '240556426106372096',
            'Exciting and original response!')
        get.assert_called_once_with(
            'https://api.twitter.com/1.1/statuses/update.json',
            dict(status='@raffi Exciting and original response!',
                 in_reply_to_status_id='240556426106372096'))

        # If you remembered the @mention, we won't duplicate it.
        get.reset_mock()
        self.protocol.send_thread(
            '240556426106372096',
            'You are the greatest, @raffi!')
        get.assert_called_once_with(
            'https://api.twitter.com/1.1/statuses/update.json',
            dict(status='You are the greatest, @raffi!',
                 in_reply_to_status_id='240556426106372096'))


    def test_delete(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._unpublish = mock.Mock()

        self.assertEqual(self.protocol.delete('1234'), '1234')

        publish.assert_called_with('1234')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/destroy/1234.json',
            dict(trim_user='true'))

    def test_retweet(self):
        tweet = dict(tweet='twit')
        get_url = self.protocol._get_url = mock.Mock(return_value=tweet)
        publish = self.protocol._publish_tweet = mock.Mock(
            return_value='tweet permalink')

        self.assertEqual(self.protocol.retweet('1234'), 'tweet permalink')

        publish.assert_called_with(tweet)
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/retweet/1234.json',
            dict(trim_user='false'))

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-retweet.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_retweet_with_data(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.account.user_name = 'therealrobru'
        self.account.auth.parameters = dict(
            ConsumerKey='key',
            ConsumerSecret='secret')
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertEqual(
            self.protocol.retweet('240558470661799936'),
            'https://twitter.com/therealrobru/status/324220250889543682')
        self.assertEqual(1, TestModel.get_n_rows())

        self.maxDiff = None
        expected_row = [
            'twitter', 88, '324220250889543682',
            'messages', 'Robert Bruce', '836242932', 'therealrobru', True,
            '2013-04-16T17:58:26Z', 'RT @tarek_ziade: Just found a "Notification '
            'of Inspection" card in the bottom of my bag. looks like they were '
            'curious about those raspbe ...',
            'https://si0.twimg.com/profile_images/2631306428/'
            '2a509db8a05b4310394b832d34a137a4.png',
            'https://twitter.com/therealrobru/status/324220250889543682',
            0, False, '', '', '', '', '', '', '', 0.0, 0.0,
            ]
        self.assertEqual(list(TestModel.get_row(0)), expected_row)

    def test_unfollow(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.assertEqual(self.protocol.unfollow('pumpichank'), 'pumpichank')

        get_url.assert_called_with(
            'https://api.twitter.com/1.1/friendships/destroy.json',
            dict(screen_name='pumpichank'))

    def test_follow(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.assertEqual(self.protocol.follow('pumpichank'), 'pumpichank')

        get_url.assert_called_with(
            'https://api.twitter.com/1.1/friendships/create.json',
            dict(screen_name='pumpichank', follow='true'))

    def test_like(self):
        get_url = self.protocol._get_url = mock.Mock()
        inc_cell = self.protocol._inc_cell = mock.Mock()
        set_cell = self.protocol._set_cell = mock.Mock()

        self.assertEqual(self.protocol.like('1234'), '1234')

        inc_cell.assert_called_once_with('1234', 'likes')
        set_cell.assert_called_once_with('1234', 'liked', True)
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/favorites/create.json',
            dict(id='1234'))

    def test_unlike(self):
        get_url = self.protocol._get_url = mock.Mock()
        dec_cell = self.protocol._dec_cell = mock.Mock()
        set_cell = self.protocol._set_cell = mock.Mock()

        self.assertEqual(self.protocol.unlike('1234'), '1234')

        dec_cell.assert_called_once_with('1234', 'likes')
        set_cell.assert_called_once_with('1234', 'liked', False)
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/favorites/destroy.json',
            dict(id='1234'))

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_tag(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=dict(statuses=['tweet']))
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.tag('yegbike'), 0)

        publish.assert_called_with('tweet', stream='search/#yegbike')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/search/tweets.json?q=%23yegbike')

        self.assertEqual(self.protocol.tag('#yegbike'), 0)

        publish.assert_called_with('tweet', stream='search/#yegbike')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/search/tweets.json?q=%23yegbike')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_search(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=dict(statuses=['tweet']))
        publish = self.protocol._publish_tweet = mock.Mock()

        self.assertEqual(self.protocol.search('hello'), 0)

        publish.assert_called_with('tweet', stream='search/hello')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/search/tweets.json?q=hello')

    @mock.patch('friends.protocols.twitter.time.sleep')
    def test_rate_limiter_first_time(self, sleep):
        # The first time we see a URL, there is no rate limiting.
        limiter = RateLimiter()
        message = FakeSoupMessage('friends.tests.data', 'twitter-home.dat')
        message.new('GET', 'http://example.com/')
        limiter.wait(message)
        sleep.assert_called_with(0)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_second_time(self, time, sleep):
        # The second time we see the URL, we get rate limited.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 1,
                })
        limiter.update(message.new('GET', 'http://example.com'))
        limiter.wait(message)
        sleep.assert_called_with(300)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_second_time_with_query(self, time, sleep):
        # A query parameter on the second request is ignored.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 1,
                })
        limiter.update(message.new('GET', 'http://example.com/foo?baz=7'))
        limiter.wait(message)
        sleep.assert_called_with(300)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_second_time_with_query_on_request(self, time, sleep):
        # A query parameter on the original request is ignored.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 1,
                })
        limiter.update(message.new('GET', 'http://example.com/foo?baz=7'))
        limiter.wait(message)
        sleep.assert_called_with(300)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_maximum(self, time, sleep):
        # With one remaining call this window, we get rate limited to the
        # full amount of the remaining window.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 1,
                })
        limiter.update(message.new('GET', 'http://example.com/alpha'))
        limiter.wait(message)
        sleep.assert_called_with(300)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_until_end_of_window(self, time, sleep):
        # With no remaining calls left this window, we wait until the end of
        # the window.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 0,
                })
        limiter.update(message.new('GET', 'http://example.com/alpha'))
        limiter.wait(message)
        sleep.assert_called_with(300)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_medium(self, time, sleep):
        # With a few calls remaining this window, we time slice the remaining
        # time evenly between those remaining calls.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 3,
                })
        limiter.update(message.new('GET', 'http://example.com/beta'))
        limiter.wait(message)
        sleep.assert_called_with(100.0)

    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_rate_limiter_unlimited(self, time, sleep):
        # With more than 5 calls remaining in this window, we don't rate
        # limit, even if we've already seen this url.
        limiter = RateLimiter()
        message = FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 10,
                })
        limiter.update(message.new('GET', 'http://example.com/omega'))
        limiter.wait(message)
        sleep.assert_called_with(0)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch(
        'friends.utils.http.Soup.Message',
        FakeSoupMessage(
            'friends.tests.data', 'twitter-home.dat',
            headers={
                'X-Rate-Limit-Reset': 1349382153 + 300,
                'X-Rate-Limit-Remaining': 3,
                }))
    @mock.patch('friends.protocols.twitter.time.sleep')
    @mock.patch('friends.protocols.twitter.time.time', return_value=1349382153)
    def test_protocol_rate_limiting(self, time, sleep, login):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        # Test rate limiting via the Twitter plugin API.
        #
        # The first call doesn't get rate limited.
        self.protocol.home()
        sleep.assert_called_with(0)
        # Second call gets called with the established limit.  Because there
        # are three more calls allowed within the current window, and we're
        # reporting 300 seconds left in the current window, we're saying we'll
        # sleep 100 seconds between each call.
        self.protocol.home()
        sleep.assert_called_with(100.0)

    def test_contacts(self):
        get = self.protocol._get_url = mock.Mock(
            return_value=dict(ids=[1,2],name='Bob',screen_name='bobby'))
        prev = self.protocol._previously_stored_contact = mock.Mock(return_value=False)
        push = self.protocol._push_to_eds = mock.Mock()
        self.assertEqual(self.protocol.contacts(), 2)
        self.assertEqual(
            get.call_args_list,
            [mock.call('https://api.twitter.com/1.1/friends/ids.json'),
             mock.call(url='https://api.twitter.com/1.1/users/show.json?user_id=1'),
             mock.call(url='https://api.twitter.com/1.1/users/show.json?user_id=2')])
        self.assertEqual(
            prev.call_args_list,
            [mock.call('1'), mock.call('2')])
        self.assertEqual(
            push.call_args_list,
            [mock.call({'twitter-id': '1',
                        'X-FOLKS-WEB-SERVICES-IDS': {
                            'twitter-id': '1',
                            'remote-full-name': 'Bob'},
                        'X-URIS': 'https://twitter.com/bobby',
                        'twitter-name': 'Bob',
                        'twitter-nick': 'bobby'}),
             mock.call({'twitter-id': '2',
                        'X-FOLKS-WEB-SERVICES-IDS': {
                            'twitter-id': '2',
                            'remote-full-name': 'Bob'},
                        'X-URIS': 'https://twitter.com/bobby',
                        'twitter-name': 'Bob',
                        'twitter-nick': 'bobby'})])
