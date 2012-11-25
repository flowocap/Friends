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

"""Test generic protocol support."""

__all__ = [
    'TestProtocolManager',
    'TestProtocols',
    ]


import unittest
import threading

from gi.repository import Dee

from friends.protocols.flickr import Flickr
from friends.protocols.twitter import Twitter
from friends.tests.mocks import FakeAccount, LogMock, mock
from friends.utils.base import Base, feature
from friends.utils.manager import ProtocolManager
from friends.utils.model import (
    COLUMN_INDICES, COLUMN_NAMES, COLUMN_TYPES, Model)


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


class TestProtocolManager(unittest.TestCase):
    """Test the protocol finder."""

    def setUp(self):
        self.manager = ProtocolManager()
        self.log_mock = LogMock('friends.utils.base')

    def tearDown(self):
        self.log_mock.stop()

    def test_find_all_protocols(self):
        # The manager can find all the protocol classes.
        self.assertEqual(self.manager.protocols['flickr'], Flickr)
        self.assertEqual(self.manager.protocols['twitter'], Twitter)

    def test_doesnt_find_base(self):
        # Make sure that the base protocol class isn't returned.
        self.assertNotIn('base', self.manager.protocols)
        for protocol_class in self.manager.protocols.values():
            self.assertNotEqual(protocol_class, Base)


class MyProtocol(Base):
    """Simplest possible protocol implementation to allow testing of Base."""

    # This exists just to make it easier to test that noop() was actually
    # called asynchronously.  Normally, __call__() is not expected to, nor
    # does it really support, returning results.
    result = ''

    def noop(self, one=None, two=None):
        self.result = '{}:{}'.format(one, two)

    # A non-public method that cannot be called through __call__()
    _private = noop

    def _locked_login(self, old_token):
        self._account.access_token = 'fake_token'

    # Two features and two non-features for testing purposes.

    @feature
    def feature_1(self): pass

    @feature
    def feature_2(self): pass

    def non_feature_1(self): pass

    def non_feature_2(self): pass


