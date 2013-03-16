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


import os
import tempfile
import unittest
import shutil

from gi.repository import GLib
from pkg_resources import resource_filename

from friends.protocols.facebook import Facebook
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock
from friends.tests.mocks import TestModel, mock
from friends.tests.mocks import EDSBookClientMock, EDSSource, EDSRegistry
from friends.errors import ContactsError, FriendsError, AuthorizationError
from friends.utils.cache import JsonCache


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
class TestFacebook(unittest.TestCase):
    """Test the Facebook API."""

    def setUp(self):
        self._temp_cache = tempfile.mkdtemp()
        self._root = JsonCache._root = os.path.join(
            self._temp_cache, '{}.json')
        self.account = FakeAccount()
        self.protocol = Facebook(self.account)
        self.protocol.source_registry = EDSRegistry()

    def tearDown(self):
        TestModel.clear()
        shutil.rmtree(self._temp_cache)

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
                FriendsError,
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
        self.assertEqual(self.protocol.receive(), 12)
        self.assertEqual(TestModel.get_n_rows(), 12)
        self.assertEqual(list(TestModel.get_row(0)), [
            'facebook',
            88,
            'fake_id',
            'mentions',
            'Yours Truly',
            '56789',
            'Yours Truly',
            False,
            '2013-03-13T23:29:07Z',
            'Writing code that supports geotagging data from facebook. ' +
            'If y\'all could make some geotagged facebook posts for me ' +
            'to test with, that\'d be super.',
            GLib.get_user_cache_dir() +
            '/friends/avatars/5c4e74c64b1a09343558afc1046c2b1d176a2ba2',
            'https://www.facebook.com/56789',
            1,
            False,
            '',
            '',
            '',
            '',
            '',
            '',
            'Victoria, British Columbia',
            48.4333,
            -123.35,
            ])
        self.assertEqual(list(TestModel.get_row(2)), [
            'facebook',
            88,
            'faker than cake!',
            'reply_to/fake_id',
            'Father',
            '234',
            'Father',
            False,
            '2013-03-12T23:29:45Z',
            'don\'t know how',
            GLib.get_user_cache_dir() +
            '/friends/avatars/9b9379ccc7948e4804dff7914bfa4c6de3974df5',
            'https://www.facebook.com/234',
            0,
            False,
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            0.0,
            0.0,
            ])
        self.assertEqual(list(TestModel.get_row(6)), [
            'facebook',
            88,
            '161247843901324_629147610444676',
            'mentions',
            'Best Western Denver Southwest',
            '161247843901324',
            'Best Western Denver Southwest',
            False,
            '2013-03-11T23:51:25Z',
            'Today only -- Come meet Caroline and Meredith and Stanley the ' +
            'Stegosaurus (& Greg & Joe, too!) at the TechZulu Trend Lounge, ' +
            'Hilton Garden Inn 18th floor, 500 N Interstate 35, Austin, ' +
            'Texas. Monday, March 11th, 4:00pm to 7:00 pm. Also here ' +
            'Hannah Hart (My Drunk Kitchen) and Angry Video Game Nerd ' +
            'producer, Sean Keegan. Stanley is in the lobby.',
            GLib.get_user_cache_dir() +
            '/friends/avatars/5b2d70e788df790b9c8db4c6a138fc4a1f433ec9',
            'https://www.facebook.com/161247843901324',
            84,
            False,
            'https://fbcdn-photos-a.akamaihd.net/hphotos-ak-snc7/' +
            '601266_629147587111345_968504279_s.jpg',
            '',
            'https://www.facebook.com/photo.php?fbid=629147587111345&set=a.173256162700492.47377.161247843901324&type=1&relevant_count=1',
            '',
            '',
            '',
            'Hilton Garden Inn Austin Downtown/Convention Center',
            30.265384957204,
            -97.735604602521,
            ])
        self.assertEqual(list(TestModel.get_row(9)), [
            'facebook',
            88,
            '104443_100085049977',
            'mentions',
            'Guy Frenchie',
            '1244414',
            'Guy Frenchie',
            False,
            '2013-03-15T19:57:14Z',
            'Guy Frenchie did some things with some stuff.',
            GLib.get_user_cache_dir() +
            '/friends/avatars/3f5e276af0c43f6411d931b829123825ede1968e',
            'https://www.facebook.com/1244414',
            3,
            False,
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            0.0,
            0.0,
            ])

    # XXX We really need full coverage of the receive() method, including
    # cases where some data is missing, or can't be converted
    # (e.g. timestamps), and paginations.

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-full.dat'))
    @mock.patch('friends.protocols.facebook.Facebook._login',
                return_value=True)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_home_since_id(self, *mocks):
        self.account.access_token = 'access'
        self.account.secret_token = 'secret'
        self.account.auth.parameters = dict(
            ConsumerKey='key',
            ConsumerSecret='secret')
        self.assertEqual(self.protocol.home(), 12)

        with open(self._root.format('facebook_ids'), 'r') as fd:
            self.assertEqual(fd.read(), '{"messages": "2013-03-15T19:57:14Z"}')

        follow = self.protocol._follow_pagination = mock.Mock()
        follow.return_value = []
        self.assertEqual(self.protocol.home(), 12)
        follow.assert_called_once_with(
            'https://graph.facebook.com/me/home',
            dict(limit=50,
                 since='2013-03-15T19:57:14Z',
                 access_token='access',
                 )
            )

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
