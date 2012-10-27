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

"""Test the command line interface for friends-service."""


__all__ = [
    'TestCommandLine',
    ]


import unittest

from itertools import product

from friends.utils.options import Options
from friends.testing.mocks import mock


class TestCommandLine(unittest.TestCase):
    """Test the command line."""

    def setUp(self):
        self.options = Options()

    def test_no_args(self):
        args = self.options.parser.parse_args([])
        self.assertFalse(args.debug)
        self.assertFalse(args.console)

    def test_debug_args(self):
        args = self.options.parser.parse_args(['--debug'])
        self.assertTrue(args.debug)
        self.assertFalse(args.console)
        args = self.options.parser.parse_args(['-d'])
        self.assertTrue(args.debug)
        self.assertFalse(args.console)

    def test_console_args(self):
        args = self.options.parser.parse_args(['--console'])
        self.assertFalse(args.debug)
        self.assertTrue(args.console)
        args = self.options.parser.parse_args(['-o'])
        self.assertFalse(args.debug)
        self.assertTrue(args.console)

    def test_all_flags(self):
        # Test all combinations of flag arguments.
        for options in product(('-d', '--debug'), ('-o', '--console')):
            # argparse requires a list not a tuple.
            options = list(options)
            args = self.options.parser.parse_args(options)
            self.assertTrue(args.debug)
            self.assertTrue(args.console)

    @mock.patch('argparse._sys.exit')
    @mock.patch('argparse._sys.stderr')
    def test_bad_args(self, stderr, exit):
        # Bad arguments.
        #
        # By default, argparse will print a message to stderr and exit when it
        # gets the bad argument.  We could derive from the Options class and
        # override a bunch of methods, but it's a bit easier to just mock two
        # methods to capture the state.
        self.options.parser.parse_args(['--noargument'])
        # In the case of the stderr mock, test suite invocation messes with
        # the error message we expect.  Rather than instrument or deriving
        # from the Options class to accept a special usage string, we just
        # test the tail of the error message.
        called_with = stderr.write.call_args
        # Exactly one positional argument.
        self.assertEqual(len(called_with[0]), 1)
        # No keyword arguments.
        self.assertFalse(called_with[1])
        # And the positional argument contains the error message.
        self.assertEqual(called_with[0][0][-44:-1],
                         'error: unrecognized arguments: --noargument')
        # parse_args() really tried to exit with error code 2.
        exit.assert_called_once_with(2)
