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

"""Test callbacks in our threading architecture."""

__all__ = [
    'TestThreads',
    ]


import unittest
import threading

from friends.tests.mocks import mock
from friends.utils.base import _OperationThread


def join_all_threads():
    current = threading.current_thread()
    for thread in threading.enumerate():
        if thread != current:
            thread.join()


def exception_raiser(exception):
    """Used for testing that the failure callback gets called."""
    raise exception


def it_cant_fail():
    """Used for testing that the success callback gets called."""
    return 1 + 1


def adder(a, b):
    """Used for testing that argument passing works with subthreads."""
    return a + b


@mock.patch('friends.utils.base.notify', mock.Mock())
class TestThreads(unittest.TestCase):
    """Test protocol implementations."""

    def test_exception_calls_failure_callback(self):
        success = mock.Mock()
        failure = mock.Mock()
        err = ValueError('This value is bad, and you should feel bad!')

        _OperationThread(
            id='Test.thread',
            target=exception_raiser,
            success=success,
            failure=failure,
            args=(err,),
            ).start()

        # Wait for threads to exit, avoiding race condition.
        join_all_threads()

        failure.assert_called_once_with(str(err))
        self.assertEqual(success.call_count, 0)

    def test_no_exception_calls_success_callback(self):
        success = mock.Mock()
        failure = mock.Mock()

        _OperationThread(
            id='Test.thread',
            target=it_cant_fail,
            success=success,
            failure=failure,
            ).start()

        # Wait for threads to exit, avoiding race condition.
        join_all_threads()

        success.assert_called_once_with('2')
        self.assertEqual(failure.call_count, 0)

    def test_can_pass_args_to_operations(self):
        success = mock.Mock()
        failure = mock.Mock()

        _OperationThread(
            id='Test.thread',
            target=adder,
            success=success,
            failure=failure,
            args=(5, 7),
            ).start()

        # Wait for threads to exit, avoiding race condition.
        join_all_threads()

        success.assert_called_once_with('12')
        self.assertEqual(failure.call_count, 0)

    def test_can_pass_kwargs_to_operations(self):
        success = mock.Mock()
        failure = mock.Mock()

        _OperationThread(
            id='Test.thread',
            target=adder,
            success=success,
            failure=failure,
            kwargs=dict(a=5, b=7),
            ).start()

        # Wait for threads to exit, avoiding race condition.
        join_all_threads()

        success.assert_called_once_with('12')
        self.assertEqual(failure.call_count, 0)
