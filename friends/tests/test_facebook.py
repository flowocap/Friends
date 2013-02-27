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

"""Test the Facebook plugin."""

__all__ = [
    'TestFacebook',
    ]


import unittest

from gi.repository import Dee, GLib
from pkg_resources import resource_filename

from friends.protocols.facebook import Facebook, FacebookError
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock, mock
from friends.tests.mocks import EDSBookClientMock, EDSSource, EDSRegistry
from friends.errors import ContactsError, FriendsError, AuthorizationError
from friends.utils.model import COLUMN_TYPES


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
class TestFacebook(unittest.TestCase):
    """Test the Facebook API."""

    def setUp(self):
        self.account = FakeAccount()
        self.protocol = Facebook(self.account)
        self.protocol.source_registry = EDSRegistry()

    def tearDown(self):
        TestModel.clear()

    def test_features(self):
        # The set of public features.
        self.assertEqual(Facebook.get_features(),
            ['contacts', 'delete', 'home', 'like', 'receive', 'search', 'send',
             'send_thread', 'unlike', 'upload', 'wall'])

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='abc'))
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-login.dat'))
    def test_successful_login(self, mock):
        # Test that a successful response from graph.facebook.com returning
        # the user's data, sets up the account dict correctly.
        self.protocol._login()
        self.assertEqual(self.account.access_token, 'abc')
        self.assertEqual(self.account.user_name, 'Bart Person')
        self.assertEqual(self.account.user_id, '801')

    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    def test_login_unsuccessful_authentication(self, mock):
        # The user is not already logged in, but the act of logging in fails.
        self.assertRaises(AuthorizationError, self.protocol._login)
        self.assertIsNone(self.account.access_token)
        self.assertIsNone(self.account.user_name)

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='abc'))
    @mock.patch('friends.protocols.facebook.Downloader.get_json',
                return_value=dict(
                    error=dict(message='Bad access token',
                               type='OAuthException',
                               code=190)))
    def test_error_response(self, *mocks):
        with LogMock('friends.utils.base',
                     'friends.protocols.facebook') as log_mock:
            self.assertRaises(
                FacebookError,
                self.protocol.home,
                )
            contents = log_mock.empty(trim=False)
        self.assertEqual(contents, """\
Logging in to Facebook
Facebook UID: None
""")

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-full.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.protocols.facebook.Facebook._login',
                return_value=True)
    def test_receive(self, *mocks):
        # Receive the wall feed for a user.
        self.maxDiff = None
        self.account.access_token = 'abc'
        self.assertEqual(self.protocol.receive(), 4)
        self.assertEqual(TestModel.get_n_rows(), 4)
        self.assertEqual(list(TestModel.get_row(2)), [
            [['facebook',
              '1234',
              '117402931676347_386054134801436_3235476']],
            'reply_to/109',
            'Bruce Peart',
            '809',
            'Bruce Peart',
            False,
            '2012-09-26T17:16:00Z',
            'OK Don...10) Headlong Flight',
            GLib.get_user_cache_dir() +
            '/friends/avatars/b688c8def0455d4a3853d5fcdfaf0708645cfd3e',
            'https://www.facebook.com/809',
            0.0,
            False,
            '',
            '',
            '',
            '',
            '',
            ''])
        self.assertEqual(list(TestModel.get_row(0)), [
            [['facebook', '1234', '108']],
            'mentions',
            'Rush is a Band',
            '117402931676347',
            'Rush is a Band',
            False,
            '2012-09-26T17:34:00Z',
            'Rush takes off to the Great White North',
            GLib.get_user_cache_dir() +
            '/friends/avatars/7d1a70e6998f4a38954e93ca03d689463f71d63b',
            'https://www.facebook.com/117402931676347',
            16.0,
            False,
            'https://fbexternal-a.akamaihd.net/rush.jpg',
            'Rush is a Band Blog',
            'http://www.rushisaband.com/blog/Rush-Clockwork-Angels-tour',
            'Rush is a Band: Neil Peart, Geddy Lee, Alex Lifeson',
            'www.rushisaband.com',
            ''])
        self.assertEqual(list(TestModel.get_row(1)), [
            [['facebook', '1234', '109']],
            'mentions',
            'Rush is a Band',
            '117402931676347',
            'Rush is a Band',
            False,
            '2012-09-26T17:49:06Z',
            'http://www2.gibson.com/Alex-Lifeson-0225-2011.aspx',
            GLib.get_user_cache_dir() +
            '/friends/avatars/7d1a70e6998f4a38954e93ca03d689463f71d63b',
            'https://www.facebook.com/117402931676347',
            27.0,
            False,
            'https://images.gibson.com/Rush_Clockwork-Angels_t.jpg',
            'Top 10 Alex Lifeson Guitar Moments',
            'http://www2.gibson.com/Alex-Lifeson.aspx',
            'For millions of Rush fans old and new, it’s a pleasure',
            'www2.gibson.com',
            ''])

    # XXX We really need full coverage of the receive() method, including
    # cases where some data is missing, or can't be converted
    # (e.g. timestamps), and paginations.

    @mock.patch('friends.protocols.facebook.Downloader')
    def test_send_to_my_wall(self, dload):
        dload().get_json.return_value = dict(id='post_id')
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish_entry = mock.Mock(
            return_value='http://facebook.com/post_id')

        self.assertEqual(
            self.protocol.send('I can see the writing on my wall.'),
            'http://facebook.com/post_id')

        token.assert_called_once_with()
        publish.assert_called_with({'id': 'post_id'})
        self.assertEqual(
            dload.mock_calls,
            [mock.call(),
             mock.call('https://graph.facebook.com/me/feed',
                       method='POST',
                       params=dict(
                           access_token='face',
                           message='I can see the writing on my wall.')),
             mock.call().get_json(),
             mock.call('https://graph.facebook.com/post_id',
                       params=dict(access_token='face')),
             mock.call().get_json()
            ])

    @mock.patch('friends.protocols.facebook.Downloader')
    def test_send_to_my_friends_wall(self, dload):
        dload().get_json.return_value = dict(id='post_id')
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish_entry = mock.Mock(
            return_value='http://facebook.com/new_post_id')

        self.assertEqual(
            self.protocol.send('I can see the writing on my friend\'s wall.',
                               'friend_id'),
            'http://facebook.com/new_post_id')

        token.assert_called_once_with()
        publish.assert_called_with({'id': 'post_id'})
        self.assertEqual(
            dload.mock_calls,
            [mock.call(),
             mock.call(
                    'https://graph.facebook.com/friend_id/feed',
                    method='POST',
                    params=dict(
                       access_token='face',
                       message='I can see the writing on my friend\'s wall.')),
             mock.call().get_json(),
             mock.call('https://graph.facebook.com/post_id',
                       params=dict(access_token='face')),
             mock.call().get_json(),
             ])

    @mock.patch('friends.protocols.facebook.Downloader')
    def test_send_thread(self, dload):
        dload().get_json.return_value = dict(id='comment_id')
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish_entry = mock.Mock(
            return_value='http://facebook.com/private_message_id')

        self.assertEqual(
            self.protocol.send_thread('post_id', 'Some witty response!'),
            'http://facebook.com/private_message_id')

        token.assert_called_once_with()
        publish.assert_called_with({'id': 'comment_id'})
        self.assertEqual(
            dload.mock_calls,
            [mock.call(),
             mock.call(
                    'https://graph.facebook.com/post_id/comments',
                    method='POST',
                    params=dict(
                        access_token='face',
                        message='Some witty response!')),
             mock.call().get_json(),
             mock.call('https://graph.facebook.com/comment_id',
                       params=dict(access_token='face')),
             mock.call().get_json(),
             ])

    @mock.patch('friends.protocols.facebook.Uploader.get_json',
                return_value=dict(post_id='234125'))
    @mock.patch('friends.protocols.facebook.time.time',
                return_value=1352209748.1254)
    def test_upload_local(self, *mocks):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish = mock.Mock()

        src = 'file://' + resource_filename('friends.tests.data', 'ubuntu.png')
        self.assertEqual(self.protocol.upload(src, 'This is Ubuntu!'),
                         'https://www.facebook.com/234125')

        token.assert_called_once_with()

        publish.assert_called_once_with(
            sender_nick=None,
            stream='images',
            url='https://www.facebook.com/234125',
            timestamp='2012-11-06T13:49:08Z',
            sender_id=None,
            from_me=True,
            icon_uri=GLib.get_user_cache_dir() +
            '/friends/avatars/d49d72a384d50adf7c736ba27ca55bfa9fa5782d',
            message='This is Ubuntu!',
            message_id='234125',
            sender=None)

    @mock.patch('friends.utils.http._soup')
    @mock.patch('friends.protocols.facebook.Uploader._build_request',
                return_value=None)
    @mock.patch('friends.protocols.facebook.time.time',
                return_value=1352209748.1254)
    def test_upload_missing(self, *mocks):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish = mock.Mock()

        src = 'file:///tmp/a/non-existant/path'
        self.assertRaises(
            ValueError,
            self.protocol.upload,
            src,
            'There is no spoon',
            )
        token.assert_called_once_with()

        self.assertFalse(publish.called)

    @mock.patch('friends.utils.http._soup')
    def test_upload_not_uri(self, *mocks):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish = mock.Mock()

        src = resource_filename('friends.tests.data', 'ubuntu.png')
        self.assertRaises(
            GLib.GError,
            self.protocol.upload,
            src,
            'There is no spoon',
            )
        token.assert_called_once_with()

        self.assertFalse(publish.called)

    def test_search(self):
        self.protocol._get_access_token = lambda: '12345'
        get_pages = self.protocol._follow_pagination = mock.Mock(
            return_value=['search results'])
        publish = self.protocol._publish_entry = mock.Mock()

        self.assertEqual(self.protocol.search('hello'), 1)

        publish.assert_called_with('search results', 'search/hello')
        get_pages.assert_called_with(
            'https://graph.facebook.com/search',
            dict(q='hello', access_token='12345'))

    @mock.patch('friends.protocols.facebook.Downloader')
    def test_like(self, dload):
        dload().get_json.return_value = True
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')

        self.assertEqual(self.protocol.like('post_id'), 'post_id')

        token.assert_called_once_with()
        dload.assert_called_with(
            'https://graph.facebook.com/post_id/likes',
            method='POST',
            params=dict(access_token='face'))

    @mock.patch('friends.protocols.facebook.Downloader')
    def test_unlike(self, dload):
        dload.get_json.return_value = True
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')

        self.assertEqual(self.protocol.unlike('post_id'), 'post_id')

        token.assert_called_once_with()
        dload.assert_called_once_with(
            'https://graph.facebook.com/post_id/likes',
            method='DELETE',
            params=dict(access_token='face'))

    @mock.patch('friends.protocols.facebook.Downloader')
    def test_delete(self, dload):
        dload().get_json.return_value = True
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        unpublish = self.protocol._unpublish = mock.Mock()

        self.assertEqual(self.protocol.delete('post_id'), 'post_id')

        token.assert_called_once_with()
        dload.assert_called_with(
            'https://graph.facebook.com/post_id',
            method='DELETE',
            params=dict(access_token='face'))
        unpublish.assert_called_once_with('post_id')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-contacts.dat'))
    @mock.patch('friends.protocols.facebook.Facebook._login',
                return_value=True)
    def test_fetch_contacts(self, *mocks):
        # Receive the users friends.
        results = self.protocol._fetch_contacts()
        self.assertEqual(len(results), 8)
        self.assertEqual(results[7]['name'], 'John Smith')
        self.assertEqual(results[7]['id'], '444444')

    def test_create_contact(self, *mocks):
        # Receive the users friends.
        bare_contact = {'name': 'Lucy Baron',
                        'id': '555555555',
                        'username': 'lucy.baron5',
                        'link': 'http:www.facebook.com/lucy.baron5'}
        eds_contact = self.protocol._create_contact(bare_contact)
        facebook_id_attr = eds_contact.get_attribute('facebook-id')
        self.assertEqual(facebook_id_attr.get_value(), '555555555')
        facebook_name_attr = eds_contact.get_attribute('facebook-name')
        self.assertEqual(facebook_name_attr.get_value(), 'Lucy Baron')
        web_service_addrs = eds_contact.get_attribute('X-FOLKS-WEB-SERVICES-IDS')
        params= web_service_addrs.get_params()

        self.assertEqual(len(params), 3)

        test_jabber = False
        test_remote_name = False
        test_facebook_id = False

        for p in params:
            if p.get_name() == 'jabber':
                self.assertEqual(len(p.get_values()), 1)
                self.assertEqual(p.get_values()[0], '-555555555@chat.facebook.com')
                test_jabber = True
            if p.get_name() == 'remote-full-name':
                self.assertEqual(len(p.get_values()), 1)
                self.assertEqual(p.get_values()[0], 'Lucy Baron')
                test_remote_name = True
            if p.get_name() == 'facebook-id':
                self.assertEqual(len(p.get_values()), 1)
                self.assertEqual(p.get_values()[0], '555555555')
                test_facebook_id = True
        # Finally test to ensure all key value pairs were tested
        self.assertTrue(test_jabber and test_remote_name and test_facebook_id)

    @mock.patch('friends.utils.base.Base._get_eds_source',
                return_value=True)
    @mock.patch('gi.repository.EBook.BookClient.new',
                return_value=EDSBookClientMock())
    def test_successfull_push_to_eds(self, *mocks):
        bare_contact = {'name': 'Lucy Baron',
                        'id': '555555555',
                        'username': 'lucy.baron5',
                        'link': 'http:www.facebook.com/lucy.baron5'}
        eds_contact = self.protocol._create_contact(bare_contact)
        # Implicitely fail test if the following raises any exceptions
        self.protocol._push_to_eds('test-address-book', eds_contact)

    @mock.patch('friends.utils.base.Base._get_eds_source',
                return_value=None)
    @mock.patch('friends.utils.base.Base._create_eds_source',
                return_value=None)
    def test_unsuccessfull_push_to_eds(self, *mocks):
        bare_contact = {'name': 'Lucy Baron',
                        'id': '555555555',
                        'username': 'lucy.baron5',
                        'link': 'http:www.facebook.com/lucy.baron5'}
        eds_contact = self.protocol._create_contact(bare_contact)
        self.assertRaises(
            ContactsError,
            self.protocol._push_to_eds,
            'test-address-book',
            eds_contact,
            )

    @mock.patch('gi.repository.EDataServer.Source.new',
                return_value=EDSSource('foo', 'bar'))
    def test_create_eds_source(self, *mocks):
        regmock = self.protocol._source_registry = mock.Mock()
        regmock.ref_source = lambda x: x

        result = self.protocol._create_eds_source('facebook-test-address')
        self.assertEqual(result, 'test-source-uid')

    @mock.patch('gi.repository.EBook.BookClient.new',
                return_value=EDSBookClientMock())
    def test_successful_previously_stored_contact(self, *mocks):
        result = self.protocol._previously_stored_contact(
            True, 'facebook-id', '11111')
        self.assertEqual(result, True)

    def test_successful_get_eds_source(self, *mocks):
        class FakeSource:
            def get_display_name(self):
                return 'test-facebook-contacts'
            def get_uid(self):
                return 1345245

        reg_mock = self.protocol._source_registry = mock.Mock()
        reg_mock.list_sources.return_value = [FakeSource()]
        reg_mock.ref_source = lambda x: x
        result = self.protocol._get_eds_source('test-facebook-contacts')
        self.assertEqual(result, 1345245)

    @mock.patch('friends.utils.base.Base._get_eds_source_registry',
                mock.Mock())
    @mock.patch('friends.utils.base.Base._source_registry',
                mock.Mock(**{'list_sources.return_value': []}))
    def test_unsuccessful_get_eds_source(self, *mocks):
        result = self.protocol._get_eds_source('test-incorrect-contacts')
        self.assertIsNone(result)