@mock.patch('friends.utils.base.notify', mock.Mock())
class TestProtocols(unittest.TestCase):
    """Test protocol implementations."""

    def setUp(self):
        TestModel.clear()

    def test_no_operation(self):
        # Trying to call a protocol with a missing operation raises an
        # AttributeError exception.
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        with self.assertRaises(NotImplementedError) as cm:
            my_protocol('give_me_a_pony')
        self.assertEqual(str(cm.exception), 'give_me_a_pony')

    def test_private_operation(self):
        # Trying to call a protocol with a non-public operation raises an
        # AttributeError exception.
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        # We can call the method directly.
        my_protocol._private('ant', 'bee')
        self.assertEqual(my_protocol.result, 'ant:bee')
        # But we cannot call the method through the __call__ interface.
        my_protocol.result = ''
        with self.assertRaises(NotImplementedError) as cm:
            my_protocol('_private', 'cat', 'dog')
        self.assertEqual(str(cm.exception), '_private')
        self.assertEqual(my_protocol.result, '')

    def test_basic_api_synchronous(self):
        # Protocols get instantiated with an account, and the instance gets
        # called to perform an operation.
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        my_protocol.noop(one='foo', two='bar')
        self.assertEqual(my_protocol.result, 'foo:bar')

    def test_basic_api_asynchronous(self):
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        # Using __call__ makes invocation happen asynchronously in a thread.
        my_protocol('noop', one='one', two='two')
        for thread in threading.enumerate():
            # Join all but the main thread.
            if thread != threading.current_thread():
                thread.join()
        self.assertEqual(my_protocol.result, 'one:two')

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_shared_model_successfully_mocked(self):
        count = Model.get_n_rows()
        self.assertEqual(TestModel.get_n_rows(), 0)
        base = Base(FakeAccount())
        base._publish('alpha', message='a')
        base._publish('beta', message='b')
        base._publish('omega', message='c')
        self.assertEqual(Model.get_n_rows(), count)
        self.assertEqual(TestModel.get_n_rows(), 3)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    @mock.patch('friends.utils.base._seen_messages', {})
    def test_seen_dicts_successfully_instantiated(self):
        from friends.utils.base import _seen_ids, _seen_messages
        from friends.utils.base import initialize_caches
        self.assertEqual(TestModel.get_n_rows(), 0)
        base = Base(FakeAccount())
        base._publish('alpha', sender='a', message='a')
        base._publish('beta', sender='a', message='a')
        base._publish('omega', sender='a', message='b')
        self.assertEqual(TestModel.get_n_rows(), 2)
        _seen_ids.clear()
        _seen_messages.clear()
        initialize_caches()
        self.assertEqual(sorted(list(_seen_messages.keys())), ['aa', 'ab'])
        self.assertEqual(sorted(list(_seen_ids.keys())),
                         [('base', 'faker/than fake', 'alpha'),
                          ('base', 'faker/than fake', 'beta'),
                          ('base', 'faker/than fake', 'omega')])
        # These two point at the same row because sender+message are identical
        self.assertEqual(_seen_ids[('base', 'faker/than fake', 'alpha')],
                         _seen_ids[('base', 'faker/than fake', 'beta')])

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_invalid_argument(self):
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        with self.assertRaises(TypeError) as cm:
            base._publish('message_id', invalid_argument='not good')
        self.assertEqual(str(cm.exception),
                         'Unexpected keyword arguments: invalid_argument')

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_invalid_arguments(self):
        # All invalid arguments are mentioned in the exception message.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        with self.assertRaises(TypeError) as cm:
            base._publish('p.middy', bad='no', wrong='yes')
        self.assertEqual(str(cm.exception),
                         'Unexpected keyword arguments: bad, wrong')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_one_message(self):
        # Test that publishing a message inserts a row into the model.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        self.assertEqual(1, TestModel.get_n_rows())
        row = TestModel.get_row(0)
        # For convenience.
        def V(column_name):
            return row[COLUMN_INDICES[column_name]]
        self.assertEqual(V('message_ids'),
                         [['base', 'faker/than fake', '1234']])
        self.assertEqual(V('stream'), 'messages')
        self.assertEqual(V('sender'), 'fred')
        self.assertEqual(V('sender_nick'), 'freddy')
        self.assertTrue(V('from_me'))
        self.assertEqual(V('timestamp'), 'today')
        self.assertEqual(V('message'), 'hello, @jimmy')
        self.assertEqual(V('likes'), 10)
        self.assertTrue(V('liked'))
        # All the other columns have empty string values.
        empty_columns = set(COLUMN_NAMES) - set(
            ['message_ids', 'stream', 'sender', 'sender_nick', 'from_me',
             'timestamp', 'comments', 'message', 'likes', 'liked'])
        for column_name in empty_columns:
            self.assertEqual(row[COLUMN_INDICES[column_name]], '')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_unpublish(self):
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='5678',
            sender='fred',
            message='hello, +jimmy'))
        self.assertEqual(1, TestModel.get_n_rows())
        self.assertEqual(TestModel[0][0],
                         [['base', 'faker/than fake', '1234'],
                          ['base', 'faker/than fake', '5678']])
        base._unpublish('1234')
        self.assertEqual(1, TestModel.get_n_rows())
        self.assertEqual(TestModel[0][0],
                         [['base', 'faker/than fake', '5678']])
        base._unpublish('5678')
        self.assertEqual(0, TestModel.get_n_rows())

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_duplicate_messages_identified(self):
        # When two messages which are deemed identical, by way of the
        # _make_key() test in base.py, are published, only one ends up in the
        # model.  However, the message_ids list-of-lists gets both sets of
        # identifiers.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        # Insert the first message into the table.  The key will be the string
        # 'fredhellojimmy'
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        # Insert the second message into the table.  Note that because
        # punctuation was stripped from the above message, this one will also
        # have the key 'fredhellojimmy', thus it will be deemed a duplicate.
        self.assertTrue(base._publish(
            message_id='5678',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello jimmy',
            likes=10,
            liked=False))
        # See, we get only one row in the table.
        self.assertEqual(1, TestModel.get_n_rows())
        # The first published message wins.
        row = TestModel.get_row(0)
        self.assertEqual(row[COLUMN_INDICES['message']], 'hello, @jimmy')
        # Both message ids will be present, in the order they were published.
        self.assertEqual(row[COLUMN_INDICES['message_ids']],
                         [['base', 'faker/than fake', '1234'],
                          ['base', 'faker/than fake', '5678']])

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_duplicate_ids_not_duplicated(self):
        # When two messages are actually identical (same ids and all),
        # we need to avoid duplicating the id in the sharedmodel.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            message='hello, @jimmy'))
        self.assertEqual(1, TestModel.get_n_rows())
        row = TestModel.get_row(0)
        # The same message_id should not appear twice.
        self.assertEqual(row[COLUMN_INDICES['message_ids']],
                         [['base', 'faker/than fake', '1234']])

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_messages', {})
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_similar_messages_allowed(self):
        # Because both the sender and message contribute to the unique key we
        # use to identify messages, if two messages are published with
        # different senders, both are inserted into the table.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        # The key for this row is 'fredhellojimmy'
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        self.assertEqual(1, TestModel.get_n_rows())
        # The key for this row is 'tedtholomewhellojimmy'
        self.assertTrue(base._publish(
            message_id='34567',
            stream='messages',
            sender='tedtholomew',
            sender_nick='teddy',
            from_me=False,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        # See?  Two rows in the table.
        self.assertEqual(2, TestModel.get_n_rows())
        # The first row is the message from fred.
        self.assertEqual(TestModel.get_row(0)[COLUMN_INDICES['sender']],
                         'fred')
        # The second row is the message from tedtholomew.
        self.assertEqual(TestModel.get_row(1)[COLUMN_INDICES['sender']],
                         'tedtholomew')

    def test_basic_login(self):
        # Try to log in twice.  The second login attempt returns False because
        # it's already logged in.
        my_protocol = MyProtocol(FakeAccount())
        self.assertTrue(my_protocol._login())
        self.assertFalse(my_protocol._login())

    def test_failing_login(self):
        # The first login attempt fails because _locked_login() does not set
        # an access token.
        class FailingProtocol(MyProtocol):
            def _locked_login(self, old_token):
                pass
        my_protocol = FailingProtocol(FakeAccount())
        self.assertFalse(my_protocol._login())

    # XXX I think there's a threading test that should be performed, but it
    # hurts my brain too much.  See the comment at the bottom of the
    # with-statement in Base._login().

    def test_features(self):
        self.assertEqual(MyProtocol.get_features(), ['feature_1', 'feature_2'])
