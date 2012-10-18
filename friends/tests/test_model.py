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
from gi.repository import Dee


class TestModel(unittest.TestCase):
    """Test our Dee.SharedModel instance."""

    def test_basic_properties(self):
        self.assertIsInstance(Model, Dee.SharedModel)
        self.assertEqual(Model.get_n_columns(), 37)
        self.assertEqual(Model.get_schema(),
                         ['aas', 's', 's', 's', 'b', 's', 's', 's',
                          's', 's', 's', 's', 's', 's', 'd', 'b', 's', 's',
                          's', 's', 's', 's', 's', 's', 's', 's', 's', 's',
                          's', 's', 's', 's', 's', 'as', 's', 's', 's'])
        if first_run or stale_schema:
            # Then the Model should be brand-new and empty
            self.assertEqual(Model.get_n_rows(), 0)
