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

"""Test the Twitter plugin."""


__all__ = [
    'TestTwitter',
    ]


import unittest

from gi.repository import Dee
from urllib.error import HTTPError

from friends.protocols.twitter import RateLimiter, Twitter
from friends.testing.helpers import FakeAccount
from friends.testing.mocks import FakeSoupMessage, LogMock, mock
from friends.utils.model import COLUMN_TYPES


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


@mock.patch('friends.utils.http._soup', mock.Mock())
class TestTwitter(unittest.TestCase):
    """Test the Twitter API."""

    def setUp(self):
        TestModel.clear()
        self.account = FakeAccount()
        self.protocol = Twitter(self.account)
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.twitter')

    def tearDown(self):
        # Ensure that any log entries we haven't tested just get consumed so
        # as to isolate out test logger from other tests.
        self.log_mock.stop()

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=None)
    @mock.patch('friends.protocols.twitter.Downloader.get_json',
                return_value=None)
    def test_unsuccessful_authentication(self, dload, login):
        self.assertFalse(self.protocol._login())
        self.assertIsNone(self.account.user_name)
        self.assertIsNone(self.account.user_id)

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='some clever fake data',
                                  TokenSecret='sssssshhh!',
                                  UserId='rickygervais',
                                  ScreenName='Ricky Gervais'))
    def test_successful_authentication(self, *mocks):
        self.assertTrue(self.protocol._login())
        self.assertEqual(self.account.user_name, 'Ricky Gervais')
        self.assertEqual(self.account.user_id, 'rickygervais')
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
        self.account.auth.id = 6
        self.account.auth.method = 'oauth2'
        self.account.auth.mechanism = 'HMAC-SHA1'
        self.account.auth.parameters = dict(ConsumerKey='consume',
                                            ConsumerSecret='obey')
        result = '''\
OAuth oauth_nonce="once%20upon%20a%20nonce", \
oauth_timestamp="1348690628", \
oauth_version="1.0", \
oauth_signature_method="HMAC-SHA1", \
oauth_consumer_key="consume", \
oauth_token="omega", \
oauth_signature="2MlC4DOqcAdCUmU647izPmxiL%2F0%3D"'''

        self.protocol._rate_limiter = 'limits'
        self.protocol._get_url('http://example.com')
        self.assertEqual(
            dload.mock_calls,
            [mock.call('http://example.com',
                       headers=dict(Authorization=result),
                       rate_limiter='limits',
                       params=None,
                       method='GET'),
             mock.call().get_json()])

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-home.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_home(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.account.auth.parameters = dict(
            ConsumerKey='key',
            ConsumerSecret='secret')
        self.assertEqual(0, TestModel.get_n_rows())
        self.protocol.home()
        self.assertEqual(3, TestModel.get_n_rows())

        # This test data was ripped directly from Twitter's API docs.
        expected = [
            [[['twitter', 'faker/than fake', '240558470661799936']],
             'messages', 'OAuth Dancer', '119476949', 'oauth_dancer', False,
             '2012-08-28T21:16:23Z', 'just another test', '', '',
             'https://twitter.com/oauth_dancer/status/240558470661799936', '',
             '', '', '', 0.0, False, '', '', '', '', '', '', '', '', '', '',
             '', '', '', '', '', '', '', '', '', '',
             ],
            [[['twitter', 'faker/than fake', '240556426106372096']],
             'messages', 'Raffi Krikorian', '8285392', 'raffi', False,
             '2012-08-28T21:08:15Z', 'lecturing at the "analyzing big data ' +
             'with twitter" class at @cal with @othman  http://t.co/bfj7zkDJ',
             '', '', 'https://twitter.com/raffi/status/240556426106372096', '',
             '', '', '', 0.0, False, '', '', '', '', '', '', '', '', '', '',
             '', '', '', '', '', '', '', '', '', '',
             ],
            [[['twitter', 'faker/than fake', '240539141056638977']],
             'messages', 'Taylor Singletary', '819797', 'episod', False,
             '2012-08-28T19:59:34Z',
             'You\'d be right more often if you thought you were wrong.', '',
             '', 'https://twitter.com/episod/status/240539141056638977', '',
             '', '', '', 0.0, False, '', '', '', '', '', '', '', '', '', '',
             '', '', '', '', '', '', '', '', '', '',
             ],
            ]
        for i, expected_row in enumerate(expected):
            for got, want in zip(TestModel.get_row(i), expected_row):
                self.assertEqual(got, want)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'twitter-send.dat'))
    @mock.patch('friends.protocols.twitter.Twitter._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_from_me(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.account.user_name = 'oauth_dancer'
        self.account.auth.parameters = dict(
            ConsumerKey='key',
            ConsumerSecret='secret')
        self.assertEqual(0, TestModel.get_n_rows())
        self.protocol.send('some message')
        self.assertEqual(1, TestModel.get_n_rows())

        # This test data was ripped directly from Twitter's API docs.
        expected_row = [
            [['twitter', 'faker/than fake', '240558470661799936']],
            'messages', 'OAuth Dancer', '119476949', 'oauth_dancer', True,
            '2012-08-28T21:16:23Z', 'just another test', '', '',
            'https://twitter.com/oauth_dancer/status/240558470661799936', '',
            '', '', '', 0.0, False, '', '', '', '', '', '', '', '', '', '',
            '', '', '', '', '', '', '', '', '', '',
            ]
        for got, want in zip(TestModel.get_row(0), expected_row):
            self.assertEqual(got, want)

    def test_home_url(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.home()

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/home_timeline.json?count=50')

    def test_mentions(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.mentions()

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/mentions_timeline.json')

    def test_user(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.user()

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
        'https://api.twitter.com/1.1/statuses/user_timeline.json?screen_name=')

    def test_list(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.list('some_list_id')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
        'https://api.twitter.com/1.1/lists/statuses.json?list_id=some_list_id')

    def test_lists(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=[dict(id_str='twitlist')])
        publish = self.protocol.list = mock.Mock()

        self.protocol.lists()

        publish.assert_called_with('twitlist')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/lists/list.json')

    def test_private(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.private()

        publish.assert_called_with('tweet', stream='private')
        self.assertEqual(
            get_url.mock_calls,
            [mock.call('https://api.twitter.com/1.1/direct_messages.json'),
             mock.call('https://api.twitter.com/1.1/direct_messages/sent.json')
             ])

    @mock.patch('friends.protocols.twitter.Avatar.get_image',
                return_value='~/.cache/friends/avatars/hash')
    def test_private_avatars(self, image_mock):
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
            icon_uri='~/.cache/friends/avatars/hash',
            sender_nick='some_guy', sender_id='', from_me=False,
            timestamp='2012-11-04T17:14:52Z', message='Does my avatar show up?',
            message_id='1452456')
        self.assertEqual(
            get_url.mock_calls,
            [mock.call('https://api.twitter.com/1.1/direct_messages.json'),
             mock.call('https://api.twitter.com/1.1/direct_messages/sent.json')
             ])

    def test_send_private(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.send_private('pumpichank', 'Are you mocking me?')

        publish.assert_called_with('tweet', stream='private')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/direct_messages/new.json',
            dict(text='Are you mocking me?', screen_name='pumpichank'))

    def test_failing_send_private(self):
        def fail(*ignore):
            raise HTTPError('url', 403, 'Forbidden', 'Forbidden', mock.Mock())

        with mock.patch.object(self.protocol, '_get_url', side_effect=fail):
            self.protocol.send_private('pumpichank', 'Are you mocking me?')

        self.assertEqual(
            self.log_mock.empty(),
            'HTTP Error 403: Forbidden: Does that user follow you?\n')

    def test_send(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.send('Hello, twitterverse!')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/update.json',
            dict(status='Hello, twitterverse!'))

    def test_send_thread(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.send_thread(
            '1234',
            'Why yes, I would love to respond to your tweet @pumpichank!')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/update.json',
            dict(status='Why yes, I would love to respond to your '
                        'tweet @pumpichank!',
                 in_reply_to_status_id='1234'))

    def test_delete(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._unpublish = mock.Mock()

        self.protocol.delete('1234')

        publish.assert_called_with('1234')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/destroy/1234.json',
            dict(trim_user='true'))

    def test_retweet(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.retweet('1234')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/statuses/retweet/1234.json',
            dict(trim_user='true'))

    def test_unfollow(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.protocol.unfollow('pumpichank')

        get_url.assert_called_with(
            'https://api.twitter.com/1.1/friendships/destroy.json',
            dict(screen_name='pumpichank'))

    def test_follow(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.protocol.follow('pumpichank')

        get_url.assert_called_with(
            'https://api.twitter.com/1.1/friendships/create.json',
            dict(screen_name='pumpichank', follow='true'))

    def test_like(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.protocol.like('1234')

        get_url.assert_called_with(
            'https://api.twitter.com/1.1/favorites/create.json',
            dict(id='1234'))

    def test_unlike(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.protocol.unlike('1234')

        get_url.assert_called_with(
            'https://api.twitter.com/1.1/favorites/destroy.json',
            dict(id='1234'))

    def test_tag(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=dict(statuses=['tweet']))
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.tag('yegbike')

        publish.assert_called_with('tweet', stream='search/#yegbike')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/search/tweets.json?q=%23yegbike')

        self.protocol.tag('#yegbike')

        publish.assert_called_with('tweet', stream='search/#yegbike')
        get_url.assert_called_with(
            'https://api.twitter.com/1.1/search/tweets.json?q=%23yegbike')

    def test_search(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=dict(statuses=['tweet']))
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.search('hello')

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
        self.account.auth.parameters = dict(
            ConsumerKey='key',
            ConsumerSecret='secret')
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
