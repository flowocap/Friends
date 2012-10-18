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

from gi.repository import Dee
from gi.repository import EBook, EDataServer, Gio, GLib

from friends.protocols.facebook import Facebook
from friends.testing.helpers import FakeAccount
from friends.testing.mocks import FakeSoupMessage, LogMock
from friends.utils.base import Base
from friends.utils.model import COLUMN_TYPES


try:
    # Python 3.3
    from unittest import mock
except ImportError:
    import mock


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)
FACEBOOK_TEST_ADDRESS_BOOK = "fb-contacts-test_address-book"

@mock.patch('friends.utils.download._soup', mock.Mock())

def quit_main_loop(loop):
    loop.quit()
    return False

class TestFacebook(unittest.TestCase):
    """Test the Facebook API."""

    def setUp(self):
        self.account = FakeAccount()
        self.protocol = Facebook(self.account)
        # Enable sub-thread synchronization, and mock out the loggers.
        Base._SYNCHRONIZE = True
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.facebook')
        # Create a new address book for the tests
        ml = GLib.MainLoop()
        GLib.idle_add(self.create_test_address_book, ml)
        ml.run()        

    def tearDown(self):
        # Stop log mocking, and return sub-thread operation to asynchronous.
        self.log_mock.stop()
        Base._SYNCHRONIZE = False
        # Reset the database.
        TestModel.clear()

        ml = GLib.MainLoop()
        GLib.idle_add(self.delete_test_address_book, ml)
        ml.run()        

    def create_test_address_book(self, loop):
        self.registry = EDataServer.SourceRegistry.new_sync(None)  
        source = EDataServer.Source.new(None, None)
        source.set_display_name(FACEBOOK_TEST_ADDRESS_BOOK)
        source.set_parent("local-stub")       
        extension = source.get_extension(EDataServer.SOURCE_EXTENSION_ADDRESS_BOOK)
        extension.set_backend_name("local")
        self.source_uid = None
        if(self.registry.commit_source_sync(source, Gio.Cancellable())):
            self.source_uid = source.get_uid()
        else:
            self.source_uid = None
            print("Can't create new source for our test address book")
        GLib.timeout_add_seconds(1, quit_main_loop, loop)

    def delete_test_address_book(self, loop):
        # Delete the test source
        if(self.source_uid is not None):
            source = self.registry.ref_source(self.source_uid)
            if(source is None):
                print("Teardown could not find the source with that id")
            else:
                res = source.remove_sync(Gio.Cancellable())
                print("Deleted previous found source - deletion result = %s", str(res))
        loop.quit()

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
        self.protocol('receive')
        self.assertEqual(self.log_mock.empty(trim=False), """\
Facebook error (190 OAuthException): Bad access token
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
        self.assertEqual(TestModel.get_n_rows(), 2)
        self.assertEqual(list(TestModel.get_row(0)), [
            [['facebook', 'faker/than fake', '108']],
            'messages',
            '117402931676347',
            'Rush is a Band',
            False,
            '2012-09-26T17:34:00',
            'Rush takes off to the Great White North',
            '',
            'https://s-static.ak.facebook.com/rsrc.php/v2/yD/r/a.gif',
            'https://www.facebook.com/108',
            '',
            '',
            '',
            '',
            16.0,
            True,
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
            [],
            '',
            '',
            ''])
        self.assertEqual(list(TestModel.get_row(1)), [
            [['facebook', 'faker/than fake', '109']],
            'messages',
            '117402931676347',
            'Rush is a Band',
            False,
            '2012-09-26T17:49:06',
            'http://www2.gibson.com/Alex-Lifeson-0225-2011.aspx',
            '',
            'https://s-static.ak.facebook.com/rsrc.php/v2/yD/r/a.gif',
            'https://www.facebook.com/109',
            '',
            '',
            '',
            '',
            27.0,
            True,
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
            ['OK Don...10) Headlong Flight',
             'No Cygnus X-1 Bruce?  I call shenanigans!'],
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
        self.account.access_token = 'abc'
        results = self.protocol.fetch_contacts() 
        self.assertEqual(len(results), 8)
        self.assertEqual(results[7]["name"], "John Smith")
        self.assertEqual(results[7]["id"], "444444")

    def test_create_contact(self, *mocks):
        # Receive the users friends.
        self.account.access_token = 'abc'
        bare_contact = {"name": "Lucy Baron", "id": "555555555"}
        eds_contact = self.protocol.create_contact(bare_contact) 
        facebook_id_attr = eds_contact.get_attribute("facebook-id")
        self.assertEqual(facebook_id_attr.get_value(), "555555555")
        facebook_name_attr = eds_contact.get_attribute("facebook-name")
        self.assertEqual(facebook_name_attr.get_value(), "Lucy Baron")

    def test_push_to_eds(self, *mocks):
        # Receive the users friends.
        ml = GLib.MainLoop()
        GLib.idle_add(self._test_push_to_eds, ml)
        ml.run()

    def _test_push_to_eds(self,  ml):
        bare_contact = {"name": "Lucy Baron", "id": "555555555"}
        eds_contact = self.protocol.create_contact(bare_contact) 
        self.protocol._push_to_eds(FACEBOOK_TEST_ADDRESS_BOOK, eds_contact)
        source = self.registry.ref_source(self.source_uid)
        print("is source none ", str(source == None))
        self.assertEqual(Base.previously_stored_contact(source, "facebook-id", bare_contact['id']), True)
        ml.quit()
