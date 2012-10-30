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

"""Test the Facebook plugin."""

__all__ = [
    'TestFacebook',
    ]


import unittest

from gi.repository import Dee, EBook, EDataServer, Gio, GLib

from friends.protocols.facebook import Facebook
from friends.testing.helpers import FakeAccount
from friends.testing.mocks import FakeSoupMessage, LogMock, mock
from friends.testing.mocks import EDSBookClientMock, EDSSource, EDSRegistry
from friends.utils.base import Base
from friends.utils.model import COLUMN_TYPES


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


@mock.patch('friends.utils.download._soup', mock.Mock())
class TestFacebook(unittest.TestCase):
    """Test the Facebook API."""

    def setUp(self):
        self.account = FakeAccount()
        self.protocol = Facebook(self.account)
        self.protocol.source_registry = EDSRegistry()
        # Enable sub-thread synchronization, and mock out the loggers.
        Base._SYNCHRONIZE = True

    def tearDown(self):
        # Stop log mocking, and return sub-thread operation to asynchronous.
        Base._SYNCHRONIZE = False
        # Reset the database.
        TestModel.clear()

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='abc'))
    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-login.dat'))
    def test_successful_login(self, mock):
        # Test that a successful response from graph.facebook.com returning
        # the user's data, sets up the account dict correctly.
        self.protocol._login()
        self.assertEqual(self.account.access_token, 'abc')
        self.assertEqual(self.account.user_name, 'Bart Person')
        self.assertEqual(self.account.user_id, '801')

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=None)
    def test_login_unsuccessful_authentication(self, mock):
        # The user is not already logged in, but the act of logging in fails.
        self.protocol._login()
        self.assertIsNone(self.account.access_token)
        self.assertIsNone(self.account.user_name)

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value={})
    def test_unsuccessful_login_no_access_token(self, mock):
        # When Authentication.login() returns a dictionary, but that does not
        # have the AccessToken key, then the account data is not updated.
        self.protocol._login()
        self.assertIsNone(self.account.access_token)
        self.assertIsNone(self.account.user_name)

    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='abc'))
    @mock.patch('friends.protocols.facebook.get_json',
                return_value=dict(
                    error=dict(message='Bad access token',
                               type='OAuthException',
                               code=190)))
    def test_error_response(self, *mocks):
        with LogMock('friends.utils.base',
                     'friends.protocols.facebook') as log_mock:
            self.protocol('receive')
            contents = log_mock.empty(trim=False)
        self.assertEqual(contents, """\
Facebook.receive is starting in a new thread.
Logging in to Facebook
Facebook UID: None
Facebook error (190 OAuthException): Bad access token
Facebook.receive has completed, thread exiting.
""")

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-full.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.protocols.facebook.Facebook._login',
                return_value=True)
    def test_receive(self, *mocks):
        # Receive the wall feed for a user.
        self.maxDiff = None
        self.account.access_token = 'abc'
        self.protocol.receive()
        self.assertEqual(TestModel.get_n_rows(), 4)
        self.assertEqual(list(TestModel.get_row(0)), [
            [['facebook',
              'faker/than fake',
              '117402931676347_386054134801436_3235476']],
            'reply_to/109',
            'Bruce Peart',
            'Bruce Peart',
            False,
            '2012-09-26T17:16:00Z',
            'OK Don...10) Headlong Flight',
            '',
            '',
            'https://www.facebook.com/117402931676347_386054134801436_3235476',
            '',
            '',
            '',
            '',
            0.0,
            False,
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''])
        self.assertEqual(list(TestModel.get_row(1)), [
            [['facebook', 'faker/than fake', '108']],
            'messages',
            'Rush is a Band',
            'Rush is a Band',
            False,
            '2012-09-26T17:34:00Z',
            'Rush takes off to the Great White North',
            '',
            '',
            'https://www.facebook.com/108',
            '',
            '',
            '',
            '',
            16.0,
            False,
            '',
            '',
            '',
            'https://fbexternal-a.akamaihd.net/rush.jpg',
            'Rush is a Band Blog',
            'http://www.rushisaband.com/blog/Rush-Clockwork-Angels-tour',
            'Rush is a Band: Neil Peart, Geddy Lee, Alex Lifeson',
            'www.rushisaband.com',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''])
        self.assertEqual(list(TestModel.get_row(3)), [
            [['facebook', 'faker/than fake', '109']],
            'messages',
            'Rush is a Band',
            'Rush is a Band',
            False,
            '2012-09-26T17:49:06Z',
            'http://www2.gibson.com/Alex-Lifeson-0225-2011.aspx',
            '',
            '',
            'https://www.facebook.com/109',
            '',
            '',
            '',
            '',
            27.0,
            False,
            '',
            '',
            '',
            'https://images.gibson.com/Rush_Clockwork-Angels_t.jpg',
            'Top 10 Alex Lifeson Guitar Moments',
            'http://www2.gibson.com/Alex-Lifeson.aspx',
            'For millions of Rush fans old and new, it’s a pleasure',
            'www2.gibson.com',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''])

    # XXX We really need full coverage of the receive() method, including
    # cases where some data is missing, or can't be converted
    # (e.g. timestamps), and paginations.

    @mock.patch('friends.protocols.facebook.get_json',
                return_value=dict(id='post_id'))
    def test_send_to_my_wall(self, get_json):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish_entry = mock.Mock()

        self.protocol.send('I can see the writing on my wall.')

        token.assert_called_once_with()
        publish.assert_called_with({'id': 'post_id'})
        self.assertEqual(
            get_json.mock_calls,
            [mock.call('https://graph.facebook.com/me/feed',
                       method='POST',
                       params=dict(
                           access_token='face',
                           message='I can see the writing on my wall.')),
             mock.call('https://graph.facebook.com/post_id',
                       params=dict(access_token='face'))
            ])

    @mock.patch('friends.protocols.facebook.get_json',
                return_value=dict(id='post_id'))
    def test_send_to_my_friends_wall(self, get_json):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish_entry = mock.Mock()

        self.protocol.send('I can see the writing on my friend\'s wall.',
                           'friend_id')

        token.assert_called_once_with()
        publish.assert_called_with({'id': 'post_id'})
        self.assertEqual(
            get_json.mock_calls,
            [mock.call(
                    'https://graph.facebook.com/friend_id/feed',
                    method='POST',
                    params=dict(
                       access_token='face',
                       message='I can see the writing on my friend\'s wall.')),
             mock.call('https://graph.facebook.com/post_id',
                       params=dict(access_token='face'))
             ])

    @mock.patch('friends.protocols.facebook.get_json',
                return_value=dict(id='comment_id'))
    def test_send_thread(self, get_json):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        publish = self.protocol._publish_entry = mock.Mock()

        self.protocol.send_thread('post_id', 'Some witty response!')

        token.assert_called_once_with()
        publish.assert_called_with({'id': 'comment_id'})
        self.assertEqual(
            get_json.mock_calls,
            [mock.call(
                    'https://graph.facebook.com/post_id/comments',
                    method='POST',
                    params=dict(
                        access_token='face',
                        message='Some witty response!')),
             mock.call('https://graph.facebook.com/comment_id',
                       params=dict(access_token='face'))
             ])

    def test_search(self):
        self.protocol._get_access_token = lambda: '12345'
        get_pages = self.protocol._follow_pagination = mock.Mock(
            return_value=['search results'])
        publish = self.protocol._publish_entry = mock.Mock()

        self.protocol.search('hello')

        publish.assert_called_with('search results', 'search/hello')
        get_pages.assert_called_with(
            'https://graph.facebook.com/search',
            dict(q='hello', access_token='12345'))

    @mock.patch('friends.protocols.facebook.get_json',
                return_value=True)
    def test_like(self, get_json):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')

        self.protocol.like('post_id')

        token.assert_called_once_with()
        get_json.assert_called_once_with(
            'https://graph.facebook.com/post_id/likes',
            method='POST',
            params=dict(access_token='face'))

    @mock.patch('friends.protocols.facebook.get_json',
                return_value=True)
    def test_unlike(self, get_json):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')

        self.protocol.unlike('post_id')

        token.assert_called_once_with()
        get_json.assert_called_once_with(
            'https://graph.facebook.com/post_id/likes',
            method='DELETE',
            params=dict(access_token='face'))

    @mock.patch('friends.protocols.facebook.get_json',
                return_value=True)
    def test_delete(self, get_json):
        token = self.protocol._get_access_token = mock.Mock(
            return_value='face')
        unpublish = self.protocol._unpublish = mock.Mock()

        self.protocol.delete('post_id')

        token.assert_called_once_with()
        get_json.assert_called_once_with(
            'https://graph.facebook.com/post_id',
            method='DELETE',
            params=dict(access_token='face'))
        unpublish.assert_called_once_with('post_id')

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'facebook-contacts.dat'))
    @mock.patch('friends.protocols.facebook.Facebook._login',
                return_value=True)
    def test_fetch_contacts(self, *mocks):
        # Receive the users friends.
        results = self.protocol.fetch_contacts()
        self.assertEqual(len(results), 8)
        self.assertEqual(results[7]['name'], 'John Smith')
        self.assertEqual(results[7]['id'], '444444')

    def test_create_contact(self, *mocks):
        # Receive the users friends.
        bare_contact = {'name': 'Lucy Baron',
                        'id': '555555555',
                        'username': "lucy.baron5",
                        'link': 'http:www.facebook.com/lucy.baron5'}
        eds_contact = self.protocol.create_contact(bare_contact)
        facebook_id_attr = eds_contact.get_attribute('facebook-id')
        self.assertEqual(facebook_id_attr.get_value(), '555555555')
        facebook_name_attr = eds_contact.get_attribute('facebook-name')
        self.assertEqual(facebook_name_attr.get_value(), 'Lucy Baron')
        web_service_addrs = eds_contact.get_attribute('X-FOLKS-WEB-SERVICES-IDS')
        self.assertEqual(len(web_service_addrs.get_params()), 1)
        self.assertEqual(web_service_addrs.get_params()[0].get_name(), "jabber")
        self.assertEqual(len(web_service_addrs.get_params()[0].get_values()), 1)
        self.assertEqual(web_service_addrs.get_params()[0].get_values()[0], "-555555555@chat.facebook.com")
            
    @mock.patch('friends.utils.base.Base._get_eds_source',
                return_value=True)
    @mock.patch('gi.repository.EBook.BookClient.new',
                return_value=EDSBookClientMock())
    def test_successfull_push_to_eds(self, *mocks):
        bare_contact = {'name': 'Lucy Baron',
                        'id': '555555555',
                        'username': "lucy.baron5",
                        'link': 'http:www.facebook.com/lucy.baron5'}
        eds_contact = self.protocol.create_contact(bare_contact)
        result = self.protocol._push_to_eds('test-address-book', eds_contact)
        self.assertEqual(result, True)

    @mock.patch('friends.utils.base.Base._get_eds_source',
                return_value=None)
    @mock.patch('friends.utils.base.Base._create_eds_source',
                return_value=None)
    def test_unsuccessfull_push_to_eds(self, *mocks):
        bare_contact = {'name': 'Lucy Baron',
                        'id': '555555555',
                        'username': "lucy.baron5",
                        'link': 'http:www.facebook.com/lucy.baron5'}
        eds_contact = self.protocol.create_contact(bare_contact)
        result = self.protocol._push_to_eds('test-address-book', eds_contact)
        self.assertEqual(result, False)

    @mock.patch('gi.repository.EDataServer.Source.new',
                return_value=EDSSource('foo', 'bar'))
    def test_create_eds_source(self, *mocks):
        self.protocol._source_registry = mock.Mock()
        result = self.protocol._create_eds_source('facebook-test-address')
        self.assertEqual(result, 'test-source-uid')

    @mock.patch('gi.repository.EBook.BookClient.new',
                return_value=EDSBookClientMock())
    def test_successful_previously_stored_contact(self, *mocks):
        result = Facebook.previously_stored_contact(
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

    def test_unsuccessful_get_eds_source(self, *mocks):
        result = self.protocol._get_eds_source('test-incorrect-contacts')
        self.assertIsNone(result)





