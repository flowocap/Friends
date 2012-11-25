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

"""Test the Dee.SharedModel that we use for communicating with our frontend.

This does not test the use of the SharedModel through dbus, since that must be
done in test_dbus.py so as to be isolated from the user's environment.
"""

__all__ = [
    'TestModel',
    ]


import unittest

from friends.utils.model import Model, first_run, stale_schema
from friends.utils.model import prune_model, persist_model
from friends.tests.mocks import LogMock, mock
from gi.repository import Dee


class TestModel(unittest.TestCase):
    """Test our Dee.SharedModel instance."""

    def setUp(self):
        self.log_mock = LogMock('friends.utils.model')

    def tearDown(self):
        self.log_mock.stop()

    def test_basic_properties(self):
        self.assertIsInstance(Model, Dee.SequenceModel)
        self.assertEqual(Model.get_n_columns(), 37)
        self.assertEqual(Model.get_schema(),
                         ['aas', 's', 's', 's', 's', 'b', 's', 's', 's',
                          's', 's', 's', 's', 's', 's', 'd', 'b', 's', 's',
                          's', 's', 's', 's', 's', 's', 's', 's', 's', 's',
                          's', 's', 's', 's', 's', 's', 's', 's'])
        if first_run or stale_schema:
            # Then the Model should be brand-new and empty
            self.assertEqual(Model.get_n_rows(), 0)

    @mock.patch('friends.utils.model._resource_manager')
    def test_persistence(self, resource_manager):
        persist_model()
        resource_manager.store.assert_called_once_with(
            Model, 'com.canonical.Friends.Streams')

    @mock.patch('friends.utils.model.Model')
    @mock.patch('friends.utils.model.persist_model')
    def test_prune_one(self, persist, model):
        model.get_n_rows.return_value = 8001
        def side_effect(arg):
            model.get_n_rows.return_value -= 1
        model.remove.side_effect = side_effect
        prune_model(8000)
        persist.assert_called_once_with()
        model.get_first_iter.assert_called_once_with()
        model.remove.assert_called_once_with(model.get_first_iter())
        self.assertEqual(self.log_mock.empty(),
                         'Deleted 1 rows from Dee.SharedModel.\n')

    @mock.patch('friends.utils.model.Model')
    @mock.patch('friends.utils.model.persist_model')
    def test_prune_one_hundred(self, persist, model):
        model.get_n_rows.return_value = 8100
        def side_effect(arg):
            model.get_n_rows.return_value -= 1
        model.remove.side_effect = side_effect
        prune_model(8000)
        persist.assert_called_once_with()
        self.assertEqual(model.get_first_iter.call_count, 100)
        model.remove.assert_called_with(model.get_first_iter())
        self.assertEqual(model.remove.call_count, 100)
        self.assertEqual(self.log_mock.empty(),
                         'Deleted 100 rows from Dee.SharedModel.\n')

    @mock.patch('friends.utils.model.Model')
    @mock.patch('friends.utils.model.persist_model')
    def test_prune_none(self, persist, model):
        model.get_n_rows.return_value = 100
        def side_effect(arg):
            model.get_n_rows.return_value -= 1
        model.remove.side_effect = side_effect
        prune_model(8000)
        model.get_n_rows.assert_called_once_with()
        self.assertFalse(persist.called)
        self.assertFalse(model.get_first_iter.called)
        self.assertFalse(model.remove.called)
        self.assertEqual(self.log_mock.empty(), '')
