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

"""Test the JSON cacher."""

__all__ = [
    'TestJsonCache',
    ]


import os
import time
import shutil
import tempfile
import unittest

from datetime import date, timedelta
from pkg_resources import resource_filename

from friends.utils.cache import JsonCache


class TestJsonCache(unittest.TestCase):
    """Test JsonCache logic."""

    def setUp(self):
        self._temp_cache = tempfile.mkdtemp()
        self._root = JsonCache._root = os.path.join(
            self._temp_cache, '{}.json')

    def tearDown(self):
        # Clean up the temporary cache directory.
        shutil.rmtree(self._temp_cache)

    def test_creation(self):
        cache = JsonCache('foo')
        with open(self._root.format('foo'), 'r') as fd:
            empty = fd.read()
        self.assertEqual(empty, '{}')

    def test_values(self):
        cache = JsonCache('bar')
        cache['hello'] = 'world'
        with open(self._root.format('bar'), 'r') as fd:
            result = fd.read()
        self.assertEqual(result, '{"hello": "world"}')

    def test_writes(self):
        cache = JsonCache('stuff')
        cache.update(dict(pi=289/92))
        with open(self._root.format('stuff'), 'r') as fd:
            empty = fd.read()
        self.assertEqual(empty, '{}')
        cache.write()
        with open(self._root.format('stuff'), 'r') as fd:
            result = fd.read()
        self.assertEqual(result, '{"pi": 3.141304347826087}')
